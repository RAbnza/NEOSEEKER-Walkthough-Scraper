from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
import re
from typing import Iterable
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import BrowserContext


def localize_assets(
    *,
    context: BrowserContext,
    html: str,
    output_dir: str,
    asset_subdir: str = "assets",
    url_allowlist_prefixes: Iterable[str] = ("http://", "https://"),
    referer_url: str | None = None,
) -> tuple[str, int]:
    """Download images referenced by HTML and rewrite to local paths.

    This makes the combined HTML (and resulting PDF) usable offline.

    Only rewrites <img src="..."> for http(s) URLs.
    """

    out_dir = Path(output_dir)
    assets_dir = out_dir / asset_subdir
    assets_dir.mkdir(parents=True, exist_ok=True)

    soup = BeautifulSoup(html, "lxml")

    downloaded = 0
    seen: dict[str, str] = {}

    for img in soup.find_all("img"):
        src = _best_image_url(img)
        if not src:
            continue
        if src.startswith("data:"):
            continue
        if not any(src.startswith(p) for p in url_allowlist_prefixes):
            continue

        # Avoid re-downloading duplicates.
        if src in seen:
            _rewrite_img(img, seen[src])
            continue

        local_rel = _download_to_assets(
            context=context,
            url=src,
            assets_dir=assets_dir,
            referer_url=referer_url,
        )
        if not local_rel:
            continue

        _rewrite_img(img, local_rel)
        seen[src] = local_rel
        downloaded += 1

    # Inline CSS background-image: url(...)
    for el in soup.find_all(style=True):
        style = (el.get("style") or "")
        if "url(" not in style:
            continue
        new_style, count = _rewrite_inline_style_urls(
            context=context,
            style=style,
            assets_dir=assets_dir,
            seen=seen,
            url_allowlist_prefixes=url_allowlist_prefixes,
            referer_url=referer_url,
        )
        if count:
            el["style"] = new_style
            downloaded += count

    return str(soup), downloaded


def _download_to_assets(
    *,
    context: BrowserContext,
    url: str,
    assets_dir: Path,
    referer_url: str | None = None,
) -> str | None:
    try:
        headers = {}
        if referer_url:
            headers["Referer"] = referer_url
        resp = context.request.get(url, timeout=60_000, headers=headers or None)
    except Exception:
        return None

    try:
        if not resp.ok:
            return None

        body = resp.body()
        if not body:
            return None

        content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
        ext = _choose_extension(url=url, content_type=content_type)

        name = _safe_name(url, ext)
        local_path = assets_dir / name
        local_path.write_bytes(body)

        # Use a relative path that survives HTML parsing and PDF rendering.
        return f"{assets_dir.name}/{name}"
    finally:
        resp.dispose()


_SRCSET_SPLIT_RE = re.compile(r"\s*,\s*")
_SRCSET_PART_RE = re.compile(r"^\s*(\S+)\s*(\d+(?:\.\d+)?)([wx])?\s*$")


def _best_image_url(img) -> str | None:
    """Choose the best URL for an <img>, including lazy-load and srcset."""

    # Common lazy-load attributes
    for key in (
        "data-src",
        "data-original",
        "data-lazy-src",
        "data-echo",
        "data-url",
    ):
        val = (img.get(key) or "").strip()
        if val:
            return val

    # srcset (or lazy srcset)
    srcset = (img.get("srcset") or img.get("data-srcset") or "").strip()
    best = _pick_best_from_srcset(srcset)
    if best:
        return best

    src = (img.get("src") or "").strip()
    if src and not _looks_like_placeholder(src):
        return src

    # Fallback: if src is placeholder, try srcset anyway
    if srcset:
        return _pick_best_from_srcset(srcset)

    return src or None


def _pick_best_from_srcset(srcset: str) -> str | None:
    if not srcset:
        return None

    candidates: list[tuple[float, str]] = []
    for part in _SRCSET_SPLIT_RE.split(srcset):
        part = part.strip()
        if not part:
            continue

        # Typical format: "url 2x" or "url 640w"
        pieces = part.split()
        url = pieces[0]
        score = 0.0
        if len(pieces) >= 2:
            m = _SRCSET_PART_RE.match(" ".join(pieces))
            if m:
                try:
                    score = float(m.group(2))
                    if (m.group(3) or "").lower() == "w":
                        score = score / 1000.0  # normalize widths a bit
                except Exception:
                    score = 0.0

        candidates.append((score, url))

    if not candidates:
        return None

    # Prefer highest score; ties keep later entries.
    candidates.sort(key=lambda t: t[0])
    return candidates[-1][1]


def _looks_like_placeholder(src: str) -> bool:
    lowered = src.lower()
    return (
        lowered.startswith("data:image/gif")
        or "1x1" in lowered
        or "spacer" in lowered
        or lowered.endswith("/pixel")
    )


def _rewrite_img(img, local_rel: str) -> None:
    img["src"] = local_rel
    # Remove srcset variants so Chromium doesn't try to fetch remote URLs.
    for key in (
        "srcset",
        "data-srcset",
        "data-src",
        "data-original",
        "data-lazy-src",
        "data-echo",
        "data-url",
    ):
        if key in img.attrs:
            del img.attrs[key]


_INLINE_URL_RE = re.compile(r"url\((?P<q>['\"]?)(?P<u>.*?)(?P=q)\)", re.IGNORECASE)


def _rewrite_inline_style_urls(
    *,
    context: BrowserContext,
    style: str,
    assets_dir: Path,
    seen: dict[str, str],
    url_allowlist_prefixes: Iterable[str],
    referer_url: str | None,
) -> tuple[str, int]:
    count = 0

    def repl(m: re.Match[str]) -> str:
        nonlocal count
        u = (m.group("u") or "").strip()
        if not u or u.startswith("data:"):
            return m.group(0)
        if not any(u.startswith(p) for p in url_allowlist_prefixes):
            return m.group(0)

        if u in seen:
            return f"url('{seen[u]}')"

        local_rel = _download_to_assets(
            context=context,
            url=u,
            assets_dir=assets_dir,
            referer_url=referer_url,
        )
        if not local_rel:
            return m.group(0)

        seen[u] = local_rel
        count += 1
        return f"url('{local_rel}')"

    new_style = _INLINE_URL_RE.sub(repl, style)
    return new_style, count


def _choose_extension(*, url: str, content_type: str) -> str:
    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix
    if suffix and len(suffix) <= 10:
        return suffix

    if content_type:
        guessed = mimetypes.guess_extension(content_type)
        if guessed:
            return guessed

    return ".bin"


def _safe_name(url: str, ext: str) -> str:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    clean_ext = ext if ext.startswith(".") else f".{ext}"
    return f"asset-{h}{clean_ext}"
