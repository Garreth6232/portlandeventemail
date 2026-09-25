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
