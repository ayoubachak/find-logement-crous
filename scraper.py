import json
import os
import threading
import logging
import smtplib
from datetime import datetime
from urllib.parse import urlencode
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from bs4 import BeautifulSoup

from config import EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD

logger = logging.getLogger(__name__)

BASE_URL = "https://trouverunlogement.lescrous.fr"
TOOL_ID = 48  # CROUS search tool id (was 37 before)
DEFAULT_BOUNDS = "1.4462445_49.241431_3.5592208_48.1201456"  # Ile-de-France
DEFAULT_LOCATION = "Île-de-France"

# Remembers which listings were already seen, per alert, across restarts.
SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_offers.json")
_seen_lock = threading.Lock()

# Written when new listings are found; notifier.py (desktop toasts) watches this file.
NOTIFY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_notification.json")


# ---------------------------------------------------------------- seen store
def _load_seen():
    try:
        with open(SEEN_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        logger.exception('Could not read seen_offers.json, starting fresh')
        return {}


def _save_seen(data):
    tmp = SEEN_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SEEN_FILE)


def _get_seen(alert_id):
    with _seen_lock:
        return _load_seen().get(str(alert_id))


def _update_seen(alert_id, url, links):
    with _seen_lock:
        data = _load_seen()
        data[str(alert_id)] = {
            "url": url,
            "links": sorted(links),
            "count": len(links),
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        _save_seen(data)


def clear_seen(alert_id):
    """Forget what was seen for an alert (call when the alert is deleted)."""
    with _seen_lock:
        data = _load_seen()
        if data.pop(str(alert_id), None) is not None:
            _save_seen(data)


def _write_notification(new_offers, total):
    """Drop a small JSON file that the desktop notifier picks up."""
    try:
        payload = {
            "id": datetime.now().isoformat(),
            "new": len(new_offers),
            "total": total,
            "offers": [
                {
                    "title": o["title"],
                    "price": o["price"],
                    "link": o["link"],
                    "description": o["description"],
                }
                for o in new_offers
            ],
        }
        tmp = NOTIFY_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, NOTIFY_FILE)
    except Exception:
        logger.exception('Could not write notification file')


# ------------------------------------------------------------------- helpers
def _text(el, default=""):
    """Safe text extraction: returns default if the element is missing."""
    return el.get_text(strip=True) if el else default


def build_search_url(alert):
    """Build the CROUS search URL from the alert's settings (all optional)."""
    bounds = getattr(alert, "bounds", None) or DEFAULT_BOUNDS
    max_price = getattr(alert, "price", None)
    location = (
        getattr(alert, "location_name", None)
        or getattr(alert, "city", None)
        or getattr(alert, "name", None)
        or DEFAULT_LOCATION
    )

    params = {"bounds": bounds}
    if max_price:
        # price is stored as float (500.0); send 500
        if isinstance(max_price, float) and max_price.is_integer():
            max_price = int(max_price)
        params["maxPrice"] = max_price
    params["locationName"] = location

    return f"{BASE_URL}/tools/{TOOL_ID}/search?{urlencode(params)}"


# --------------------------------------------------------------------- email
def send_email(notification_message, housing_offers, recipient_emails, subject='New Housing Results Found'):
    """Send the notification. Returns True on success, False otherwise."""
    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = ", ".join(recipient_emails)
    msg['Subject'] = subject

    text = f"{notification_message}\n\nHere are the new offers:\n"
    for offer in housing_offers:
        text += f"{offer['title']} - {offer['price']}\n{offer['link']}\n\n"

    html = f"""
    <html>
    <body>
        <h2>{notification_message}</h2>
        <p>Here are the new offers:</p>
        <ul>
    """
    for offer in housing_offers:
        img_html = (
            f'<img src="{offer["image"]}" alt="{offer["title"]}" style="width:100px;"><br>'
            if offer['image'] else ''
        )
        html += f"""
        <li>
            {img_html}
            <strong>{offer['title']} - {offer['price']}</strong><br>
            <p>{offer['description']}</p>
            <a href="{offer['link']}">View Details</a><br><br>
        </li>
        """
    html += """
        </ul>
    </body>
    </html>
    """

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    server = None
    try:
        port = int(EMAIL_PORT)
        # Google shows app passwords as "xxxx xxxx xxxx xxxx"; remove any whitespace
        password = "".join((EMAIL_HOST_PASSWORD or "").split())
        logger.info(
            f'SMTP: host={EMAIL_HOST} port={port} user={EMAIL_HOST_USER} '
            f'password_length={len(password)}'
        )
        if port == 465:
            # Implicit SSL
            server = smtplib.SMTP_SSL(EMAIL_HOST, port, timeout=30)
        else:
            # Typically 587: plain connection upgraded with STARTTLS
            server = smtplib.SMTP(EMAIL_HOST, port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        server.login(EMAIL_HOST_USER, password)
        server.sendmail(EMAIL_HOST_USER, recipient_emails, msg.as_string())
        logger.info('Email sent successfully.')
        return True
    except Exception:
        logger.exception('Failed to send email')
        return False
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass


# ------------------------------------------------------------------- scraper
def check_for_results(alert):
    """
    Fetch the current listings and compare them with the last check.
    Emails only the NEW listings. Returns True if an email was sent.
    """
    logger.info('check_for_results called')
    alert_id = getattr(alert, "id", None)

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "user-agent": "Mozilla/5.0"
    }

    try:
        url = build_search_url(alert)
        logger.info(f'Search URL: {url}')
        response = requests.get(url, headers=headers, timeout=20)
        logger.info(f'HTTP GET request to {url} returned status code {response.status_code}')
        if response.status_code != 200:
            return False

        soup = BeautifulSoup(response.content, 'html.parser')
        result_element = soup.find('h2', class_='SearchResults-desktop')
        if not result_element:
            # Page layout changed or we were blocked: don't touch the saved state
            logger.warning('Results header not found on the page. Check selectors.')
            return False

        header_text = result_element.get_text(strip=True)
        no_results = "Aucun logement trouvé" in header_text

        housing_offers = []
        if not no_results:
            for offer in soup.find_all('li', class_='fr-col-12'):
                title_h3 = offer.find('h3', class_='fr-card__title')
                link_el = title_h3.find('a') if title_h3 else None
                if not link_el or not link_el.get('href'):
                    continue  # not an offer card (layout/pagination item)

                img_el = offer.find('img', class_='fr-responsive-img')
                image = ""
                if img_el:
                    image = img_el.get('src') or img_el.get('data-src') or ""

                href = link_el['href']
                if href.startswith('/'):
                    href = BASE_URL + href

                housing_offers.append({
                    'title': _text(link_el),
                    'link': href,
                    'price': _text(offer.find('p', class_='fr-badge')),
                    'description': _text(offer.find('p', class_='fr-card__desc')),
                    'image': image,
                })

            if not housing_offers:
                logger.warning('Header says housing found, but no offer cards were parsed. Check selectors.')
                return False

        # ---- compare with the previous check
        current_links = {o['link'] for o in housing_offers}
        entry = _get_seen(alert_id)
        baseline = entry is None or entry.get("url") != url  # first run (or search changed)
        previous_links = set() if baseline else set(entry.get("links", []))
        previous_count = None if baseline else entry.get("count", len(previous_links))
        new_links = current_links - previous_links

        logger.info(
            f'[alert {alert_id}] previous={previous_count if previous_count is not None else "n/a (first run)"} '
            f'current={len(current_links)} new={len(new_links)}'
        )

        if not new_links:
            # Keep the saved state in sync (drops listings that disappeared,
            # so they count as new if they come back).
            _update_seen(alert_id, url, current_links)
            return False

        new_offers = [o for o in housing_offers if o['link'] in new_links]
        recipient_emails = [e.strip() for e in alert.emails.split(",") if e.strip()]
        message = f"{len(new_offers)} new housing offer(s), {len(current_links)} available in total"
        subject = f"{len(new_offers)} new housing offer(s) found ({len(current_links)} total)"

        if send_email(message, new_offers, recipient_emails, subject=subject):
            _update_seen(alert_id, url, current_links)
            _write_notification(new_offers, len(current_links))
            return True

        # Email failed: keep the old state so the same listings are retried next cycle
        return False

    except Exception:
        logger.exception('Error during scraping')  # logs the full traceback
        return False
