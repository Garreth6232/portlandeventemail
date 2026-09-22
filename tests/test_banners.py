from helpers import event
from mailer import banners, render
from mailer.send import build_message, send
from pipeline import assemble


def test_both_banners_ship_with_the_project():
    assert [b.name for b in banners.available()] == ["header", "footer"]


def test_real_send_references_attachments_by_content_id(window, prefs):
    digest = assemble([event("Show", category="Film")], window, prefs)
    html = render.html(digest, "Portland Events", banners.sources(banners.available(), inline=True))
    assert 'src="cid:header@portland-events"' in html
    assert 'src="cid:footer@portland-events"' in html
    assert html.index("cid:header") < html.index(">Show</a>") < html.index("cid:footer")


def test_preview_points_at_local_files(window, prefs):
    html = render.html(assemble([], window, prefs), "Portland Events",
                       banners.sources(banners.available(), inline=False))
    assert "file://" in html and "header.png" in html


def test_without_banners_the_text_title_returns(window, prefs):
    html = render.html(assemble([], window, prefs), "Portland Events")
    assert "cid:" not in html
    assert ">Portland Events</td>" in html


def test_message_structure():
    msg = build_message("me@gmail.com", "Portland Events", "friend@gmail.com", "Tue 9/22: Show",
                        '<img src="cid:header@portland-events">', "plain", banners.available())
    assert msg["From"] == "Portland Events <me@gmail.com>"
    assert msg["To"] == "friend@gmail.com"
    assert msg.get_content_type() == "multipart/alternative"

    plain, related = msg.get_payload()
    assert plain.get_content_type() == "text/plain"
    assert related.get_content_type() == "multipart/related"

    html_part, *images = related.get_payload()
    assert html_part.get_content_type() == "text/html"
    assert [i["Content-ID"] for i in images] == ["<header@portland-events>", "<footer@portland-events>"]
    assert all(i.get_content_type() == "image/png" for i in images)
    assert images[0].get_payload(decode=True)[:8] == b"\x89PNG\r\n\x1a\n"


def test_send_logs_in_and_sends_each_message(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, context, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            calls.append(("login", user, password))

        def send_message(self, msg):
            calls.append(("send", msg["To"]))

    monkeypatch.setattr("mailer.send.smtplib.SMTP_SSL", FakeSMTP)
    msgs = [build_message("me@gmail.com", "x", to, "s", "<p>h</p>", "t") for to in ("a@x.com", "b@x.com")]
    send("smtp.gmail.com", 465, "me@gmail.com", "abcd efgh ijkl mnop", msgs)
    assert calls == [
        ("connect", "smtp.gmail.com", 465),
        ("login", "me@gmail.com", "abcdefghijklmnop"),
        ("send", "a@x.com"),
        ("send", "b@x.com"),
    ]
