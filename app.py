from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit
import threading
import time
import logging
from scraper import check_for_results
import json


app = Flask(__name__)
socketio = SocketIO(app)

scraping_active = False
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def start_scraping(max_price, bounds, interval):
    global scraping_active
    scraping_active = True
    logger.info(f'Scraping started with maxPrice={max_price} and bounds={bounds}')
    socketio.emit('log', {'message': 'Scraping started...'})

    while scraping_active:
        logger.info('Checking for new results...')
        socketio.emit('log', {'message': 'Checking for new results...'})
        if check_for_results(max_price, bounds):
            logger.info('Results found! Sending email and stopping scraper.')
            socketio.emit('log', {'message': 'Results found! Email sent.'})
            break
        logger.info(f'Waiting for {interval} seconds before the next check...')
        socketio.emit('log', {'message': f'Waiting for {interval} seconds...'})
        time.sleep(interval)
    
    scraping_active = False
    logger.info('Scraping stopped.')
    socketio.emit('log', {'message': 'Scraping stopped.'})



@app.route('/')
def index():
    with open('static/meta.json') as meta_file:
        meta = json.load(meta_file)
    return render_template('index.html', meta=meta)
@app.route('/meta.json')
def meta_json():
    """Serve the meta.json file."""
    return send_from_directory('static', 'meta.json')

@socketio.on('start_scraping')
def handle_start_scraping(data):
    max_price = data.get('maxPrice', '500')
    bounds = data.get('bounds', '4.8583622_45.7955875_4.9212614_45.7484524')
    interval = int(data.get('interval', 5))
    
    if not scraping_active:
        threading.Thread(target=start_scraping, args=(max_price, bounds, interval)).start()

@socketio.on('stop_scraping')
def handle_stop_scraping():
    global scraping_active
    scraping_active = False
    logger.info('Scraping manually stopped by user.')
    socketio.emit('log', {'message': 'Scraping manually stopped by user.'})

if __name__ == '__main__':
    socketio.run(app, debug=True)
