function getLocation() {
  const button = document.getElementById("findButton");
  const loadingMessage = document.getElementById("loading");
  const form = document.querySelector("form");

  if (!navigator.geolocation) {
    alert("Geolocation is not supported by your browser.");
    return false;
  }

  button.disabled = true;
  button.innerText = "Finding your location...";

  navigator.geolocation.getCurrentPosition(
    function (position) {
      document.getElementById("latitude").value = position.coords.latitude;

      document.getElementById("longitude").value = position.coords.longitude;

      button.innerText = "Searching...";
      loadingMessage.style.display = "block";

      form.submit();
    },

    function () {
      alert(
        "Unable to get your location. Please allow location access and try again.",
      );

      button.disabled = false;
      button.innerText = "Find a Bin";
      loadingMessage.style.display = "none";
    },
  );

  return false;
}

if (window.findMyBinData) {
  // -----------------------------
  // Initial data
  // -----------------------------

  const {
    userLatitude,
    userLongitude,
    binLatitude,
    binLongitude,
    distance,
    nearestBins,
  } = window.findMyBinData;

  // -----------------------------
  // Create the map
  // -----------------------------
  function createMap() {
    const newMap = L.map("map").setView([userLatitude, userLongitude], 17);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(newMap);

    return newMap;
  }
  const map = createMap();

  let currentRoute = null;
  let selectedMarker = null;

  let selectedBinLatitude = binLatitude;
  let selectedBinLongitude = binLongitude;
  // -----------------------------
  // Map icons
  // -----------------------------
  function createIcons() {
    const userIcon = L.divIcon({
      className: "custom-marker",
      html: '<div class="user-marker">●</div>',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });

    const binIcon = L.divIcon({
      className: "custom-marker",
      html: '<div class="bin-marker">🗑️</div>',
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    const selectedBinIcon = L.divIcon({
      className: "custom-marker",
      html: '<div class="bin-marker selected-bin">🗑️</div>',
      iconSize: [42, 42],
      iconAnchor: [21, 21],
    });

    return {
      userIcon,
      binIcon,
      selectedBinIcon,
    };
  }

  const { userIcon, binIcon, selectedBinIcon } = createIcons();

  // -----------------------------
  // Create bin markers
  // -----------------------------
  function createBinMarkers() {
    nearestBins.forEach(function (item, index) {
      const wasteBin = item.bin;
      const binDistance = Math.round(item.distance);

      const marker = L.marker([wasteBin.lat, wasteBin.lon], { icon: binIcon })
        .addTo(map)
        .bindPopup(
          `<strong>🗑️ Bin ${index + 1}</strong><br>${binDistance} metres away`,
        );
      marker.on("click", function () {
        if (selectedMarker) {
          selectedMarker.setIcon(binIcon);
        }
        marker.setIcon(selectedBinIcon);
        selectedMarker = marker;

        selectedBinLatitude = wasteBin.lat;
        selectedBinLongitude = wasteBin.lon;
        const heading = document.getElementById("resultHeading");
        const distanceLabel = document.getElementById("straightLineDistance");

        heading.innerText = `🗑️ Bin ${index + 1}`;
        distanceLabel.innerText = `${binDistance} metres`;

        loadWalkingRoute(selectedBinLatitude, selectedBinLongitude);
      });

      if (index === 0) {
        marker.setIcon(selectedBinIcon);
        selectedMarker = marker;
        marker.openPopup();
      }
    });
  }

  createBinMarkers();

  // -----------------------------
  // Walking route
  // -----------------------------
  async function loadWalkingRoute(selectedBinLatitude, selectedBinLongitude) {
    const walkingRoute = document.getElementById("walkingRoute");

    try {
      const response = await fetch("/walking-route", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_lat: userLatitude,
          user_lon: userLongitude,
          bin_lat: selectedBinLatitude,
          bin_lon: selectedBinLongitude,
        }),
      });

      const routeData = await response.json();

      if (!response.ok) {
        throw new Error(
          routeData.error || "Walking route could not be loaded.",
        );
      }

      if (currentRoute) {
        map.removeLayer(currentRoute);
      }

      currentRoute = L.geoJSON(routeData, {
        style: {
          color: "#2e8b57",
          weight: 6,
          opacity: 0.9,
        },
      }).addTo(map);

      map.fitBounds(currentRoute.getBounds(), {
        padding: [40, 40],
      });

      const summary = routeData.features[0].properties.summary;
      const walkingDistance = Math.round(summary.distance);
      const walkingMinutes = Math.round(summary.duration / 60);

      walkingRoute.innerText = `🚶 ${walkingDistance} metres • About ${walkingMinutes} minutes`;
    } catch (error) {
      console.error("Walking route error:", error);

      map.fitBounds(
        [
          [userLatitude, userLongitude],
          [selectedBinLatitude, selectedBinLongitude],
        ],
        {
          padding: [40, 40],
        },
      );

      walkingRoute.innerText =
        "Walking route unavailable. Use Navigate for directions.";
    }
  }

  loadWalkingRoute(binLatitude, binLongitude);

  // -----------------------------
  // Google Maps button
  // -----------------------------
  function setupNavigationButton() {
    const navigateButton = document.getElementById("navigateButton");

    navigateButton.addEventListener("click", function () {
      const mapsUrl =
        "https://www.google.com/maps/dir/?api=1" +
        `&origin=${userLatitude},${userLongitude}` +
        `&destination=${selectedBinLatitude},${selectedBinLongitude}` +
        "&travelmode=walking";

      window.open(mapsUrl, "_blank");
    });
  }

  setupNavigationButton();
}
