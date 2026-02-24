# NEOSEEKER: Walkthrough-Scraper

I made this app so I wouldn’t have to keep clicking “Next” every time I read a walkthrough on Neoseeker. It automatically crawls paged walkthroughs (Neoseeker-style “Next” pages) and exports everything into a single PDF, so you can read everything in one go. (Yes, I am that lazy lol)

Note: some sites may show a security verification page. This project does not bypass anti-bot protections. The best automated approach is to attach to your already-verified Chrome session.

## Requirements

- Windows
- Python 3.12+
- Internet access

## Install

From PowerShell (run in the repo root):

```powershell
# Recommended on Windows (py launcher)
py -3.12 -m pip install -r requirements.txt
py -3.12 -m playwright install chromium
```

If you don’t have the `py` launcher, try:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
```

## Run (recommended: menu interface)

This opens a small PowerShell menu to:
- stop Chrome
- start CDP Chrome
- test CDP
- run the scraper
- exit

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1
```

Optional defaults:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1 -DefaultCdpPort 9222 -DefaultMaxPages 400
```

The detailed “attach to Chrome (CDP)” walkthrough is in [RUN_WITH_CHROME_CDP.md](RUN_WITH_CHROME_CDP.md).

## Advanced (CLI)

Show options:

```powershell
py -3.12 -m walkthrough_scraper --help
```

Useful flags:
- `--offline-assets` downloads images so the PDF renders more reliably.
- `--urls-file urls.txt` uses an explicit list of URLs (one per line) instead of clicking Next.
- `--save-html output/combined.html` writes the combined HTML for debugging.

## Troubleshooting

- If you get `PermissionError` writing the PDF, close the PDF viewer (Windows locks open PDFs).
- If you see repeated verification pages, use the CDP method in [RUN_WITH_CHROME_CDP.md](RUN_WITH_CHROME_CDP.md).
- If the menu exits immediately, run diagnostics:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1 -Diagnostics
```
