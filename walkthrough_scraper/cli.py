from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from .model import ScrapedPage
from .neoseeker import extract_main_content, find_next_url, looks_like_bot_challenge, walkthrough_prefix
from .pdf import build_combined_html, render_pdf


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="walkthrough-scraper",
        description="Scrape a Neoseeker walkthrough (paged) into a single PDF.",
    )
    p.add_argument("--start", required=True, help="Start URL (first page of the walkthrough)")
    p.add_argument("--output", required=True, help="Output PDF path")
    p.add_argument("--max-pages", type=int, default=300, help="Safety cap to avoid infinite loops")
    p.add_argument("--delay", type=float, default=1.0, help="Delay (seconds) between pages")
    p.add_argument(
        "--selector",
        default=None,
        help="Optional CSS selector for the main content container (advanced)",
    )
    p.add_argument(
        "--profile-dir",
        default=str(Path(".profile").resolve()),
        help="Chromium user-data dir (keeps cookies so you can pass site verification once)",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run headless. If you hit anti-bot pages, rerun without --headless.",
    )
    p.add_argument(
        "--save-html",
        default=None,
        help="Optional path to save the combined HTML before PDF rendering",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    start_url: str = args.start
    output_pdf: str = args.output
    max_pages: int = args.max_pages
    delay_s: float = max(0.0, float(args.delay))
    selector: str | None = args.selector
    profile_dir = str(Path(args.profile_dir).resolve())

    allowed_prefix = walkthrough_prefix(start_url)

    pages: list[ScrapedPage] = []
    visited: set[str] = set()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=bool(args.headless),
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        page = context.new_page()
        url = start_url
        doc_title = "Neoseeker Walkthrough"

        for idx in range(max_pages):
            if url in visited:
                break
            visited.add(url)

            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)

            if looks_like_bot_challenge(page):
                if args.headless:
                    print(
                        "Hit a bot-verification page in headless mode. "
                        "Rerun without --headless so you can complete verification in the browser window.",
                        file=sys.stderr,
                    )
                    return 2

                print(
                    "Neoseeker is showing a security verification page.\n"
                    "A Chromium window should be open. Complete the verification, then press Enter here to continue...",
                    file=sys.stderr,
                )
                try:
                    input()
                except KeyboardInterrupt:
                    return 130

                page.goto(url, wait_until="networkidle", timeout=60000)

                if looks_like_bot_challenge(page):
                    print("Still on verification page; stopping.", file=sys.stderr)
                    return 2

            extracted = extract_main_content(page, selector=selector)
            if idx == 0 and extracted.title:
                doc_title = extracted.title

            pages.append(ScrapedPage(url=url, title=extracted.title or url, content_html=extracted.content_html))
            print(f"[{len(pages)}] {extracted.title} ({extracted.text_len} chars) — {url}")

            next_url = find_next_url(page, allowed_prefix=allowed_prefix)
            if not next_url:
                break

            url = next_url
            if delay_s:
                time.sleep(delay_s)

        if not pages:
            print("No pages scraped.", file=sys.stderr)
            return 1

        html = build_combined_html(doc_title=doc_title, pages=pages, start_url=start_url)

        if args.save_html:
            html_path = Path(args.save_html)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")

        render_pdf(context=context, html=html, output_pdf=output_pdf)
        context.close()

    print(f"Wrote PDF: {output_pdf}")
    return 0
