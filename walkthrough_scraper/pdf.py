from __future__ import annotations

from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext

from .model import ScrapedPage


def build_combined_html(*, doc_title: str, pages: list[ScrapedPage], start_url: str) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    sections = []
    for i, p in enumerate(pages, start=1):
        sections.append(
            "\n".join(
                [
                    '<section class="page">',
                    f"<h1>{_escape(p.title)}</h1>",
                    f"<div class=\"meta\">{i}/{len(pages)} • <a href=\"{_escape_attr(p.url)}\">{_escape(p.url)}</a></div>",
                    f"<div class=\"content\">{p.content_html}</div>",
                    "</section>",
                ]
            )
        )

    css = """
:root { --text: #111; --muted: #555; --link: #1a56db; }
@page { margin: 18mm 14mm; }
* { box-sizing: border-box; }
body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; color: var(--text); line-height: 1.45; }
a { color: var(--link); text-decoration: none; }
a:hover { text-decoration: underline; }
.cover { margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid #ddd; }
.cover h1 { font-size: 26px; margin: 0 0 6px 0; }
.cover .meta { color: var(--muted); font-size: 12px; }
.page { page-break-before: always; }
.page h1 { font-size: 22px; margin: 0 0 6px 0; }
.meta { color: var(--muted); font-size: 11px; margin-bottom: 10px; }
.content img { max-width: 100%; height: auto; }
.content pre, .content code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace; font-size: 12px; }
.content pre { white-space: pre-wrap; background: #f6f6f6; padding: 10px; border-radius: 6px; }
.content table { border-collapse: collapse; width: 100%; }
.content th, .content td { border: 1px solid #ddd; padding: 6px; vertical-align: top; }
"""

    # A <base> tag helps relative URLs inside captured HTML resolve.
    base = "https://www.neoseeker.com/"

    return "\n".join(
        [
            "<!doctype html>",
            "<html>",
            "<head>",
            "<meta charset=\"utf-8\">",
            f"<base href=\"{base}\">",
            f"<title>{_escape(doc_title)}</title>",
            f"<style>{css}</style>",
            "</head>",
            "<body>",
            "<section class=\"cover\">",
            f"<h1>{_escape(doc_title)}</h1>",
            f"<div class=\"meta\">Generated {generated_at} • Start: <a href=\"{_escape_attr(start_url)}\">{_escape(start_url)}</a></div>",
            "</section>",
            *sections,
            "</body>",
            "</html>",
        ]
    )


def render_pdf(*, context: BrowserContext, html: str, output_pdf: str) -> None:
    out_path = Path(output_pdf)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    page = context.new_page()
    page.set_content(html, wait_until="networkidle")
    page.emulate_media(media="print")
    page.pdf(
        path=str(out_path),
        format="Letter",
        print_background=True,
        margin={"top": "18mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
    )
    page.close()


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _escape_attr(s: str) -> str:
    return _escape(s)
