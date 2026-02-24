from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urldefrag

from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError

from .assets import localize_assets
from .model import ScrapedPage
from .neoseeker import extract_main_content, find_next_url, looks_like_bot_challenge, walkthrough_prefix
from .pdf import build_combined_html, render_pdf


def _wait_for_settle(page, *, timeout_ms: int = 60_000) -> None:
    """Best-effort wait for page to finish navigating.

    Some sites (and bot-check pages) never reach 'networkidle'.
    """

    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
        return
    except Exception:
        pass

    try:
        page.wait_for_load_state("load", timeout=timeout_ms)
    except Exception:
        pass


def _wait_for_verification_to_clear(page, *, timeout_s: int = 300) -> bool:
    """Poll until the anti-bot verification page is gone."""

    deadline = time.time() + max(1, timeout_s)
    last_title = ""

    while time.time() < deadline:
        try:
            last_title = page.title()
        except Exception:
            last_title = ""

        if not looks_like_bot_challenge(page):
            return True

        remaining = int(deadline - time.time())
        # Keep the output single-line-ish so it feels alive.
        print(f"Waiting for verification to complete... ({remaining}s remaining) [{last_title}]", file=sys.stderr)
        try:
            page.wait_for_timeout(2000)
        except Exception:
            time.sleep(2)

    return not looks_like_bot_challenge(page)


def _normalize_url(url: str) -> str:
    # Strip fragment identifiers so "page#anchor" doesn't become a new crawl target.
    normalized, _frag = urldefrag(url)
    return normalized


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="walkthrough-scraper",
        description="Scrape a Neoseeker walkthrough (paged) into a single PDF.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--start", help="Start URL (first page of the walkthrough)")
    src.add_argument(
        "--urls-file",
        help="Path to a text file containing URLs (one per line) to scrape in order",
    )
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
        "--cdp-url",
        default=None,
        help=(
            "Connect to an existing Chrome instance via the DevTools protocol, e.g. http://127.0.0.1:9222. "
            "This uses your normal browser session/cookies and can reduce verification loops."
        ),
    )
    p.add_argument(
        "--browser",
        choices=["chromium", "chrome"],
        default="chromium",
        help="Browser engine to use. 'chrome' uses your installed Google Chrome (if available).",
    )
    p.add_argument(
        "--headless",
        action="store_true",
        help="Run headless. If you hit anti-bot pages, rerun without --headless.",
    )
    p.add_argument(
        "--verification-timeout",
        type=int,
        default=300,
        help="Seconds to wait for the site's security verification page to clear",
    )
    p.add_argument(
        "--save-html",
        default=None,
        help="Optional path to save the combined HTML before PDF rendering",
    )
    p.add_argument(
        "--offline-assets",
        action="store_true",
        help="Download <img> assets and rewrite to local files before rendering PDF",
    )
    p.add_argument(
        "--assets-dir",
        default=None,
        help="Directory to store downloaded assets (defaults next to the output PDF)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    start_url: str | None = args.start
    output_pdf: str = args.output
    max_pages: int = args.max_pages
    delay_s: float = max(0.0, float(args.delay))
    selector: str | None = args.selector
    profile_dir = str(Path(args.profile_dir).resolve())

    urls: list[str] | None = None
    if args.urls_file:
        urls_path = Path(args.urls_file)
        if not urls_path.exists():
            print(f"URLs file not found: {urls_path}", file=sys.stderr)
            return 2
        raw_lines = urls_path.read_text(encoding="utf-8").splitlines()
        urls = [ln.strip() for ln in raw_lines if ln.strip() and not ln.strip().startswith("#")]
        if not urls:
            print("URLs file is empty.", file=sys.stderr)
            return 2
        start_url = urls[0]

    if not start_url:
        print("Missing --start or --urls-file", file=sys.stderr)
        return 2

    allowed_prefix = walkthrough_prefix(start_url)

    pages: list[ScrapedPage] = []
    visited: set[str] = set()
    bot_challenge_hits = 0

    with sync_playwright() as p:
        if args.cdp_url:
            try:
                browser = p.chromium.connect_over_cdp(args.cdp_url)
            except PlaywrightError as e:
                print(f"Failed to connect to CDP at: {args.cdp_url}", file=sys.stderr)
                print(str(e), file=sys.stderr)
                print(
                    "\nFix checklist:\n"
                    "1) Start Chrome with remote debugging enabled, e.g.:\n"
                    "   & \"$env:ProgramFiles\\Google\\Chrome\\Application\\chrome.exe\" --remote-debugging-port=9222 --user-data-dir \"$env:TEMP\\chrome-cdp-profile\"\n"
                    "2) Keep that Chrome window open while scraping.\n"
                    "3) In a browser, open this to confirm the endpoint is live:\n"
                    "   http://127.0.0.1:9222/json/version\n"
                    "4) If you used a different port (e.g. 9223), pass it in --cdp-url.\n"
                    "5) If you see ECONNREFUSED, Chrome is not listening on that port.",
                    file=sys.stderr,
                )
                return 2
            context = browser.contexts[0] if browser.contexts else browser.new_context()
        else:
            channel = "chrome" if args.browser == "chrome" else None
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=bool(args.headless),
                channel=channel,
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )

        page = context.new_page()
        url = _normalize_url(start_url)
        doc_title = "Neoseeker Walkthrough"

        scrape_list = urls[:max_pages] if urls else None

        def scrape_one(target_url: str, idx: int) -> str | None:
            target_url = _normalize_url(target_url)
            if target_url in visited:
                return None
            visited.add(target_url)

            page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
            _wait_for_settle(page, timeout_ms=60000)

            nonlocal bot_challenge_hits
            if looks_like_bot_challenge(page):
                bot_challenge_hits += 1
                if bot_challenge_hits >= 3:
                    print(
                        "Neoseeker keeps returning a security verification page in this automated browser session.\n"
                        "That usually means the site is blocking automation from your network/device.\n"
                        "This tool will stop here (it does not bypass anti-bot protection).\n"
                        "Suggested fallback: open the pages in your normal browser and Print to PDF per chapter, then merge PDFs with scripts/merge_pdfs.py.",
                        file=sys.stderr,
                    )
                    return 2
                if args.headless:
                    print(
                        "Hit a bot-verification page in headless mode. "
                        "Rerun without --headless so you can complete verification in the browser window.",
                        file=sys.stderr,
                    )
                    return 2

                print(
                    "Neoseeker is showing a security verification page.\n"
                    "A browser window should be open. Complete the verification (it may take 10–30s).\n"
                    "Waiting for it to finish... (press Ctrl+C to stop)",
                    file=sys.stderr,
                )
                # Cloudflare/anti-bot flows often trigger their own redirects.
                # Don't issue a new goto() here; wait for the verification to clear.
                if not _wait_for_verification_to_clear(page, timeout_s=int(args.verification_timeout)):
                    print(
                        "Verification did not clear. You may need to complete additional steps in the browser window (e.g., checkbox/captcha) or try again later.",
                        file=sys.stderr,
                    )
                    return 2

                _wait_for_settle(page, timeout_ms=60000)

            extracted = extract_main_content(page, selector=selector)
            nonlocal doc_title
            if idx == 0 and extracted.title:
                doc_title = extracted.title

            pages.append(ScrapedPage(url=target_url, title=extracted.title or target_url, content_html=extracted.content_html))
            print(f"[{len(pages)}] {extracted.title} ({extracted.text_len} chars) — {target_url}")

            if scrape_list is not None:
                return None

            nxt = find_next_url(page, allowed_prefix=allowed_prefix)
            return _normalize_url(nxt) if nxt else None

        try:
            if scrape_list is not None:
                for idx, target_url in enumerate(scrape_list):
                    scrape_one(target_url, idx)
                    if delay_s:
                        time.sleep(delay_s)
            else:
                for idx in range(max_pages):
                    next_url = scrape_one(url, idx)
                    if not next_url:
                        break
                    url = next_url
                    if delay_s:
                        time.sleep(delay_s)
        except KeyboardInterrupt:
            print("Stopped by user.", file=sys.stderr)
            return 130

        if not pages:
            print("No pages scraped.", file=sys.stderr)
            return 1

        base_href = None if args.offline_assets else "https://www.neoseeker.com/"
        html = build_combined_html(doc_title=doc_title, pages=pages, start_url=start_url, base_href=base_href)

        assets_base_dir: str | None = None
        if args.offline_assets:
            pdf_path = Path(output_pdf)
            default_assets_dir = pdf_path.parent / f"{pdf_path.stem}_assets"
            assets_dir = Path(args.assets_dir) if args.assets_dir else default_assets_dir
            html, downloaded = localize_assets(
                context=context,
                html=html,
                output_dir=str(assets_dir),
                asset_subdir="assets",
                referer_url=start_url,
            )
            print(f"Downloaded {downloaded} assets into: {assets_dir}")
            assets_base_dir = str(assets_dir.resolve())

        if args.save_html:
            html_path = Path(args.save_html)
            html_path.parent.mkdir(parents=True, exist_ok=True)
            html_path.write_text(html, encoding="utf-8")

        render_pdf(context=context, html=html, output_pdf=output_pdf, content_base_dir=assets_base_dir)
        # Only close persistent contexts that we launched; for CDP we leave the user's browser alone.
        if not args.cdp_url:
            context.close()

    print(f"Wrote PDF: {output_pdf}")
    return 0
