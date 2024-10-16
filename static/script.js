const socket = io();

document.getElementById('start').addEventListener('click', function () {
    const maxPrice = document.getElementById('maxPrice').value;
    const bounds = document.getElementById('bounds').value;
    const interval = document.getElementById('interval').value;

    socket.emit('start_scraping', {
        maxPrice: maxPrice,
        bounds: bounds,
        interval: interval
    });
});

document.getElementById('stop').addEventListener('click', function () {
    socket.emit('stop_scraping');
});

socket.on('log', function (data) {
    const logBox = document.getElementById('logBox');
    logBox.value += data.message + "\n";
    logBox.scrollTop = logBox.scrollHeight;  // Scroll to the bottom as new logs appear
});
