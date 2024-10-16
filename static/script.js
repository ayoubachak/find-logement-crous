const socket = io();

const photonAPIUrl = "https://photon.komoot.io/api/";

document.getElementById('searchLocation').addEventListener('input', async function () {
    const query = this.value;

    // If "No Location" is checked, clear the bounds
    if (document.getElementById('noLocationCheckbox').checked) {
        document.getElementById('bounds').value = '';  // Clear bounds if "No Location" is selected
        return;
    }

    if (query.length >= 3) {
        try {
            const response = await fetch(`${photonAPIUrl}?q=${query}&limit=5&lang=fr`);
            const data = await response.json();

            const suggestionsList = document.getElementById('suggestions');
            suggestionsList.innerHTML = '';  // Clear previous suggestions

            if (data.features && data.features.length > 0) {
                data.features.forEach((feature, index) => {
                    const suggestionItem = document.createElement('li');
                    suggestionItem.textContent = `${feature.properties.name}, ${feature.properties.state}, ${feature.properties.country}`;
                    suggestionItem.classList.add('cursor-pointer', 'hover:bg-gray-200', 'px-2', 'py-1', 'border-b');
                    suggestionItem.addEventListener('click', function () {
                        const coordinates = feature.geometry.coordinates;
                        const extent = feature.properties.extent || null;

                        let bounds = '';
                        if (extent) {
                            bounds = `${extent[0]}_${extent[1]}_${extent[2]}_${extent[3]}`; // If extent is present, use it
                        } else {
                            // If only point coordinates are available, construct a small bounding box around the point
                            const lng = coordinates[0];
                            const lat = coordinates[1];
                            bounds = `${lng - 0.01}_${lat + 0.01}_${lng + 0.01}_${lat - 0.01}`;
                        }

                        document.getElementById('bounds').value = bounds;  // Update the bounds input field
                        document.getElementById('searchLocation').value = feature.properties.name;  // Update search bar with selected location
                        suggestionsList.innerHTML = '';  // Clear suggestions after selection
                    });

                    suggestionsList.appendChild(suggestionItem);
                });
            }
        } catch (error) {
            console.error("Error fetching location data from Photon API:", error);
        }
    }
});

document.getElementById('noLocationCheckbox').addEventListener('change', function () {
    if (this.checked) {
        document.getElementById('bounds').value = '';  // Clear bounds if "No Location" is selected
        document.getElementById('searchLocation').disabled = true;  // Disable location search
        document.getElementById('suggestions').innerHTML = '';  // Clear suggestions if "No Location" is selected
    } else {
        document.getElementById('searchLocation').disabled = false;  // Enable location search
    }
});

document.getElementById('start').addEventListener('click', function () {
    const maxPrice = document.getElementById('maxPrice').value;
    const bounds = document.getElementById('bounds').value;  // Can be empty if "No Location" is selected

    socket.emit('start_scraping', {
        maxPrice: maxPrice,
        bounds: bounds
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
