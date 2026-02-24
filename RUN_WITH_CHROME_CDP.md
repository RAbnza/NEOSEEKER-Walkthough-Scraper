# Run using your real Chrome session (CDP attach)

This guide shows how to run the scraper by attaching to a real Google Chrome instance via the Chrome DevTools Protocol (CDP).

Why this might helps:
- Some sites may repeatedly show a security verification page in automated browser profiles.
- Attaching to your Chrome lets you complete verification in the UI, and then the scraper uses the same session for paging + PDF.

This does not bypass anti-bot protections. It just uses an already-verified browser session.

## Prereqs

- Complete the Install steps in [README.md](README.md)

## Recommended: use the menu (easiest)

The menu script walks you through killing Chrome, starting CDP Chrome, testing CDP, and running the scraper.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1
```

Optional: pass defaults (handy for quick tests):

```powershell
Set-ExecutionPolicy -Scope Process Bypass
& .\scripts\walkthrough_menu.ps1 -DefaultCdpPort 9222 -DefaultMaxPages 400
```

## Manual: step-by-step

### 1) Stop all existing Chrome processes (recommended)

Chrome can keep background processes running and may ignore new flags like `--remote-debugging-port`.

```powershell
Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process chrome -ErrorAction SilentlyContinue
```

(No output from the second command is good.)

### 2) Start Chrome with CDP enabled

Copy/paste block (recommended):

```powershell
$chromeExe = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$profileDir = Join-Path $env:TEMP "chrome-cdp-profile"
New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
Start-Process -FilePath $chromeExe -ArgumentList @("--remote-debugging-port=9222","--user-data-dir=$profileDir")
Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:9222/json/version" | Select-Object -ExpandProperty Content
```

If that prints JSON, CDP is live.

If Chrome is installed elsewhere, try:
- `"$env:ProgramFiles(x86)\Google\Chrome\Application\chrome.exe"`

### 3) In that Chrome window, open the walkthrough and complete verification

Open:
- https://www.neoseeker.com/the-legend-of-heroes-trails-in-the-sky-the-1st/Prologue

Wait for / complete any prompts until you can see the actual walkthrough content.
Leave that Chrome window open.

### 4) Run the scraper attached to that Chrome

In a second PowerShell window:

```powershell
py -3.12 -m walkthrough_scraper `
  --cdp-url "http://127.0.0.1:9222" `
  --start "https://www.neoseeker.com/the-legend-of-heroes-trails-in-the-sky-the-1st/Prologue" `
  --output "output/trails-in-the-sky-1st.pdf" `
  --offline-assets `
  --max-pages 400 `
  --delay 1.0
```

Notes:
- `--offline-assets` downloads images before PDF generation.
- `--delay 1.0` is polite and reduces the chance of getting rate-limited.

### 5) Check the output

PDF:
- `output/trails-in-the-sky-1st.pdf`

Assets (offline mode):
- `output/trails-in-the-sky-1st_assets/assets/`

## Troubleshooting

### “Cannot connect” / CDP connection errors

- Make sure Chrome was started with `--remote-debugging-port=9222`.
- Verify the endpoint opens in a browser:
  - http://127.0.0.1:9222
  - http://127.0.0.1:9222/json/version

You can also check if Windows has something listening on the port:

```powershell
Get-NetTCPConnection -LocalPort 9222 -ErrorAction SilentlyContinue | Format-Table -AutoSize
```

If that page doesn’t load, the scraper cannot attach.

### “Port 9222 already in use”

Another Chrome (or another tool) is already using that port.

Fix options:
1. Close all Chrome windows and try again.
2. Use a different port, e.g. 9223:

Start Chrome:
```powershell
& "$env:ProgramFiles\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir "$env:TEMP\chrome-cdp-profile"
```

Run scraper:
```powershell
py -3.12 -m walkthrough_scraper --cdp-url "http://127.0.0.1:9223" --start "..." --output "output/out.pdf"
```

### Verification still loops even in real Chrome

That usually means the site is blocking scripted navigation from your environment.
The tool will stop after a few repeated verification hits.

What you can try (non-bypass):
- Increase delay: `--delay 2.0`
- Reduce speed: lower `--max-pages`, run smaller chunks.
- Run during off-peak hours.

### Stop the scraper

Press `Ctrl+C` in the terminal running the scraper.

---

## Safety note

Running Chrome with remote debugging enabled exposes a local debugging endpoint.
- Only use `127.0.0.1` (local machine).
- Don’t leave it running longer than needed.
- Close the special Chrome instance when done.
