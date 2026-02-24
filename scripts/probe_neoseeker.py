from __future__ import annotations

import json

from playwright.sync_api import sync_playwright

URL = "https://www.neoseeker.com/the-legend-of-heroes-trails-in-the-sky-the-1st/Prologue"


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(URL, wait_until="networkidle", timeout=60000)

        candidates = page.evaluate(
            """
() => {
  const selectors = [
    'link[rel="next"]',
    'a[rel="next"]',
    'a:has-text("Next")',
    'a:has-text("NEXT")',
    'a:has-text(">")',
    'a:has-text("»")',
    'a:has-text("›")',
  ];

  const next = (() => {
    const link = document.querySelector('link[rel="next"]');
    if (link && link.href) return link.href;
    const a = document.querySelector('a[rel="next"]');
    if (a && a.href) return a.href;
    // try visible anchors containing "Next"
    const anchors = Array.from(document.querySelectorAll('a'));
    const nextAnchor = anchors.find(a => (a.textContent || '').trim().toLowerCase() === 'next');
    return nextAnchor?.href || null;
  })();

  const containerSelectors = [
    'main',
    'article',
    '[role="main"]',
    '#content',
    '.content',
    '#main',
    '.main',
    '.faqtext',
    '#faqtext',
    '.post',
    '.post_content',
    '.entry-content',
  ];

  const containers = containerSelectors
    .map(sel => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const text = (el.innerText || '').replace(/\\s+/g,' ').trim();
      return {
        selector: sel,
        textLen: text.length,
        sample: text.slice(0, 200)
      };
    })
    .filter(Boolean)
    .sort((a,b) => b.textLen - a.textLen);

  return { title: document.title, url: location.href, next, containers };
}
            """,
        )

        print(json.dumps(candidates, indent=2))
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
