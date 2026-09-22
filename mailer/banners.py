"""The header and footer images at the top and bottom of every email.

They're attached to the email itself and referenced by content ID, so
they work from a private repo with nothing to host. To change one, replace
the file in assets/ with another PNG at least 1120 pixels wide (it's shown
at up to 680, and edge to edge on phones). Delete a file to go without
that banner.

The header can follow the weather. If assets/ has a file named for the
day's condition, that one is used instead of header.png:

    header-sunny.png   header-cloudy.png   header-rainy.png
    header-snowy.png   header-stormy.png

Any that don't exist fall back to header.png.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ASSETS = Path(__file__).parent.parent / "assets"
DISPLAY_WIDTH = 680  # the email's width; banners run edge to edge across it

HEADER_ALT = "Fun Things to Do in Portland"
FOOTER_ALT = "I love you Portland. Have a great day!"


@dataclass(frozen=True)
class Banner:
    name: str   # "header" or "footer"
    path: Path
    alt: str

    @property
    def content_id(self) -> str:
        return f"{self.name}@portland-events"


def available(condition: Optional[str] = None, assets: Path = ASSETS) -> list[Banner]:
    header = assets / "header.png"
    if condition and (assets / f"header-{condition}.png").is_file():
        header = assets / f"header-{condition}.png"
    candidates = (
        Banner("header", header, HEADER_ALT),
        Banner("footer", assets / "footer.png", FOOTER_ALT),
    )
    return [b for b in candidates if b.path.is_file()]


def sources(banners: list[Banner], inline: bool) -> dict[str, dict]:
    """Template values for each banner. `inline` means a real send, where
    the image travels as an attachment; otherwise the local file is used,
    for previews."""
    return {
        b.name: {"src": f"cid:{b.content_id}" if inline else b.path.resolve().as_uri(), "alt": b.alt}
        for b in banners
    }
