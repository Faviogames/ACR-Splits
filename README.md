# ACR Splits

Windows client for [acrsplits.online](https://acrsplits.online), community records for unofficial Assetto Corsa Rally stages.

## Install

Download **ACR-Splits-Setup.exe** from [the latest release](https://github.com/Faviogames/ACR-Splits/releases/latest).
Run it as your normal Windows user. It extracts to `%LOCALAPPDATA%\ACRSplits`, adds **ACR Splits** to the Start menu and opens the app. No Stage Exporter or Python installation is required. Windows x64; Microsoft Edge WebView2 Runtime is required (normally included on Windows 11; obtain missing runtime only from https://developer.microsoft.com/microsoft-edge/webview2/).

The installer is currently unsigned: Windows SmartScreen may show an unknown publisher warning.

## Updates

Use the **ACR Splits** Start-menu shortcut. Each launch checks this repository's latest stable GitHub release. A newer installer is downloaded automatically from this fixed repository, verified against GitHub's SHA-256 asset digest and applied before the client starts. Without Internet or if verification fails, the installed version starts and the failure is recorded in `%LOCALAPPDATA%\ACRSplits\update.log`.

Versions are stored in `versions/`; settings, encrypted Discord session and captures are stored separately in `data/`. Updates preserve this directory. Existing Stage Exporter installs keep their original data; this installer does not copy or publish it automatically. Do not launch the executable inside `versions/` directly: that bypasses update checks. Old versions are retained; automatic disk cleanup is not implemented.

## Record

Open the app before starting the stage. Capture starts automatically when the stage clock advances. Leave the result screen so the game saves its official stage, car, raw time and penalties. Sign in with Discord, choose your permanent pilot name and confirm the upload. Capture reads game telemetry and saves; it never modifies them. Upload is user-confirmed, not automatic. Private compact traces support server-side plausibility checks; this is not game anti-cheat attestation.

## Build

.NET SDK 10 and PowerShell on Windows x64:

1. Download the official Python 3.14.0 embeddable Windows x64 archive from https://www.python.org/ftp/python/3.14.0/python-3.14.0-embed-amd64.zip to `records/build-tools/python-3.14.0-embed-amd64.zip`.
2. Run `./records/build_desktop.ps1`.
3. Run `records/dist/ACR-Splits-Setup.exe --self-test <absolute-report-path.json>` and check `result: PASS`. This extracts in a temporary directory, rejects unsafe ZIP paths, verifies idempotence and data preservation, and imports the standalone Python/TLS runtime and 25-stage catalogue.
4. Run `python -m records.test_online` for authentication/DPAPI checks.

Output: `records/dist/ACR-Splits-Setup.exe` and `SHA256SUMS.txt`.

For each new release, increase the version in installer/Program.cs (ReleaseVersion), installer/Installer.csproj, build_desktop.ps1, app.py and ui/index.html. Publish a stable `vX.Y.Z` release with the installer named **ACR-Splits-Setup.exe** and SHA256SUMS.txt. GitHub must provide the asset's SHA-256 `digest` or clients refuse the update. Never replace a published release asset in place. The first release cannot prove an upgrade from a previous public version; test that separately before the next release.

Only client sources and the stage-name catalogue are included. No game assets, save files, captured traces, sessions, backend secrets or exporter binaries are distributed. .NET, Python and WebView2 components retain their respective licenses. This is an independent community project, not affiliated with the game developer.
