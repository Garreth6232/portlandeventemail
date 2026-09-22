# Portland Events

A weekday-morning email of things to do around Portland, sent at 8am to a
short list of people. It leans toward repertory film, wine bars, small shows
and park events, with the occasional big arena night mixed in.

Each email has three sections:

- **Today**
- **This Week**, the next seven days
- **Coming Up**, the 23 days after that

Anything that repeats (a film's run, weekly trivia, a Saturday market) shows
up once, at its next date, with a note like "Runs through Sun 10/18, 7
showings".

It runs on GitHub Actions, so there's no server to keep alive.

## Where listings come from

| Source | What it covers | Key needed |
| --- | --- | --- |
| Hollywood Theatre | Every screening, from the theater's own site | No |
| Portland Art Museum | Exhibitions, talks, and PAM CUT screenings at the Tomorrow Theater | No |
| Literary Arts | Readings, author talks, Portland Arts & Lectures | No |
| PDX Pipeline | The weekly roundup: bars, trivia, happy hours, small shows | No |
| PDX Vine and Dine | The weekly wine tasting roundup, as one listing | No |
| Oregon Wine Board | Tastings and winemaker dinners in Portland and the north Willamette Valley | No |
| Portland Farmers Market | Every market day across the city | No |
| Portland Parks & Recreation | Park events, movies and concerts in the parks | No |
| Lan Su Chinese Garden | Festivals, performances, and garden events | No |
| Pioneer Courthouse Square | Free concerts, watch parties, and downtown happenings | No |
| Ticketmaster | Shows at the venues listed in `preferences.toml` | Free |
| SeatGeek | The same, and a cross-check on Ticketmaster | Free |

The middle six all run the same WordPress calendar plugin, so they share one
connector (`sources/events_calendar.py`) and are listed under `[[calendars]]`
in `preferences.toml`. Adding another site that uses it is four lines there.

Ticketmaster and SeatGeek list almost everything with a box office, so only
the venues under `[ticketed]` get through. `big_venues` (Moda Center,
Providence Park, the Keller and so on) are capped at two per section.
`small_venues` (Doug Fir, Mississippi Studios, Wonder Ballroom, Helium and
others) rank like any other listing. Any of those rooms that sell through
Ticketmaster or SeatGeek will show up; ones that use a different box office
won't. Parking passes, suites and similar add-ons are dropped.

Each section holds at most three listings from one category, so a week with
twenty screenings still shows a tasting, a reading and a show alongside the
films. If there aren't enough other categories to fill the section, the
next-best listings fill the rest.

When two sources list the same event, it appears once. Same-day listings at
the same venue count as one event if the names are close, or if both come
from ticketing sites and start within half an hour of each other.

## Setup

1. **Turn on 2-Step Verification for the Gmail account the email will come
   from**, then make an app password for it at
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   Google shows a 16-character password once; copy it. This lets the job
   send from that Gmail account without knowing its real password, and you
   can revoke it any time from the same page.

2. **Optionally, get Ticketmaster and SeatGeek keys.** Ticketmaster: create
   an app at [developer.ticketmaster.com](https://developer.ticketmaster.com)
   and copy the Consumer Key. SeatGeek: [seatgeek.com/account/develop](https://seatgeek.com/account/develop).
   Skip either and the email still goes out without it.

3. **Put the code in a private GitHub repo.** Private because the recipient
   list lives in its secrets. GitHub Desktop is the easiest way; uploading
   through the website tends to skip the hidden `.github` folder, and the
   schedule lives in there.

4. **Add repository secrets** under Settings > Secrets and variables > Actions:

   | Secret | Value |
   | --- | --- |
   | `GMAIL_ADDRESS` | the Gmail address from step 1 |
   | `GMAIL_APP_PASSWORD` | the 16-character app password |
   | `RECIPIENTS` | comma-separated, e.g. `you@gmail.com,partner@gmail.com` |
   | `TICKETMASTER_API_KEY` | optional |
   | `SEATGEEK_CLIENT_ID` | optional |

   `FROM_NAME` can go under the Variables tab if you want something other
   than "Portland Events".

5. **Send a test.** Actions > Send digest > Run workflow, with "Send now"
   checked.

After that it sends every weekday at 8. Gmail allows a personal account
about 500 recipients a day, so four people is nowhere near the limit.

## Changing what shows up

Everything about taste lives in `preferences.toml`: category weights,
keyword boosts ("35mm", "natural wine"), favorite venues, which venues
Ticketmaster and SeatGeek can list from, the calendar sites, section sizes
(8 today, 12 this week, 12 coming up), how many per category, and where
the search is centered. Edit it, push, and the next email reflects it.

How an event's score works: its category weight, plus the largest keyword
boost it matches, plus a bump if the venue is a favorite, plus a little
more for each extra source that lists it. The top scorers in each section
make the email, then get sorted by time. The rest are counted in a
"Plus 4 more this week" line.

## Header and footer images

`assets/header.png` sits at the top of every email and `assets/footer.png`
at the bottom. They're attached to each email rather than linked, so they
work from a private repo and don't need hosting anywhere.

To change one, replace the file with another PNG of the same name. Make it
1120 pixels wide; it's shown at 560, which keeps it sharp on phones. Any
height works. Delete a file to go without it. With no header, the email
falls back to its name in text.

Some mail apps hide images until you tap "show images", so nothing
essential should live only in the pictures.

## Running it locally

Needs Python 3.11 or newer.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env

python main.py --dry-run                     # writes preview.html and preview.txt
python main.py --dry-run --date 2026-10-02   # as if it were another day
python main.py --force                       # a real send, right now
python -m pytest
```

A dry run doesn't need the Gmail settings.

## Scheduling

GitHub's cron runs in UTC and doesn't follow daylight saving, so the
workflow fires at both 15:00 and 16:00 UTC. `main.py` checks which of the
two lines up with 8am Portland time that day and only that one sends. The
check uses the scheduled time, not the clock, so a run GitHub starts 40
minutes late still goes out.

If every source fails, the job exits with an error instead of sending an
empty email, and GitHub emails you about the failed run.

## Adding a source

Write a module in `sources/` with a `fetch(settings, window)` function that
returns a list of `Event`, then add it to `SOURCES` in `sources/__init__.py`.
Dedupe, ranking and layout pick it up from there. Sources run in parallel
and a failure in one doesn't affect the others.

## Known gaps

- **Other indie theaters.** Laurelhurst Theater, Cinema 21, Academy and
  Clinton Street don't publish showtimes in a form that can be read
  reliably. Hollywood Theatre and the Tomorrow Theater (through the art
  museum) do. Favorite-venue boosts still apply when PDX Pipeline mentions
  one of the others.
- **Checked and left out.** Multnomah County Library (its calendar needs an
  API key it doesn't hand out), Travel Portland and EverOut (no feed),
  Portland'5 (no feed, but its halls are on Ticketmaster and in the venue
  list), and OMSI, Oregon Historical Society and Forest Park Conservancy
  (their sites ask automated readers to stay out, so they're left alone).
- **Wine events past this weekend.** PDX Vine and Dine and PDX Pipeline are
  both weekly, so they only fill Today and This Week. Oregon Wine Board
  covers the weeks after that.
- **Individual tastings.** The Vine and Dine newsletter is written as prose,
  so it appears as one "this weekend in wine" link rather than a line per
  tasting.
- **PDX Pipeline's format.** It's read from their HTML. If they change how
  the roundup is written, `tests/test_sources.py` fails against the saved
  copy in `tests/fixtures/`, and that source goes quiet until it's updated.
- **Yelp.** Its API has an events endpoint that would help here, but Yelp
  now charges $229 a month after a 30-day trial.
