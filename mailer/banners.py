"""The header and footer images at the top and bottom of every email.

They're attached to the email itself and referenced by content ID, so
they work from a private repo with nothing to host. Images live in
assets/, at least 1120 pixels wide (shown at up to 680, and edge to edge
on phones).

Which header goes out depends on the day's weather; [headers] in
preferences.toml maps each kind of weather to one or more images in
assets/. With more than one, they take turns day by day. Anything missing
falls back to header.png.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping, Optional, Sequence

ASSETS = Path(__file__).parent.parent / "assets"
DISPLAY_WIDTH = 680  # the email's width; banners run edge to edge across it
DEFAULT_HEADER = "header.png"

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


def _find(assets: Path, name: str) -> Optional[Path]:
    """The file in assets/ with this name, ignoring upper/lower case, since
    "Header.PNG" and "header.png" are different files on GitHub's servers."""
    exact = assets / name
    if exact.is_file():
        return exact
    if assets.is_dir():
        wanted = name.lower()
        return next((p for p in assets.iterdir() if p.name.lower() == wanted and p.is_file()), None)
    return None


def header_for(condition: Optional[str], day: date, headers: Mapping[str, Sequence[str]],
               assets: Path = ASSETS) -> str:
    """The header file for this kind of weather. Several choices rotate by
    date, so the same day always gets the same one."""
    choices = [found.name for f in headers.get(condition or "normal", ()) if (found := _find(assets, f))]
    if not choices:
        return DEFAULT_HEADER
    return choices[day.toordinal() % len(choices)]


def available(header: str = DEFAULT_HEADER, assets: Path = ASSETS) -> list[Banner]:
    path = _find(assets, header) or assets / DEFAULT_HEADER
    candidates = (
        Banner("header", path, HEADER_ALT),
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
