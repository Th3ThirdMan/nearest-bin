function getLocation(triggerButton = null) {
  const button = triggerButton || document.getElementById("findButton");
  const originalButtonText = button.innerText;
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
      const latitude = position.coords.latitude;
      const longitude = position.coords.longitude;

      document.getElementById("latitude").value = latitude;
      document.getElementById("longitude").value = longitude;

      sessionStorage.setItem(
        "findMyBinLocation",
        JSON.stringify({
          latitude,
          longitude,
        }),
      );

      button.innerText = "Searching...";
      loadingMessage.style.display = "block";

      form.submit();
    },

    function (error) {
      console.error("Geolocation error:", error.code, error.message);

      alert(
        "Unable to get your location. Please allow location access and try again.",
      );

      button.disabled = false;
      button.innerText = originalButtonText;
      loadingMessage.style.display = "none";
    },

    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 30000,
    },
  );

  return false;
}

// Restore the last location when the home page is refreshed.
document.addEventListener("DOMContentLoaded", function () {
  if (window.findMyBinData) {
    return;
  }

  const savedLocation = sessionStorage.getItem("findMyBinLocation");

  if (!savedLocation) {
    return;
  }

  try {
    const location = JSON.parse(savedLocation);
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");
    const loadingMessage = document.getElementById("loading");
    const form = document.querySelector("form");

    latitudeInput.value = location.latitude;
    longitudeInput.value = location.longitude;
    loadingMessage.style.display = "block";

    form.submit();
  } catch (error) {
    sessionStorage.removeItem("findMyBinLocation");
    console.error("Saved location could not be read:", error);
  }
});

if (window.findMyBinData) {
  const searchForm = document.querySelector("form");
  searchForm.style.display = "none";

  // -----------------------------
  // Initial data
  // -----------------------------

  const {
    userLatitude: initialUserLatitude,
    userLongitude: initialUserLongitude,
    binLatitude,
    binLongitude,
    nearestBins,
  } = window.findMyBinData;

  let currentUserLatitude = initialUserLatitude;
  let currentUserLongitude = initialUserLongitude;

  let selectedBinLatitude = binLatitude;
  let selectedBinLongitude = binLongitude;

  let currentRoute = null;
  let selectedMarker = null;

  // -----------------------------
  // Distance formatting
  // -----------------------------

  function formatDistance(distance) {
    if (distance >= 1000) {
      return `${(distance / 1000).toFixed(1)} km`;
    }

    return `${Math.round(distance)} m`;
  }

  // -----------------------------
  // Create the map
  // -----------------------------

  function createMap() {
    const newMap = L.map("map").setView(
      [currentUserLatitude, currentUserLongitude],
      17,
    );

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(newMap);

    return newMap;
  }

  const map = createMap();

  // -----------------------------
  // Map icons
  // -----------------------------

  function createIcons() {
    const userIcon = L.divIcon({
      className: "custom-marker",
      html: `
        <div class="user-location">
          <div class="user-dot"></div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });

    const binIcon = L.divIcon({
      className: "custom-marker",
      html: '<div class="bin-marker">🗑️</div>',
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });

    const selectedBinIcon = L.divIcon({
      className: "custom-marker",
      html: '<div class="bin-marker selected-bin">🗑️</div>',
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });

    return {
      userIcon,
      binIcon,
      selectedBinIcon,
    };
  }

  const { userIcon, binIcon, selectedBinIcon } = createIcons();

  // -----------------------------
  // User location marker
  // -----------------------------

  const userAccuracyCircle = L.circle(
    [currentUserLatitude, currentUserLongitude],
    {
      radius: 35,
      color: "#0078d4",
      fillColor: "#0078d4",
      fillOpacity: 0.16,
      weight: 2,
    },
  ).addTo(map);

  const userMarker = L.marker([currentUserLatitude, currentUserLongitude], {
    icon: userIcon,
    zIndexOffset: 1000,
  })
    .addTo(map)
    .bindPopup("<strong>You are here</strong>");

  // Keep the blue dot updated while the page is open.
  if (navigator.geolocation) {
    navigator.geolocation.watchPosition(
      function (position) {
        currentUserLatitude = position.coords.latitude;
        currentUserLongitude = position.coords.longitude;

        const updatedLocation = [currentUserLatitude, currentUserLongitude];

        userMarker.setLatLng(updatedLocation);
        userAccuracyCircle.setLatLng(updatedLocation);
        userAccuracyCircle.setRadius(Math.max(position.coords.accuracy, 20));

        sessionStorage.setItem(
          "findMyBinLocation",
          JSON.stringify({
            latitude: currentUserLatitude,
            longitude: currentUserLongitude,
          }),
        );
      },

      function (error) {
        console.error(
          "Live location update failed:",
          error.code,
          error.message,
        );
      },

      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 5000,
      },
    );
  }

  // -----------------------------
  // Create bin markers
  // -----------------------------

  let binMarkers = [];

  function createBinMarkers(bins) {
    binMarkers.forEach((marker) => map.removeLayer(marker));
    binMarkers = [];

    bins.forEach(function (item, index) {
      const wasteBin = item.bin;
      const binDistance = Math.round(item.distance);

      const marker = L.marker([wasteBin.lat, wasteBin.lon], {
        icon: index === 0 ? selectedBinIcon : binIcon,
      })
        .addTo(map)
        .bindPopup(
          `<strong>🗑️ Public Bin</strong><br>${formatDistance(binDistance)} away`,
        );

      marker.on("click", function () {
        if (selectedMarker) {
          selectedMarker.setIcon(binIcon);
        }

        marker.setIcon(selectedBinIcon);
        selectedMarker = marker;

        selectedBinLatitude = wasteBin.lat;
        selectedBinLongitude = wasteBin.lon;

        document.getElementById("resultHeading").innerText =
          "Nearest Public Bin";

        document.getElementById("straightLineDistance").innerText =
          `${formatDistance(binDistance)} away`;

        loadWalkingRoute(selectedBinLatitude, selectedBinLongitude);
      });

      if (index === 0) {
        selectedMarker = marker;
        marker.openPopup();
      }

      binMarkers.push(marker);
    });
  }

  createBinMarkers(nearestBins);

  // -----------------------------
  // Walking route
  // -----------------------------

  async function loadWalkingRoute(destinationLatitude, destinationLongitude) {
    const walkingRoute = document.getElementById("walkingRoute");

    walkingRoute.classList.add("walking-loading");
    walkingRoute.classList.remove("walking-route-result");
    walkingRoute.innerText = "Loading route...";

    try {
      const response = await fetch("/walking-route", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_lat: currentUserLatitude,
          user_lon: currentUserLongitude,
          bin_lat: destinationLatitude,
          bin_lon: destinationLongitude,
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

      const routeOutline = L.geoJSON(routeData, {
        style: {
          color: "#ffffff",
          weight: 10,
          opacity: 0.95,
          lineCap: "round",
          lineJoin: "round",
        },
      }).addTo(map);

      const routeLine = L.geoJSON(routeData, {
        style: {
          color: "#23844b",
          weight: 6,
          opacity: 1,
          dashArray: "6, 6",
          lineCap: "round",
          lineJoin: "round",
        },
      }).addTo(map);

      currentRoute = L.layerGroup([routeOutline, routeLine]).addTo(map);

      map.fitBounds(routeLine.getBounds(), {
        padding: [40, 40],
      });

      const summary = routeData.features[0].properties.summary;

      const walkingMinutes = Math.round(summary.duration / 60);

      const displayedMinutes = Math.max(1, walkingMinutes);

      walkingRoute.classList.remove("walking-loading");
      walkingRoute.classList.add("walking-route-result");
      walkingRoute.innerText = `${displayedMinutes} min walk`;
    } catch (error) {
      console.error("Walking route error:", error);

      map.fitBounds(
        [
          [currentUserLatitude, currentUserLongitude],
          [destinationLatitude, destinationLongitude],
        ],
        {
          padding: [40, 40],
        },
      );

      walkingRoute.classList.remove("walking-loading");
      walkingRoute.classList.remove("walking-route-result");

      walkingRoute.innerText =
        "Walking route unavailable. Use Google Maps for directions.";
    }
  }

  loadWalkingRoute(selectedBinLatitude, selectedBinLongitude);

  // -----------------------------
  // Google Maps button
  // -----------------------------

  function setupNavigationButton() {
    const navigateButton = document.getElementById("navigateButton");

    navigateButton.addEventListener("click", function () {
      const mapsUrl =
        "https://www.google.com/maps/dir/?api=1" +
        `&origin=${currentUserLatitude},${currentUserLongitude}` +
        `&destination=${selectedBinLatitude},${selectedBinLongitude}` +
        "&travelmode=walking";

      window.open(mapsUrl, "_blank");
    });
  }

  function refreshNearbyBins(button) {
    if (!navigator.geolocation) {
      alert("Geolocation is not supported by your browser.");
      return;
    }

    const originalButtonContent = button.innerHTML;

    button.disabled = true;
    button.innerText = "Updating...";

    navigator.geolocation.getCurrentPosition(
      async function (position) {
        currentUserLatitude = position.coords.latitude;
        currentUserLongitude = position.coords.longitude;

        const updatedLocation = [currentUserLatitude, currentUserLongitude];

        userMarker.setLatLng(updatedLocation);
        userAccuracyCircle.setLatLng(updatedLocation);
        userAccuracyCircle.setRadius(Math.max(position.coords.accuracy, 20));

        sessionStorage.setItem(
          "findMyBinLocation",
          JSON.stringify({
            latitude: currentUserLatitude,
            longitude: currentUserLongitude,
          }),
        );

        try {
          const response = await fetch("/nearby-bins", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              latitude: currentUserLatitude,
              longitude: currentUserLongitude,
            }),
          });

          const data = await response.json();

          if (!response.ok) {
            throw new Error(
              data.error || "Nearby bins could not be refreshed.",
            );
          }

          if (!data.nearestBins || data.nearestBins.length === 0) {
            throw new Error("No nearby public bins were found.");
          }

          createBinMarkers(data.nearestBins);

          const nearestBin = data.nearestBins[0];
          const nearestDistance = Math.round(nearestBin.distance);

          selectedBinLatitude = nearestBin.bin.lat;
          selectedBinLongitude = nearestBin.bin.lon;

          document.getElementById("resultHeading").innerText =
            "Nearest Public Bin";

          document.getElementById("straightLineDistance").innerText =
            `${formatDistance(nearestDistance)} away`;

          await loadWalkingRoute(selectedBinLatitude, selectedBinLongitude);
        } catch (error) {
          console.error("Nearby-bin refresh failed:", error);
          alert(error.message);
        } finally {
          button.disabled = false;
          button.innerHTML = originalButtonContent;
        }
      },

      function (error) {
        console.error("Location refresh failed:", error.code, error.message);

        alert("Unable to update your location.");

        button.disabled = false;
        button.innerHTML = originalButtonContent;
      },

      {
        enableHighAccuracy: true,
        timeout: 15000,
        maximumAge: 5000,
      },
    );
  }

  // -----------------------------
  // Locate again button
  // -----------------------------

  function setupLocateAgainButton() {
    const locateAgainButton = document.getElementById("locateAgainButton");

    locateAgainButton.addEventListener("click", function () {
      refreshNearbyBins(locateAgainButton);
    });
  }

  // -----------------------------
  // Copy coordinates button
  // -----------------------------

  function setupCopyCoordinatesButton() {
    const copyButton = document.getElementById("copyCoordinatesButton");

    const originalButtonContent = copyButton.innerHTML;

    copyButton.addEventListener("click", async function () {
      const coordinates = `${selectedBinLatitude}, ${selectedBinLongitude}`;

      try {
        await navigator.clipboard.writeText(coordinates);

        copyButton.disabled = true;
        copyButton.innerText = "Copied!";

        setTimeout(function () {
          copyButton.disabled = false;
          copyButton.innerHTML = originalButtonContent;
        }, 2000);
      } catch (error) {
        console.error("Clipboard error:", error);
        alert("Unable to copy coordinates.");
      }
    });
  }

  setupNavigationButton();
  setupLocateAgainButton();
  setupCopyCoordinatesButton();
}
