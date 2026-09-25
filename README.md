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
| PDX Movie Times | Showtimes at Hollywood, Laurelhurst, Cinema 21, Academy, Living Room and other indie theaters | No |
| Hollywood Theatre | Every screening, from the theater's own site (currently refuses GitHub's servers; PDX Movie Times covers it) | No |
| Portland Art Museum | Exhibitions, talks, and PAM CUT screenings at the Tomorrow Theater | No |
| Clinton Street Theater | Cult, indie and repertory film, plus drag, music and comedy nights | No |
| Literary Arts | Readings, author talks, Portland Arts & Lectures | No |
| PDX Pipeline | The weekday and weekend roundups: bars, trivia, happy hours, small shows | No |
| PDX Vine and Dine | The weekly wine tasting roundup, as one listing | No |
| Oregon Wine Board | Tastings and winemaker dinners in Portland and the north Willamette Valley | No |
| Portland Farmers Market | Every market day across the city | No |
| Portland Parks & Recreation | Park events, movies and concerts in the parks | No |
| Lan Su Chinese Garden | Festivals, performances, and garden events | No |
| Pioneer Courthouse Square | Free concerts, watch parties, and downtown happenings | No |
| Ticketmaster | Shows at the venues listed in `preferences.toml` | Free |
| SeatGeek | The same, and a cross-check on Ticketmaster | Free |

The art museum, Clinton Street, Literary Arts, the Wine Board, the
Farmers Market, Lan Su and Pioneer Courthouse Square all run the same
WordPress calendar plugin, so they share one connector
(`sources/events_calendar.py`) and are listed under `[[calendars]]` in
`preferences.toml`. Adding another site that uses it is four lines there.

PDX Movie Times gathers every indie theater's showtimes into one page a
day. Only the theaters under `[movie_times]` in `preferences.toml` are
kept, which leaves out first-run houses like Studio One and Kennedy School.
Each film shows up once, at its next showing, with the rest of its run
noted.

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

After that it sends every weekday around 8am. To see the email without sending
it to anyone, run the workflow with "Preview only" checked; the finished
email is attached to the run as a download called `preview`.

Gmail allows a personal account about 500 recipients a day, so four people
is nowhere near the limit.

## Changing what shows up

The subject line rotates through the list under `[subject]` in
`preferences.toml`, one per day, with set lines for Mondays and Fridays.
Add, remove or reword them there. `{date}` becomes "Tuesday, Sep 22" and
`{weekday}` becomes "Tuesday".

Everything about taste lives in `preferences.toml`: category weights,
keyword boosts ("35mm", "natural wine"), favorite venues, which venues
Ticketmaster and SeatGeek can list from, the calendar sites, section sizes
(8 today, 12 this week, 12 coming up), how many per category and venue,
the top pick rotation, and where
the search is centered. Edit it, push, and the next email reflects it.

How an event's score works: its category weight, plus the largest keyword
boost it matches, plus a bump if the venue is a favorite, plus a little
more for each extra source that lists it, minus a penalty if it has five
or more dates in the next month. Film and music sit at a neutral weight,
because there's always a lot of both; the special ones (a 35mm print, a
Q&A, a live score, a one-night show) rise through the keyword boosts, and
a film's regular run or a weekly trivia night sinks under the long-run
penalty. A category a source made up ("Karaoke", "Workshop") keeps its
label in the email but ranks as "other". On a tie, a one-time event beats
one that repeats, then the sooner one wins.

Each section holds at most two listings per category and two per venue,
and one arena show, before filling any leftover seats with the next best.

The "Top pick" takes turns by category: one step a day through the list
under `[top_pick]`, with each section starting at a different point, so
the three picks in an email differ and tomorrow's differ from today's.
It's the best listing shown in that day's category, or the next category
down the list if the section has none.

Preview runs (Actions > Send digest > "Preview only") log each section's
choices with their scores broken down, and how many candidates each
category had, which is the quickest way to see what a change to
`preferences.toml` does.

The rest aren't dropped. "Plus 23 more this week" links to a plain
one-line-each list at the bottom of the email, grouped by day. Gmail hides
anything past about 102KB behind "View entire message", so on a very full
day the far end of Coming Up is cut short to keep the email under that.

## Weather

A small line under the date gives the day's forecast in three parts, for
example "Morning 61°, cloudy · Afternoon 69°, partly cloudy · Tonight 63°,
mostly clear". Afternoon is the high; morning and tonight are averages. A
rain chance of 30% or more gets mentioned, and so does wind. The forecast comes from
[Open-Meteo](https://open-meteo.com), which is free and needs no key. If it
can't be reached, the email goes out without the line.

## Header and footer images

`assets/header.png` sits at the top of every email and `assets/footer.png`
at the bottom. They're attached to each email rather than linked, so they
work from a private repo and don't need hosting anywhere.

To change one, replace the file with another PNG of the same name, at
least 1120 pixels wide. It's shown up to 680 wide on a computer and edge
to edge on a phone. Any height works. Delete a file to go without it.
With no header, the email falls back to its name in text.

The header changes with the weather. `[headers]` in `preferences.toml`
says which image in `assets/` goes with which kind of day:

| Weather | When |
| --- | --- |
| stormy | any thunder |
| snowy | a couple of hours of snow |
| rainy | a couple of hours of rain, or a 60%+ chance |
| windy | gusts of 30+ mph or steady wind of 18+ mph for a couple of hours |
| cloudy | mostly overcast, or fog |
| sunny | mostly clear skies |
| normal | anything else: some sun, some cloud, nothing notable |

The first that fits wins, top to bottom. List more than one image for a
kind of day and they take turns. Anything missing falls back to
`header.png`.

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

GitHub starts scheduled jobs late, often by three or four hours, and runs
set for the top of the hour are the worst hit. A single 8am run therefore
tends to arrive around lunchtime. So the workflow tries every half hour
from about 3am to noon Pacific, at :07 and :37 past the hour, and
`main.py` sends from the first run that starts between 7:45am and noon on
a weekday. Once that run sends, it leaves a marker in the Actions cache
for the day, and every later run that day sees it and stops. If GitHub's delay
holds steady through the morning, the email lands between 7:45 and 8:15, and the retries cover GitHub skipping
a run.

Change the window with `SEND_FROM` and `SEND_UNTIL` in `config.py`.

Each check that doesn't send still costs a billed minute on a private
repo, about 20 a weekday or 450 a month. The free plan includes 2,000.

A manual run with "Send now" also marks the day as sent, so the morning
runs won't send it again. "Only me" and "Preview only" don't.

If every source fails, the job exits with an error instead of sending an
empty email, and GitHub emails you about the failed run.

## Adding a source

To check whether a site can be read before writing anything, add it to
`CANDIDATES` in `probe.py` and run Actions > Probe sources. It tries each
site from GitHub's servers (some sites answer a laptop but block GitHub),
respects robots.txt, and lists what it found on the run's summary page:
an Events Calendar feed, schema.org event data, RSS, iCal links, and which
ticketing site the venue sells through.


Write a module in `sources/` with a `fetch(settings, window)` function that
returns a list of `Event`, then add it to `SOURCES` in `sources/__init__.py`.
Dedupe, ranking and layout pick it up from there. Sources run in parallel
and a failure in one doesn't affect the others.

## Known gaps

- **Hollywood Theatre, PDX Vine and Dine, Oregon Wine Board.** All three
  refuse requests from GitHub's servers. Hollywood's showtimes still come
  in through PDX Movie Times; the two wine sources don't. Running the job
  from somewhere other than GitHub (a home machine, a small server) would
  bring them back.
- **Small music rooms.** Mississippi Studios, Revolution Hall, Polaris
  Hall, the Aladdin and Holocene sell through Etix, which has no public
  feed, and their own sites don't publish their calendars in a readable
  form. Ones that also list on Ticketmaster or SeatGeek show up there.
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
