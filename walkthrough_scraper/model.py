from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    title: str
    content_html: str
