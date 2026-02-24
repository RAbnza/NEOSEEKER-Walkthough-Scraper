# walkthrough-scraper

Scrape a paged Neoseeker walkthrough and export it to a **single PDF** (so you don’t have to keep pressing “Next”).

Important: Neoseeker may show a **security / anti-bot verification** page ("Just a moment..."). This project does **not** bypass that. Instead, you run it in **non-headless** mode, complete verification in the opened browser window, and the tool reuses the saved cookies via a persistent profile directory.

## Requirements

- Windows + Python 3.12+
- Internet access

## Install

From PowerShell:

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m pip install -r requirements.txt
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m playwright install chromium
Pop-Location
```

## Usage

Example (your link):

```powershell
Push-Location "e:/My Files/Personal Projects/walkthough-scraper"
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m walkthrough_scraper `
  --start "https://www.neoseeker.com/the-legend-of-heroes-trails-in-the-sky-the-1st/Prologue" `
  --output "output/trails-in-the-sky-1st.pdf" `
  --max-pages 400 `
  --delay 1.0
Pop-Location
```

If the browser shows a verification page:

1. Complete the verification in the Chromium window.
2. Come back to the terminal and press Enter.

The tool stores cookies in `.profile/` by default.

### Troubleshooting

- If you get stuck on a verification page in headless mode, **do not use `--headless`**.
- If the PDF is missing content, try specifying the main content container:

```powershell
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m walkthrough_scraper --start "..." --output "output/out.pdf" --selector "main"
```

- To debug what’s being rendered, save the combined HTML:

```powershell
& "C:/Users/Rendel Abainza/AppData/Local/Programs/Python/Python312/python.exe" -m walkthrough_scraper --start "..." --output "output/out.pdf" --save-html "output/combined.html"
```

## Notes

- Be polite: keep a delay between pages.
- Use this for personal offline reading. Respect Neoseeker’s terms and copyright.
