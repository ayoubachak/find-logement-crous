import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from config import EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD, EMAIL_RECEIVER

logger = logging.getLogger(__name__)

def send_email(notification_message, housing_offers):
    msg = MIMEMultipart("alternative")
    msg['From'] = EMAIL_HOST_USER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = 'New Housing Results Found'

    # Create the plain-text version of the email content
    text = f"{notification_message}\n\nHere are the available offers:\n"
    for offer in housing_offers:
        text += f"{offer['title']} - {offer['price']}\n{offer['link']}\n\n"

    # Create the HTML version of the email content
    html = f"""
    <html>
    <body>
        <h2>{notification_message}</h2>
        <p>Here are the available offers:</p>
        <ul>
    """
    for offer in housing_offers:
        html += f"""
        <li>
            <img src="{offer['image']}" alt="Image of {offer['title']}" style="width:100px;"><br>
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

    # Attach both plain text and HTML versions
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_HOST_USER, EMAIL_HOST_PASSWORD)
        server.sendmail(EMAIL_HOST_USER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        logger.info('Email sent successfully.')
    except Exception as e:
        logger.error(f'Failed to send email: {e}')


def check_for_results(max_price, bounds):
    url = f"https://trouverunlogement.lescrous.fr/tools/36/search?maxPrice={max_price}&bounds={bounds}"

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        logger.info(f'HTTP GET request to {url} returned status code {response.status_code}')
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            result_element = soup.find('h2', class_='SearchResults-desktop')
            if result_element and "Aucun logement trouvé" not in result_element.text:
                logger.info(f'Housing found: {result_element.text.strip()}')

                # Scrape the offers
                housing_offers = []
                offer_elements = soup.find_all('li', class_='fr-col-12')  # Adjust the selector if needed
                for offer in offer_elements:
                    title_element = offer.find('h3', class_='fr-card__title').find('a')
                    price_element = offer.find('p', class_='fr-badge')
                    description_element = offer.find('p', class_='fr-card__desc')
                    image_element = offer.find('img', class_='fr-responsive-img')

                    housing_offers.append({
                        'title': title_element.text.strip(),
                        'link': "https://trouverunlogement.lescrous.fr" + title_element['href'],
                        'price': price_element.text.strip(),
                        'description': description_element.text.strip(),
                        'image': image_element['src']
                    })

                # Send email with the list of offers
                notification_message = f'{result_element.text.strip()}'
                send_email(notification_message, housing_offers)
                return True
        return False
    except Exception as e:
        logger.error(f'Error during scraping: {e}')
        return False
