# Housing Alert System (CROUS)

A web application that watches the CROUS housing site ([trouverunlogement.lescrous.fr](https://trouverunlogement.lescrous.fr)) and tells you as soon as **new** housing appears: by email, by a Windows pop-up, and optionally by opening the listing for you in Chrome. It runs in the background on Windows, so you do not need to keep a terminal open.

## Table of Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the application](#running-the-application)
- [Using the dashboard](#using-the-dashboard)
- [Running in the background on Windows](#running-in-the-background-on-windows)
- [The desktop helper](#the-desktop-helper)
- [Files created at runtime](#files-created-at-runtime)
- [Troubleshooting](#troubleshooting)
- [Security notes](#security-notes)
- [For developers](#for-developers)

## Features

- **Alerts by city, price and area**: pick a city, set a max price, and add one or more email addresses.
- **Only new listings**: the app remembers what it has already seen and emails only what is new, including how many are available in total.
- **Always on**: an alert keeps checking until you turn it off. Failed emails are retried on the next cycle, so nothing is missed.
- **Randomized timing**: optionally wait a random number of seconds (for example 2 to 49) between checks instead of a fixed interval.
- **Three ways to be notified**, each with its own switch on the dashboard:
  - a Windows pop-up (toast) that opens the listing when clicked,
  - a new Chrome window with the listing, Google Maps for it, and `messervices.etudiant.gouv.fr`,
  - a Chrome notification in an open dashboard tab.
- **Persistent activity log**: the log is saved on disk, so it is still there when you reopen the page or restart the app.
- **Modern dashboard**: alerts table, notification and timing options in a side panel, and a live log console.
- **Windows service**: runs in the background, starts with Windows, and can be switched on and off with one double-click.

## How it works

```
 CROUS site  <---- requests ----  scraper.py  (one check per alert, in a background thread)
                                      |
        compares with seen_offers.json (what it saw last time)
                                      |
                 new listings? ---- yes ----> email (SMTP)
                                      |          |
                                      |          +--> latest_notification.json
                                      |                     |
                       app.py (Flask + Socket.IO)            v
                       dashboard, API, live log      notifier.py (desktop helper,
                                                      runs in YOUR Windows session)
                                                      |-- Windows pop-up
                                                      '-- opens Chrome tabs
```

1. For every active alert, a background thread fetches the CROUS search page and reads the listing cards.
2. It compares the listing links with the ones saved from the previous check (`seen_offers.json`).
3. If something new appeared, it sends one email containing only the new listings, then records them as seen.
4. It writes `latest_notification.json`. The desktop helper picks it up and shows the pop-up and/or opens Chrome, depending on your switches.
5. It waits (a fixed interval, or a random time if enabled) and repeats.

## Prerequisites

- Windows 10 or 11 (the app itself is cross-platform; the desktop helper and the `.bat` files are Windows only).
- Python 3.9 or higher (3.11 tested).
- An SMTP account for sending emails. Gmail works with an **app password** (see below).
- Google Chrome, only if you want the auto-open feature.
- Administrator rights, only for installing and managing the Windows service.

## Installation

1. **Get the project**

   ```bash
   git clone https://github.com/ayoubachak/find-logement-crous.git
   cd find-logement-crous
   ```

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   ```

3. **Activate it**

   - Windows (PowerShell): `venv\Scripts\activate`
   - macOS / Linux: `source venv/bin/activate`

4. **Install the dependencies**

   ```bash
   pip install -r requirements.txt
   ```

   The desktop helper needs one extra package, `winotify`. You can ignore it for now: `enable_autostart.bat` installs it for you (see below).

## Configuration

### 1. Environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=any_long_random_string
EMAIL_PASSWORD=your_email_app_password
DATABASE_URL=sqlite:///alerts.db
```

- `SECRET_KEY` is required. Use any long random string.
- `EMAIL_PASSWORD` is the password used to send emails (see Gmail below).
- `DATABASE_URL` defaults to a local SQLite file.

The `.env` file is loaded at the very top of `app.py`, before `config.py` is imported, so `config.py` always sees your real values.

### 2. Email settings (`config.py`)

```python
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587                       # 587 = STARTTLS, 465 = SSL
EMAIL_HOST_USER = 'your_email@gmail.com'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD')
```

Port 587 uses STARTTLS and port 465 uses implicit SSL. The app handles both.

### 3. Gmail app password

Gmail does not accept your normal password over SMTP.

1. Turn on 2-Step Verification on the Google account that will **send** the emails.
2. Create an app password in the Google account security settings.
3. Put it in `.env` as `EMAIL_PASSWORD`. Google shows it as four groups of four letters. Spaces are removed automatically, so pasting it with spaces is fine.

## Running the application

For a quick test in a terminal:

```bash
python app.py
```

Then open `http://127.0.0.1:5000`. The server listens on `127.0.0.1` only, so it is reachable from your own PC and nowhere else.

For development with auto-reload (PowerShell):

```powershell
$env:FLASK_DEBUG = "1"
python app.py
```

Without `FLASK_DEBUG`, the app runs with debug and the reloader off, which is what you want for the background service.

## Using the dashboard

### Creating an alert

1. Click **Add New Alert**.
2. Type a city and **pick one of the suggestions**. This sets the search area. The form will not submit without it.
3. Set the max price, the refresh interval in seconds, and the email addresses (comma separated).
4. Leave **Activate alert** on to start checking immediately.

### Managing alerts

The alerts table shows each alert's status and interval. Use **Edit**, **Activate / Deactivate** and **Delete** on each row. An alert keeps running until you deactivate it.

### Notifications (side panel)

| Switch | What it does |
| --- | --- |
| Windows pop-up | Desktop notification when new housing appears. Click it to open the listing. On by default. |
| Auto-open in Chrome | Opens a new Chrome window with the listing, a Google Maps search for it, and `https://messervices.etudiant.gouv.fr/`. Off by default. |
| Chrome pop-up in this tab | A browser notification while the dashboard tab stays open. Remembered per browser. |

Changes are saved instantly and apply from the next notification, with no restart. The **Helper** badge shows whether the desktop helper is running. The first two switches need it.

If several new listings appear at once, each gets its own Chrome window (up to 3), and the `messervices` tab only opens in the first window.

### Check timing (side panel)

- **Randomize the wait off**: every alert waits its own fixed interval between checks.
- **Randomize the wait on**: after every check the app waits a random whole number of seconds between **Min** and **Max**. This applies to all alerts. The minimum allowed is 2 seconds and the maximum is 3600.

Be careful with very short waits. Checking the CROUS site every few seconds can get your IP rate-limited or blocked. The page warns you below 15 seconds. A range such as 30 to 90 seconds is a reasonable choice.

### Activity log

The log shows every check, the `previous / current / new` listing counts, emails sent, warnings and errors. It keeps the last 500 lines in `logs.txt`, reloads them when you open the page, and shows a Live or Offline indicator.

## Running in the background on Windows

The app runs as a Windows service using [NSSM](https://nssm.cc), so it keeps working when no terminal is open and starts with Windows.

### One-time setup (administrator PowerShell)

```powershell
winget install -e --id NSSM.NSSM
```

Close PowerShell, open a **new** one as Administrator (so `nssm` is on the PATH), then:

```powershell
nssm install FindLogement "E:\find-logement-crous\venv\Scripts\python.exe" app.py
nssm set FindLogement AppDirectory "E:\find-logement-crous"
nssm set FindLogement AppStdout "E:\find-logement-crous\service.log"
nssm set FindLogement AppStderr "E:\find-logement-crous\service.log"
nssm start FindLogement
```

Adjust the paths to where your project lives. `service.log` is the raw console output of the service, useful when something goes wrong.

### Autostart on or off with a double-click

Keep these two files in the project folder, next to `venv`:

| File | What it does |
| --- | --- |
| `enable_autostart.bat` | Sets the service to start with Windows, starts it now, installs `winotify`, and starts the desktop helper at every login. |
| `disable_autostart.bat` | Sets the service to manual, stops it, and removes and stops the desktop helper. |

Both ask for administrator rights themselves (click Yes on the Windows prompt). You only need admin to start, stop or reconfigure the service. Day to day, you just use the dashboard in a normal browser.

### Useful service commands (administrator PowerShell)

```powershell
nssm status FindLogement
nssm restart FindLogement      # needed after changing Python files
nssm stop FindLogement
nssm remove FindLogement confirm
Get-Content E:\find-logement-crous\service.log -Wait -Tail 30
```

The service only checks while your PC is on and awake. Set Windows sleep to "Never" while plugged in if you want continuous checks.

## The desktop helper

`notifier.py` is a small program that runs in **your** Windows session. It exists because Windows services run in an isolated session and cannot show pop-ups or open windows on your desktop. The service writes `latest_notification.json` whenever it finds new listings, and the helper reacts to it:

- shows the Windows pop-up if that switch is on,
- opens the Chrome windows if auto-open is on.

It re-reads `settings.json` on every notification, so switch changes need no restart. It ignores whatever is already in the notification file when it starts, so a reboot never replays old alerts. It also writes a heartbeat file so the dashboard can show whether it is running.

Notes:

- The Google Maps tab searches for the listing title plus the card description, which on CROUS cards is usually the address.
- Chrome is found in its standard install folders. If it is installed elsewhere, auto-open does nothing.
- Windows may open the new Chrome window behind your current window instead of in front.
- Focus Assist / Do Not Disturb will hold back the Windows pop-up.

## Files created at runtime

| File | Purpose |
| --- | --- |
| `alerts.db` | The SQLite database with your alerts. |
| `seen_offers.json` | Listings already seen, per alert. Delete it to make every current listing count as new again. |
| `settings.json` | The notification switches and random wait settings. |
| `logs.txt` | The persistent activity log (last 500 lines). |
| `latest_notification.json` | Written when new listings are found. Read by the desktop helper. |
| `helper.heartbeat` | Touched by the desktop helper every few seconds. |
| `service.log` | Raw console output of the Windows service. |

None of these should be committed to Git. Add them to `.gitignore` together with `.env`.

## Troubleshooting

**Nothing happens after I start the app.**
Only alerts marked **Active** are checked. Look at the Status column and click Activate. The console (or `service.log`) should then show `Started scraping` and `check_for_results called`.

**The first email arrives with every current listing.**
That is expected. The first check of an alert has nothing to compare with, so everything counts as new. After that, only new listings are sent. Editing an alert's search area starts a fresh baseline in the same way.

**`Failed to send email: Connection unexpectedly closed`.**
The server hung up during login, which almost always means wrong credentials. Check that 2-Step Verification is on, that you use an app password for the same Gmail account as `EMAIL_HOST_USER`, and that `EMAIL_PASSWORD` is really loaded. The log prints `password_length=16` for a correct Gmail app password (the password itself is never logged). Outlook and Hotmail have disabled basic SMTP login for most accounts, so use Gmail for sending.

**`Pick a city from the suggestions` when saving an alert.**
The search area is set when you click a suggestion in the city field. Type a city and click one of the results.

**The log says `Header says housing found, but no offer cards were parsed`.**
The CROUS page layout changed and the selectors in `scraper.py` need updating. Open an alert page in the browser, copy one `<li>` card from the page source, and adjust `check_for_results`.

**`nssm: The term 'nssm' is not recognized`.**
Close PowerShell and open a new window after installing NSSM, so the updated PATH is loaded.

**`OpenService(): Access is denied`.**
Starting, stopping and configuring a service needs an administrator PowerShell, or just use the `.bat` files, which elevate themselves.

**The Helper badge says "not running".**
Run `enable_autostart.bat` again. If the Windows pop-up or Chrome windows still do not appear, check that `winotify` installed without errors and that Chrome is in a standard location.

**Changes to a Python file have no effect.**
The service keeps running the old code. Run `nssm restart FindLogement`.

## Security notes

- Never commit `.env`, `alerts.db` or the generated runtime files.
- The server binds to `127.0.0.1` and has no login. Do not expose it to the internet or your network as is. If you ever want remote access, add authentication first.
- Use an app password, not your real email password, and rotate it if it leaks.
- Respect the CROUS site. Keep the check interval reasonable.

## For developers

### Project structure

```
app.py                  Flask + Socket.IO app: routes, API, background alert manager
scraper.py              Fetches and parses CROUS, tracks seen listings, sends emails
settings.py             Shared settings (settings.json) and helper heartbeat check
logstore.py             Persistent ring buffer behind the activity log
notifier.py             Desktop helper (Windows pop-up, auto-open Chrome)
models.py               SQLAlchemy models (Alert, AlertLog)
config.py               SMTP settings
enable_autostart.bat    Service and helper start with Windows
disable_autostart.bat   Turn that off
templates/
  base.html             Base layout (overridable head, body class and container)
  index.html            Dashboard
  alert_form.html       Shared create/edit form
  create_alert.html     Extends alert_form.html
  edit_alert.html       Extends alert_form.html
static/                 Tailwind output, styles.css, script.js (city search)
```

### Key components

- **`app.py`**
  - `manage_alerts()` runs in a background thread, checks every 5 seconds for active alerts, and starts one scraping thread per alert.
  - `start_scraping(alert_id)` loops while the alert is active: it calls `check_for_results`, logs the result, then sleeps for `next_wait(alert)`.
  - `next_wait(alert)` returns a random whole number of seconds if random wait is enabled, otherwise the alert's own interval.
  - `push_log()` stores a line in the `LogStore` and emits it over Socket.IO. A logging handler also forwards the scraper's count lines, warnings and errors to the dashboard log.
  - With the Flask reloader, the module is imported twice. The manager thread is therefore started from the `__main__` block, and only in the serving process.
- **`scraper.py`**
  - `build_search_url(alert)` builds the CROUS URL from the alert's bounds, price and city. `TOOL_ID` is the CROUS search tool id and may change.
  - `check_for_results(alert)` fetches and parses the page, compares with the saved listings, emails only the new ones, and returns `True` when an email was sent. If the email fails, the saved state is not updated, so the same listings are retried.
  - `send_email(...)` supports STARTTLS (587) and SSL (465), strips whitespace from the password, and returns `True` or `False`.
- **`settings.py`** stores `toast`, `autoopen`, `random_wait`, `wait_min`, `wait_max`, validates and clamps them, and checks the helper heartbeat.
- **`notifier.py`** polls `latest_notification.json` every 3 seconds. It uses `winotify` for toasts and starts Chrome with `--new-window` and the URLs.

### HTTP and Socket.IO API

| Endpoint | Description |
| --- | --- |
| `GET /api/settings` | Current switches, random wait settings and `helper_running`. |
| `POST /api/settings` | JSON body with any of `toast`, `autoopen`, `random_wait`, `wait_min`, `wait_max`. Returns the saved values. |
| `GET /api/logs` | The last 500 log lines, each with a `seq` number. |
| `GET /notify` | The earlier standalone Chrome notification page. It still works, but the dashboard now has the same switches. |
| Socket event `log` | `{message, seq}` for each new log line. |
| Socket event `new_listings` | The contents of `latest_notification.json`, sent when an email went out. |

### How to extend or improve

- **Per-alert random timing**: store the min and max on the `Alert` model (this needs a database migration) instead of in `settings.json`.
- **Pagination**: the scraper reads only the first results page. Add paging if a search can return more listings than one page shows.
- **Resilient selectors**: the CSS classes in `check_for_results` come from the current CROUS page. A tests folder with saved HTML samples would make layout changes easy to catch.
- **Other sites**: split the scraper into a small interface so more housing sites can be watched.
- **Authentication**: add user accounts before exposing the app beyond `127.0.0.1`.
- **Headless deployment**: a VPS, a Raspberry Pi or a scheduled GitHub Action can run the checks without your PC. The desktop-only features would not apply there.
- **Docker**: add a Dockerfile for the server part (not the Windows helper).
- **Tests**: unit tests for the parser, the "new listings" comparison, `settings.update`, and `LogStore`.