# ITFlow Quick Ticket (Windows)

A lightweight Windows tray app that lets end users submit an ITFlow support
ticket — with an optional full-screen screenshot — in a few clicks, with no
portal login.

## How it works

1. Runs in the system tray, starting on login.
2. Click the tray icon (or "New Ticket") to open a small popup:
   - Subject
   - Description
   - "Attach Screenshot" (captures the full screen, shows a thumbnail,
     can be retaken or removed)
3. "Submit" posts the ticket to ITFlow via the API, then the window closes
   after a brief success message.

## ITFlow API call

```
POST {itflow_base_url}/api/v1/tickets?api_key={api_key}
Content-Type: multipart/form-data

subject=...
details=...
client_id=...
contact_id=...      (optional)
priority=Medium
file=@screenshot.png (optional)
```

This requires ITFlow **v2.11.32 or later**, which added multipart/form-data
support (with an optional `file`/`files[]` attachment) to ticket creation —
see `agent` repo commit "API: support file attachments on ticket creation,
replies, and unify attachment storage". On older versions, ticket creation
only accepts a JSON body and has no attachment support.

The `api_key` is a **legacy API key** (Admin > API Keys in ITFlow). Note:

- It must be sent as a `?api_key=` query string parameter — for
  multipart/form-data POST bodies, the JSON-body fallback does not apply.
- The legacy key authenticates as the first active admin user (ITFlow does
  not currently scope legacy-key requests to `api_key_client_id`); the
  `client_id` field in `config.json` is what actually assigns the ticket
  to the right client.
- Treat the API key as a shared secret across all machines it's deployed
  to — anyone with it can create tickets for any client via this endpoint.

## Files

- `tray_app.py` — the application (pystray + tkinter + Pillow + requests)
- `config.json` — config template, deployed to
  `%ProgramData%\ITFlowQuickTicket\config.json`
- `itflow_quick_ticket.spec` — PyInstaller spec, produces a single
  windowed `.exe` (no console)
- `requirements.txt` — Python dependencies
- `deploy/deploy_quickticket.ps1` — TacticalRMM deployment script
- `assets/icon.ico` — optional custom tray icon (not included; the app
  falls back to a generated placeholder icon if missing)

## Building

```powershell
pip install -r requirements.txt
pyinstaller itflow_quick_ticket.spec
# Output: dist\ITFlowQuickTicket.exe
```

To brand the tray icon, drop a `.ico` file at `assets/icon.ico` before
building.

## Deploying via TacticalRMM

1. Host `ITFlowQuickTicket.exe` somewhere TacticalRMM can download it from
   (file share, internal URL, etc.).
2. Run `deploy/deploy_quickticket.ps1` as a TacticalRMM script (System
   context) per client, with arguments:

   ```
   -ExeSourceUrl  <url to ITFlowQuickTicket.exe>
   -ItflowBaseUrl https://itflow.foleyit.com
   -ApiKey        <API key from Admin > API Keys>
   -ClientId      <ITFlow client_id for this client>
   -ContactId     <optional ITFlow contact_id>
   -Priority      Medium
   ```

   This installs the exe to `C:\Program Files\ITFlowQuickTicket`, writes
   `C:\ProgramData\ITFlowQuickTicket\config.json`, and adds a shortcut to
   the All Users Startup folder so it launches on every login.

## Config reference (`config.json`)

| Field             | Required | Description                                  |
|-------------------|----------|-----------------------------------------------|
| `itflow_base_url` | yes      | e.g. `https://itflow.foleyit.com`              |
| `api_key`         | yes      | Legacy API key from Admin > API Keys           |
| `client_id`       | yes      | ITFlow `client_id` this install belongs to     |
| `contact_id`      | no       | ITFlow `contact_id` to attach to the ticket    |
| `priority`        | no       | `Low` / `Medium` / `High` / `Critical` (default `Medium`) |
