"""Build and send the Portland events digest.

    python main.py                  scheduled run: sends only at 8am Pacific on weekdays
    python main.py --force          send now
    python main.py --dry-run        write preview.html and preview.txt instead of sending
    python main.py --only-me        send now, but only to the Gmail address it sends from
    python main.py --dry-run --date 2026-10-02
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from config import load_settings
from mailer import banners, render
from mailer.send import build_message, send
from pipeline import NoSourcesAvailable, build_digest
import weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("digest")


def should_send(now: datetime, tz: ZoneInfo, send_hour: int, schedule: Optional[str] = None) -> bool:
    """Whether a run at `now` should send.

    GitHub Actions cron is UTC-only, so the workflow fires at both 15:00
    and 16:00 UTC: 8am in summer and 8am in winter. `schedule` is the cron
    string that fired this run. The check is whether that cron's UTC hour
    is 8am Portland time today, which holds even when GitHub starts the job
    late, as it often does on busy mornings. Without a schedule (a local
    run), fall back to the wall clock.
    """
    local = now.astimezone(tz)
    if local.weekday() >= 5:
        return False
    if schedule:
        scheduled_hour = int(schedule.split()[1])
        target = datetime.combine(local.date(), time(send_hour), tz).astimezone(timezone.utc)
        return target.hour == scheduled_hour
    return local.hour == send_hour


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Portland events digest")
    parser.add_argument("--dry-run", action="store_true", help="write a preview instead of sending")
    parser.add_argument("--force", action="store_true", help="send regardless of day and time")
    parser.add_argument("--only-me", action="store_true",
                        help="send now, only to the sending Gmail address (for trying things out)")
    parser.add_argument("--date", type=date.fromisoformat, help="build the digest for this date (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=Path("preview.html"), help="preview path for --dry-run")
    args = parser.parse_args(argv)

    settings = load_settings(require_email=not args.dry_run)
    now = datetime.now(settings.timezone)

    if not (args.dry_run or args.force or args.only_me):
        schedule = os.environ.get("SCHEDULE") or None
        if not should_send(now, settings.timezone, settings.send_hour, schedule):
            log.info("Not the send window (%s). Use --force to send anyway.", now.strftime("%a %H:%M %Z"))
            return 0

    try:
        digest = build_digest(settings, args.date or now.date())
    except NoSourcesAvailable as exc:
        log.error("%s", exc)
        return 1

    prefs = settings.prefs
    forecast = weather.fetch(prefs.latitude, prefs.longitude, digest.window.today, settings.timezone.key)
    weather_line = forecast.line if forecast else None
    subject = render.subject(digest, prefs.subject_lines or render.DEFAULT_SUBJECTS, prefs.subject_by_day)
    text = render.text(digest, settings.from_name, weather_line)
    images = banners.available(forecast.condition if forecast else None)
    log.info("%s (%d listings)", subject, digest.total)
    if forecast:
        log.info("Weather: %s [%s, using %s]", forecast.line, forecast.condition, images[0].path.name if images else "no header")

    if args.dry_run:
        preview = render.html(digest, settings.from_name, banners.sources(images, inline=False), weather_line)
        args.output.write_text(preview)
        args.output.with_suffix(".txt").write_text(text)
        log.info("Wrote %s and %s", args.output, args.output.with_suffix(".txt"))
        return 0

    if digest.total == 0:
        log.info("Nothing to send today.")
        return 0

    html = render.html(digest, settings.from_name, banners.sources(images, inline=True), weather_line)
    recipients = (settings.smtp_user,) if args.only_me else settings.recipients
    messages = [
        build_message(settings.smtp_user, settings.from_name, to, subject, html, text, images)
        for to in recipients
    ]
    send(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password, messages)
    return 0


if __name__ == "__main__":
    sys.exit(main())
