# NEOSEEKER: Walkthrough-Scraper

I made this app so I wouldn’t have to keep clicking “Next” every time I read a walkthrough on Neoseeker. It automatically crawls paged walkthroughs (Neoseeker-style “Next” pages) and exports everything into a single PDF, so you can read everything in one go. (Yes, I am that lazy lol)

Note: some sites may show a security verification page. This project does not bypass anti-bot protections. The best automated approach is to attach to your already-verified Chrome session.

## Requirements

- Windows
- Python 3.12+
- Internet access

## Install

From PowerShell (run from the repo root):

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"

# Install Python deps
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m pip install -r requirements.txt

# Install Playwright browser
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m playwright install chromium

Pop-Location
```

If your Python is on PATH, you can replace the long Python path with `python`.

## Run (recommended: menu interface)

This opens a small PowerShell menu to:
- stop Chrome
- start CDP Chrome
- test CDP
- run the scraper
- exit

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1
Pop-Location
```

Optional defaults:

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1 -DefaultCdpPort 9222 -DefaultMaxPages 400
Pop-Location
```

The detailed “attach to Chrome (CDP)” walkthrough is in [RUN_WITH_CHROME_CDP.md](RUN_WITH_CHROME_CDP.md).

## Advanced (CLI)

Show options:

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m walkthrough_scraper --help
Pop-Location
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
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
powershell -ExecutionPolicy Bypass -File "scripts/walkthrough_menu.ps1" -Diagnostics
Pop-Location
```
