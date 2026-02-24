from __future__ import annotations

import argparse
from pathlib import Path

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Combine a folder of saved HTML pages into a single PDF (offline).\n"
            "Tip: Save pages from your normal browser to avoid anti-bot automation blocks."
        )
    )
    p.add_argument("--input", required=True, help="Folder containing .html/.htm files")
    p.add_argument("--output", required=True, help="Output PDF path")
    return p


def main() -> int:
    args = build_parser().parse_args()
    in_dir = Path(args.input)
    out_pdf = Path(args.output)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    html_files = sorted(
        [*in_dir.glob("*.html"), *in_dir.glob("*.htm")],
        key=lambda p: p.name.lower(),
    )
    if not html_files:
        raise SystemExit(f"No HTML files found in: {in_dir}")

    sections: list[str] = []
    doc_title = in_dir.name

    for html_path in html_files:
        raw = html_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(raw, "lxml")
        title = (soup.title.string.strip() if soup.title and soup.title.string else html_path.stem)

        body = soup.body
        content_html = body.decode_contents() if body else soup.decode()

        sections.append(
            "\n".join(
                [
                    '<section class="page">',
                    f"<h1>{_escape(title)}</h1>",
                    f"<div class=\"meta\">Source file: {_escape(html_path.name)}</div>",
                    f"<div class=\"content\">{content_html}</div>",
                    "</section>",
                ]
            )
        )

    css = """
@page { margin: 18mm 14mm; }
* { box-sizing: border-box; }
body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; line-height: 1.45; }
.page { page-break-before: always; }
.page h1 { font-size: 22px; margin: 0 0 6px 0; }
.meta { color: #555; font-size: 11px; margin-bottom: 10px; }
.content img { max-width: 100%; height: auto; }
"""

    combined = "\n".join(
        [
            "<!doctype html>",
            "<html>",
            "<head>",
            "<meta charset=\"utf-8\">",
            f"<title>{_escape(doc_title)}</title>",
            f"<style>{css}</style>",
            "</head>",
            "<body>",
            *sections,
            "</body>",
            "</html>",
        ]
    )

    # Render via file:// so relative references (if any) resolve.
    tmp_html = out_pdf.parent / "combined.html"
    tmp_html.write_text(combined, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(tmp_html.as_uri(), wait_until="load")
        page.emulate_media(media="print")
        page.pdf(
            path=str(out_pdf),
            format="Letter",
            print_background=True,
            margin={"top": "18mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
        )
        browser.close()

    print(f"Wrote PDF: {out_pdf}")
    return 0


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


if __name__ == "__main__":
    raise SystemExit(main())
