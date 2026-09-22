"""The header and footer images at the top and bottom of every email.

They're attached to the email itself and referenced by content ID, so
they work from a private repo with nothing to host. To change one, replace
the file in assets/ with another PNG at least 1120 pixels wide (it's shown
at up to 680, and edge to edge on phones). Delete a file to go without
that banner.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ASSETS = Path(__file__).parent.parent / "assets"
DISPLAY_WIDTH = 680  # the email's width; banners run edge to edge across it


@dataclass(frozen=True)
class Banner:
    name: str   # "header" or "footer"
    path: Path
    alt: str

    @property
    def content_id(self) -> str:
        return f"{self.name}@portland-events"


_DEFAULTS = (
    Banner("header", ASSETS / "header.png", "Fun Things to Do in Portland"),
    Banner("footer", ASSETS / "footer.png", "I love you Portland. Have a great day!"),
)


def available() -> list[Banner]:
    return [b for b in _DEFAULTS if b.path.is_file()]


def sources(banners: list[Banner], inline: bool) -> dict[str, dict]:
    """Template values for each banner. `inline` means a real send, where
    the image travels as an attachment; otherwise the local file is used,
    for previews."""
    return {
        b.name: {"src": f"cid:{b.content_id}" if inline else b.path.resolve().as_uri(), "alt": b.alt}
        for b in banners
    }
