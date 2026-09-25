"""Build and send the Portland events digest.

    python main.py                  scheduled run: sends on weekday mornings, once a day
    python main.py --force          send now
    python main.py --dry-run        write preview.html and preview.txt instead of sending
    python main.py --only-me        send now, but only to the Gmail address it sends from
    python main.py --only-me --weather rainy   ...pretending it's a rainy day, to try a header
    python main.py --dry-run --date 2026-10-02
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from config import load_settings
from mailer import banners, render
from mailer.send import build_message, send
from pipeline import Digest, NoSourcesAvailable, build_digest
import ranking
import weather

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("digest")


def should_send(now: datetime, tz: ZoneInfo, send_from: time, send_until: time) -> bool:
    """Whether a scheduled run at `now` falls in the weekday send window.

    GitHub starts scheduled jobs late, often by hours on busy mornings, so
    the workflow tries every half hour and this decides by the actual
    clock. The workflow separately skips runs once the day's email is out.
    """
    local = now.astimezone(tz)
    return local.weekday() < 5 and send_from <= local.time() < send_until


def _mark_sent() -> None:
    """Tell the workflow today's email went out, so later runs skip."""
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a") as f:
            f.write("sent=true\n")


def log_ranking(digest: Digest, prefs) -> None:
    """For previews: what each section chose and why, and what it had to
    choose from."""
    for s in digest.sections:
        pool = s.events + s.rest
        mix = Counter(ranking.bucket(e.category) for e in pool)
        log.info("%s: %d shown of %d. Candidates by category: %s", s.title, len(s.events), len(pool),
                 ", ".join(f"{c} {n}" for c, n in mix.most_common()))
        for e in s.events:
            parts = ranking.breakdown(e, prefs, s.key)
            detail = " + ".join(f"{k} {v:.1f}" for k, v in parts.items() if v)
            runs = f", {len(e.other_dates) + 1} dates" if e.other_dates else ""
            star = "*" if e is s.pick else " "
            log.info(" %s%.1f  %-14s %s @ %s (%s%s)", star, sum(parts.values()), ranking.bucket(e.category),
                     e.name[:50], e.venue[:30], detail, runs)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Portland events digest")
    parser.add_argument("--dry-run", action="store_true", help="write a preview instead of sending")
    parser.add_argument("--force", action="store_true", help="send regardless of day and time")
    parser.add_argument("--only-me", action="store_true",
                        help="send now, only to the sending Gmail address (for trying things out)")
    parser.add_argument("--weather", choices=weather.CONDITIONS,
                        help="pretend today's weather is this, to try out its header")
    parser.add_argument("--date", type=date.fromisoformat, help="build the digest for this date (YYYY-MM-DD)")
    parser.add_argument("--output", type=Path, default=Path("preview.html"), help="preview path for --dry-run")
    args = parser.parse_args(argv)

    settings = load_settings(require_email=not args.dry_run)
    now = datetime.now(settings.timezone)

    if not (args.dry_run or args.force or args.only_me):
        if os.environ.get("ALREADY_SENT") == "true":
            log.info("Today's email already went out.")
            return 0
        if not should_send(now, settings.timezone, settings.send_from, settings.send_until):
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
    condition = forecast.condition if forecast else None
    if args.weather:
        condition = args.weather
        subject = f"[Testing the {args.weather} header] {subject}"
    text = render.text(digest, settings.from_name, weather_line)
    header = banners.header_for(condition, digest.window.today, prefs.headers)
    images = banners.available(header)
    log.info("%s (%d listings)", subject, digest.total)
    if forecast:
        log.info("Weather: %s [%s]", forecast.line, forecast.condition)
    log.info("Header: %s", images[0].path.name if images else "none")

    if args.dry_run:
        log_ranking(digest, prefs)
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
    if not args.only_me:
        _mark_sent()
    return 0


if __name__ == "__main__":
    sys.exit(main())
