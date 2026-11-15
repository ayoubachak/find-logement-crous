from dotenv import load_dotenv
load_dotenv(override=True)  # must run before importing scraper (it imports config, which reads env vars)

from flask import Flask, render_template, render_template_string, jsonify, request, redirect, url_for, flash
from flask_socketio import SocketIO, emit
import threading
import time
import random
import logging
from models import db, Alert, AlertLog
from scraper import check_for_results, clear_seen, NOTIFY_FILE
import settings
from logstore import LogStore
import json
import os
from datetime import datetime


app = Flask(__name__)
SECRET_KEY = os.getenv('SECRET_KEY')
assert SECRET_KEY, 'SECRET_KEY environment variable not set'

# Get the PostgreSQL connection string from the environment variable
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///alerts.db')
assert DATABASE_URL, 'DATABASE_URL environment variable not set'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = SECRET_KEY


db.init_app(app)

with app.app_context():
    db.create_all()  # Create the database tables

socketio = SocketIO(app)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Track scraping threads
scraping_threads = {}


# Activity log shown in the web UI. Kept in logs.txt so it survives closing the tab and restarts.
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.txt")
log_store = LogStore(LOG_FILE, keep=500)


def push_log(text):
    """Store a line in the persistent log and push it to every open page."""
    seq = log_store.add(text)
    socketio.emit('log', {'message': text, 'seq': seq})


def log_message(message, alert=None):
    """Helper function to format and log messages with additional details."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    alert_name = f"[Alert: {alert.name}]" if alert else ""
    full_message = f"{timestamp} {alert_name} {message}"
    logger.info(full_message)
    push_log(full_message)


class UILogHandler(logging.Handler):
    """Forward the scraper's useful lines (previous/current/new counts, warnings, errors) to the web log."""

    def emit(self, record):
        try:
            msg = record.getMessage()
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if record.levelno >= logging.WARNING:
                push_log(f"{ts} [{record.levelname}] {msg}")
            elif msg.startswith('[alert'):
                push_log(f"{ts} {msg}")
        except Exception:
            pass


logging.getLogger('scraper').addHandler(UILogHandler())


def next_wait(alert):
    """Seconds to wait before the next check: random in [min, max] if enabled, else the alert's interval."""
    cfg = settings.load()
    if cfg["random_wait"]:
        return random.randint(cfg["wait_min"], cfg["wait_max"])
    return alert.interval


def start_scraping(alert_id):
    """Scraping logic for a specific alert."""
    with app.app_context():
        alert = Alert.query.get(alert_id)
        if not alert:
            log_message(f"Alert with ID {alert_id} no longer exists.")
            return

        log_message(f"Started scraping for {alert.city} with max price {alert.price}", alert)

        while alert.status:
            try:
                found = check_for_results(alert)
            except Exception:
                logger.exception('Unexpected error in check_for_results')
                found = False

            wait = next_wait(alert)

            if found:
                log_message(f"New listings found for {alert.city}, email sent. Next check in {wait} seconds.", alert)
                # Push to open browser tabs (Chrome pop-up)
                try:
                    with open(NOTIFY_FILE, encoding="utf-8") as f:
                        socketio.emit('new_listings', json.load(f))
                except Exception:
                    logger.exception('Could not emit new_listings')
            else:
                log_message(f"No new listings for {alert.city}. Next check in {wait} seconds.", alert)

            time.sleep(wait)
            # Refresh the alert status from the database
            db.session.refresh(alert)

        log_message(f"Scraping stopped for {alert.city}.", alert)

        # Remove the thread from tracking after completion
        if alert_id in scraping_threads:
            del scraping_threads[alert_id]


def manage_alerts():
    """Background task that checks the status of all alerts and starts/stops scraping."""
    logger.info('Alert manager started.')
    last_active = None
    while True:
        try:
            with app.app_context():
                alerts = Alert.query.filter_by(status=True).all()
                active_ids = sorted(a.id for a in alerts)
                if active_ids != last_active:
                    total = Alert.query.count()
                    logger.info(f'Alert manager: {len(active_ids)} active alert(s) {active_ids} out of {total} total.')
                    last_active = active_ids
                for alert in alerts:
                    if alert.id not in scraping_threads or not scraping_threads[alert.id].is_alive():
                        thread = threading.Thread(target=start_scraping, args=(alert.id,), daemon=True)
                        thread.start()
                        scraping_threads[alert.id] = thread
        except Exception:
            logger.exception('manage_alerts error')

        time.sleep(5)  # Check every 5 seconds for active alerts


# Load meta.json to pass to templates
def get_meta_data():
    with open('static/meta.json') as meta_file:
        return json.load(meta_file)


@app.route('/')
def index():
    meta = get_meta_data()
    alerts = Alert.query.all()
    return render_template('index.html', alerts=alerts, meta=meta)


NOTIFY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Logement alerts - notifications</title>
<style>
  body { font-family: Arial, sans-serif; max-width: 560px; margin: 40px auto; padding: 0 16px; }
  label { display: block; margin: 12px 0; cursor: pointer; }
  small { color: #555; display: block; margin-left: 24px; }
  button { padding: 10px 16px; margin-right: 8px; cursor: pointer; }
  #status, #saved { margin: 12px 0; font-weight: bold; }
  #saved { color: #1a7f37; height: 1.2em; }
  hr { margin: 28px 0; }
</style>
</head>
<body>
<h2>When new housing appears</h2>
<label><input type="checkbox" id="toast"> Windows pop-up
  <small>A toast notification on your desktop. Click it to open the listing.</small></label>
<label><input type="checkbox" id="autoopen"> Auto-open in a new Chrome window
  <small>Tabs: the CROUS listing, Google Maps for it, and messervices.etudiant.gouv.fr</small></label>
<div id="saved"></div>
<p><small style="margin-left:0">Both need the helper running on your PC (it starts with Windows once autostart is enabled).</small></p>

<hr>
<h2>Chrome pop-up (this tab)</h2>
<p>Optional: keep this tab open to also get a Chrome notification.</p>
<button id="enable">Enable Chrome notifications</button>
<button id="test">Send test</button>
<div id="status"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.5/socket.io.min.js"></script>
<script>
// ---- server-side switches
const toastEl = document.getElementById('toast');
const autoEl = document.getElementById('autoopen');
const savedEl = document.getElementById('saved');

async function loadSettings() {
  try {
    const r = await fetch('/api/settings');
    const s = await r.json();
    toastEl.checked = s.toast;
    autoEl.checked = s.autoopen;
  } catch (e) { savedEl.textContent = 'Could not load settings'; }
}
async function saveSettings() {
  try {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({toast: toastEl.checked, autoopen: autoEl.checked})
    });
    const s = await r.json();
    toastEl.checked = s.toast;
    autoEl.checked = s.autoopen;
    savedEl.textContent = 'Saved';
    setTimeout(() => savedEl.textContent = '', 1500);
  } catch (e) { savedEl.textContent = 'Could not save'; }
}
toastEl.onchange = saveSettings;
autoEl.onchange = saveSettings;
loadSettings();

// ---- Chrome notification in this tab
const statusEl = document.getElementById('status');

function refreshStatus() {
  const perm = Notification.permission;
  statusEl.textContent = perm === 'granted' ? 'Chrome notifications: ON'
    : perm === 'denied' ? 'Chrome notifications: BLOCKED (allow them in the site settings of the address bar)'
    : 'Chrome notifications: not enabled yet';
}

function notify(title, body, link) {
  if (Notification.permission !== 'granted') return;
  const n = new Notification(title, { body: body, requireInteraction: true });
  n.onclick = () => { if (link) window.open(link, '_blank'); n.close(); };
}

document.getElementById('enable').onclick = async () => {
  await Notification.requestPermission();
  refreshStatus();
};
document.getElementById('test').onclick = () => notify('Test', 'Notifications work.', null);

const socket = io();
socket.on('new_listings', (data) => {
  const offers = data.offers || [];
  const lines = offers.slice(0, 3).map(o => o.title + ' - ' + o.price);
  if (offers.length > 3) lines.push('... and ' + (offers.length - 3) + ' more');
  notify(data.new + ' new housing offer(s) (' + data.total + ' available)',
         lines.join('\\n'),
         offers.length ? offers[0].link : null);
});

refreshStatus();
</script>
</body>
</html>
"""


@app.route('/notify')
def notify_page():
    return render_template_string(NOTIFY_HTML)


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Read / change the switches and timing (stored in settings.json, read by notifier.py and the scraper loop)."""
    if request.method == 'POST':
        data = settings.update(request.get_json(silent=True) or {})
    else:
        data = settings.load()
    data['helper_running'] = settings.helper_running()
    return jsonify(data)


@app.route('/api/logs')
def api_logs():
    """Recent activity log lines, so the page can show them again after a reload."""
    return jsonify({'lines': log_store.history()})


@app.route('/alerts/new', methods=['GET', 'POST'])
def create_alert():
    meta = get_meta_data()
    if request.method == 'POST':
        name = request.form['city']  # Save the city as the name of the alert
        city = request.form['city']
        assert request.form['bounds'], 'Bounds cannot be empty'
        bounds = request.form['bounds']  # Save the bounds separately
        price = float(request.form['price'])
        emails = request.form['emails']
        interval = int(request.form['interval'])  # Refresh duration
        status = request.form.get('status') == 'on'  # Toggle

        alert = Alert(name=name, city=city, bounds=bounds, price=price, emails=emails, interval=interval, status=status)
        db.session.add(alert)
        db.session.commit()

        flash('Alert created successfully!')
        return redirect(url_for('index'))

    return render_template('create_alert.html', meta=meta)


@app.route('/alerts/<int:alert_id>/edit', methods=['GET', 'POST'])
def edit_alert(alert_id):
    meta = get_meta_data()
    alert = Alert.query.get_or_404(alert_id)

    if request.method == 'POST':
        alert.name = request.form['city']  # Update the alert name
        alert.city = request.form['city']  # Keep city as it is
        assert request.form['bounds'], 'Bounds cannot be empty'
        alert.bounds = request.form['bounds']  # Update bounds
        alert.price = float(request.form['price'])
        alert.emails = request.form['emails']
        alert.interval = int(request.form['interval'])
        alert.status = request.form.get('status') == 'on'
        db.session.commit()

        flash('Alert updated successfully!')
        return redirect(url_for('index'))

    logs = AlertLog.query.filter_by(alert_id=alert.id).all()
    return render_template('edit_alert.html', alert=alert, logs=logs, meta=meta)


@app.route('/alerts/<int:alert_id>/toggle')
def toggle_alert_status(alert_id):
    alert = Alert.query.get_or_404(alert_id)
    alert.status = not alert.status
    db.session.commit()
    action = "activated" if alert.status else "deactivated"
    log_message(f"Alert for {alert.city} {action}.", alert)
    return redirect(url_for('index'))


@app.route('/alerts/<int:alert_id>/delete', methods=['POST', 'GET'])
def delete_alert(alert_id):
    with app.app_context():
        alert = Alert.query.get_or_404(alert_id)

        # Check if the alert is still running and stop the thread
        if alert_id in scraping_threads and scraping_threads[alert_id].is_alive():
            log_message(f"Stopping scraping for {alert.city} before deletion.", alert)
            # The thread will check the alert's status and exit
            alert.status = False
            db.session.commit()
            scraping_threads[alert_id].join()  # Wait for the thread to finish
            scraping_threads.pop(alert_id, None)  # Remove from the thread tracking dictionary

        log_message(f"Alert for {alert.city} is being deleted.", alert)
        clear_seen(alert_id)
        db.session.delete(alert)
        db.session.commit()
        flash('Alert deleted successfully!')
    return redirect(url_for('index'))


@socketio.on('start_scraping')
def handle_start_scraping(data):
    """Activate the alert; manage_alerts() picks it up within 5 seconds."""
    with app.app_context():
        alert = Alert.query.get(data['alert_id'])
        if alert:
            alert.status = True
            db.session.commit()
            log_message(f"Alert for {alert.city} activated.", alert)


@socketio.on('stop_scraping')
def handle_stop_scraping(data=None):
    """Deactivate the alert; its thread exits after the current wait."""
    with app.app_context():
        alert_id = (data or {}).get('alert_id')
        alert = Alert.query.get(alert_id) if alert_id else None
        if alert:
            alert.status = False
            db.session.commit()
            log_message(f"Alert for {alert.city} deactivated.", alert)
        else:
            logger.info('stop_scraping received without a valid alert_id.')


if __name__ == '__main__':
    # Service / normal run: no reloader, debug off.
    # For development set FLASK_DEBUG=1 (reloader on; the manager then starts only in
    # the child process that serves requests, otherwise alerts would run twice).
    debug = os.environ.get('FLASK_DEBUG') == '1'
    if not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        threading.Thread(target=manage_alerts, daemon=True).start()
    socketio.run(app, host='127.0.0.1', port=5000, debug=debug, use_reloader=debug,
                 allow_unsafe_werkzeug=True)
