from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from playwright.sync_api import Page


_CLOUDFLARE_TITLE_RE = re.compile(r"\bjust a moment\b", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedContent:
    title: str
    content_html: str
    content_selector: str
    text_len: int


def looks_like_bot_challenge(page: Page) -> bool:
    try:
        title = page.title()
    except Exception:
        title = ""
    if _CLOUDFLARE_TITLE_RE.search(title or ""):
        return True

    body_text = ""
    try:
        body_text = page.inner_text("body")
    except Exception:
        return False

    lowered = body_text.lower()
    return (
        "security verification" in lowered
        or "verify you are not a bot" in lowered
        or "checking your browser" in lowered
    )


def walkthrough_prefix(url: str) -> str:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    # Neoseeker walkthrough pages use: /<game-slug>/<page>
    slug = parts[0] if parts else ""
    return f"{parsed.scheme}://{parsed.netloc}/{slug}/" if slug else f"{parsed.scheme}://{parsed.netloc}/"


def extract_main_content(page: Page, *, selector: str | None = None) -> ExtractedContent:
    selectors: Iterable[str] = (
        [selector] if selector else []
    ) + [
        "main",
        "article",
        "[role=main]",
        "#content",
        ".content",
        "#main",
        ".main",
        ".faqtext",
        "#faqtext",
        ".post_content",
        ".entry-content",
    ]

    result = page.evaluate(
        """
(selectors) => {
  const cleanAndAbsolutize = (root) => {
    // Remove noisy bits inside the chosen container.
    root.querySelectorAll('script,style,noscript,nav,footer,header,aside,form,button').forEach(e => e.remove());

    const makeAbs = (attr, el) => {
      const val = el.getAttribute(attr);
      if (!val) return;
      // ignore anchors, mailto, javascript
      if (val.startsWith('#') || val.startsWith('mailto:') || val.startsWith('javascript:')) return;
      try {
        const abs = new URL(val, location.href).href;
        el.setAttribute(attr, abs);
      } catch (_) {
        // ignore
      }
    };

    root.querySelectorAll('[href]').forEach(el => makeAbs('href', el));
    root.querySelectorAll('[src]').forEach(el => makeAbs('src', el));
  };

  const getTitle = () => {
    // prefer in-page h1 when present
    const h1 = document.querySelector('h1');
    const t = (h1?.innerText || '').trim();
    return t || document.title || location.pathname;
  };

  const candidates = [];
  for (const sel of selectors) {
    if (!sel) continue;
    const el = document.querySelector(sel);
    if (!el) continue;
    const text = (el.innerText || '').replace(/\\s+/g,' ').trim();
    candidates.push({ sel, textLen: text.length, el });
  }

  // Fallback: pick the biggest <div> if our selectors all missed.
  if (candidates.length === 0) {
    const divs = Array.from(document.querySelectorAll('div'))
      .map(el => {
        const text = (el.innerText || '').replace(/\\s+/g,' ').trim();
        return { sel: 'div', textLen: text.length, el };
      })
      .sort((a,b) => b.textLen - a.textLen);
    if (divs.length) candidates.push(divs[0]);
  }

  candidates.sort((a,b) => b.textLen - a.textLen);
  const chosen = candidates[0];
  if (!chosen) {
    return { title: getTitle(), html: '', selector: '', textLen: 0 };
  }

  const clone = chosen.el.cloneNode(true);
  cleanAndAbsolutize(clone);
  return {
    title: getTitle(),
    html: clone.innerHTML,
    selector: chosen.sel,
    textLen: chosen.textLen,
  };
}
        """,
        list(selectors),
    )

    return ExtractedContent(
        title=result.get("title", ""),
        content_html=result.get("html", ""),
        content_selector=result.get("selector", ""),
        text_len=int(result.get("textLen", 0) or 0),
    )


def find_next_url(page: Page, *, allowed_prefix: str) -> str | None:
    next_url = page.evaluate(
        """
(allowedPrefix) => {
  const current = location.href;

  const linkTag = document.querySelector('link[rel="next"]');
  if (linkTag?.href && linkTag.href.startsWith(allowedPrefix) && linkTag.href !== current) return linkTag.href;

  const anchors = Array.from(document.querySelectorAll('a[href]'));

  const scoreAnchor = (a) => {
    const href = a.href || '';
    if (!href || !href.startsWith(allowedPrefix) || href === current) return -1e9;

    const text = (a.textContent || '').trim().toLowerCase();
    const aria = ((a.getAttribute('aria-label') || '')).trim().toLowerCase();
    const rel = ((a.getAttribute('rel') || '')).toLowerCase();
    const cls = ((a.getAttribute('class') || '')).toLowerCase();
    const title = ((a.getAttribute('title') || '')).trim().toLowerCase();

    let s = 0;
    if (rel.includes('next')) s += 100;
    if (aria === 'next' || aria.includes('next')) s += 80;
    if (title === 'next' || title.includes('next')) s += 70;
    if (text === 'next') s += 90;
    if (text.includes('next')) s += 60;
    if (['›','»','>','next »','› next'].includes(text)) s += 50;
    if (cls.includes('next')) s += 40;

    // Boost if it's inside a likely pagination container.
    let p = a.parentElement;
    for (let i = 0; i < 4 && p; i++) {
      const pcls = ((p.getAttribute('class') || '')).toLowerCase();
      const pid = ((p.getAttribute('id') || '')).toLowerCase();
      if (pcls.includes('pagination') || pcls.includes('pager') || pcls.includes('nav') || pid.includes('pagination') || pid.includes('pager')) {
        s += 25;
        break;
      }
      p = p.parentElement;
    }

    return s;
  };

  let best = null;
  let bestScore = -1e9;
  for (const a of anchors) {
    const s = scoreAnchor(a);
    if (s > bestScore) {
      bestScore = s;
      best = a;
    }
  }

  if (best && bestScore > 10) return best.href;
  return null;
}
        """,
        allowed_prefix,
    )

    if not next_url or not isinstance(next_url, str):
        return None

    if not next_url.startswith(allowed_prefix):
        return None

    return next_url
