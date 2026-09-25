import probe


def test_finds_schema_org_events_in_a_graph():
    html = """<script type="application/ld+json">
      {"@graph": [{"@type": "WebPage"}, {"@type": "MusicEvent", "name": "A"},
                  {"@type": ["Event", "Thing"], "name": "B"}]}
    </script><script type="application/ld+json">not json</script>"""
    assert probe.event_types(html) == ["MusicEvent", "Event"]


def test_robots_disallow_is_respected():
    from urllib import robotparser
    robots = robotparser.RobotFileParser()
    robots.parse(["User-agent: *", "Disallow: /private/"])
    assert probe.allowed(robots, "https://x.org/events/")
    assert not probe.allowed(robots, "https://x.org/private/list")
    assert probe.allowed(None, "https://x.org/private/list")


def test_ical_links_are_calendar_files_not_words():
    assert probe._ICAL.search("https://x.org/events.ics")
    assert probe._ICAL.search("webcal://x.org/?post_type=tribe_events&ical=1")
    assert not probe._ICAL.search("https://x.org/movie/practical-magic-2")
    assert not probe._ICAL.search("https://x.org/theater/omsi-empirical-theater")
