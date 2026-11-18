const VISIBLE_NEARBY_BINS = 2;

let selectedBinType = "public";

window.addEventListener("pageshow", function (event) {
  if (event.persisted) {
    window.location.reload();
  }
});

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

// -----------------------------
// Filter Buttons
// -----------------------------

function setupFilterButtons() {
  const filterAll = document.getElementById("filterAll");
  const filterPublic = document.getElementById("filterPublic");
  const filterRecycling = document.getElementById("filterRecycling");

  const filterButtons = [filterAll, filterPublic, filterRecycling];

  filterAll.addEventListener("click", function () {
    selectedBinType = "all";
    document.getElementById("binType").value = "all";
    filterButtons.forEach((button) => {
      button.classList.remove("active");
    });
    filterAll.classList.add("active");
  });

  filterPublic.addEventListener("click", function () {
    selectedBinType = "public";
    document.getElementById("binType").value = "public";
    filterButtons.forEach((button) => {
      button.classList.remove("active");
    });
    filterPublic.classList.add("active");
  });

  filterRecycling.addEventListener("click", function () {
    selectedBinType = "recycling";
    document.getElementById("binType").value = "recycling";
    filterButtons.forEach((button) => {
      button.classList.remove("active");
    });
    filterRecycling.classList.add("active");
  });
}

setupFilterButtons();

function setupManualLocationSearch() {
  const toggle = document.getElementById("manualSearchToggle");
  const panel = document.getElementById("manualSearchPanel");
  const input = document.getElementById("manualLocationInput");
  const searchButton = document.getElementById("manualSearchButton");
  const errorMessage = document.getElementById("manualSearchError");
  const loadingMessage = document.getElementById("loading");
  const form = document.querySelector("form");

  function showError(message) {
    errorMessage.textContent = message;
    errorMessage.hidden = !message;
  }

  toggle.addEventListener("click", function () {
    const willOpen = panel.hidden;

    panel.hidden = !willOpen;
    toggle.setAttribute("aria-expanded", String(willOpen));

    if (willOpen) {
      input.focus();
    } else {
      showError("");
    }
  });

  async function searchLocation() {
    const query = input.value.trim();

    if (query.length < 3) {
      showError("Enter an address, area or Eircode.");
      input.focus();
      return;
    }

    const originalButtonText = searchButton.innerText;

    showError("");
    searchButton.disabled = true;
    searchButton.innerText = "Searching...";

    try {
      const response = await fetch("/geocode-location", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });
      const location = await response.json();

      if (!response.ok) {
        throw new Error(location.error || "That location could not be found.");
      }

      document.getElementById("latitude").value = location.latitude;
      document.getElementById("longitude").value = location.longitude;

      sessionStorage.setItem(
        "findMyBinLocation",
        JSON.stringify({
          latitude: location.latitude,
          longitude: location.longitude,
        }),
      );

      loadingMessage.style.display = "block";
      form.submit();
    } catch (error) {
      console.error("Manual location search failed:", error);
      showError(error.message);
      searchButton.disabled = false;
      searchButton.innerText = originalButtonText;
    }
  }

  searchButton.addEventListener("click", searchLocation);

  input.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      searchLocation();
    }
  });
}

setupManualLocationSearch();

// Restore the saved coordinates without automatically searching again.
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

    document.getElementById("latitude").value = location.latitude;
    document.getElementById("longitude").value = location.longitude;
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
    binType,
  } = window.findMyBinData;

  const binDisplay =
    binType === "recycling"
      ? {
          label: "Recycling Bin",
          heading: "Nearest Recycling Bin",
          nearbyHeading: "Nearby Recycling Bins",
          icon: "♻️",
        }
      : binType === "all"
        ? {
            label: "Bin",
            heading: "Nearest Bin",
            nearbyHeading: "Nearby Bins",
            icon: "📍",
          }
        : {
            label: "Public Bin",
            heading: "Nearest Public Bin",
            nearbyHeading: "Nearby Public Bins",
            icon: "🗑️",
          };

  function updateResultHeadings() {
    const resultHeading = document.getElementById("resultHeading");
    const nearbyBinsHeading = document.getElementById("nearbyBinsHeading");

    if (resultHeading) {
      resultHeading.innerText = binDisplay.heading;
    }

    if (nearbyBinsHeading) {
      nearbyBinsHeading.innerText = binDisplay.nearbyHeading;
    }
  }

  let currentUserLatitude = initialUserLatitude;
  let currentUserLongitude = initialUserLongitude;

  let selectedBinLatitude = binLatitude;
  let selectedBinLongitude = binLongitude;

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

  const recyclingMaterialLabels = {
    "recycling:aluminium": "Aluminium",
    "recycling:batteries": "Batteries",
    "recycling:cans": "Cans",
    "recycling:clothes": "Clothes",
    "recycling:glass": "Glass",
    "recycling:glass_bottles": "Glass bottles",
    "recycling:green_waste": "Garden waste",
    "recycling:metal": "Metal",
    "recycling:paper": "Paper",
    "recycling:plastic": "Plastic",
    "recycling:plastic_bottles": "Plastic bottles",
    "recycling:waste_oil": "Waste oil",
  };

  function getAcceptedMaterials(tags = {}) {
    if (tags.accepted_materials) {
      return tags.accepted_materials
        .replace(/^Materials accepted:\s*/i, "")
        .replace(/\bAluminiu\b/g, "Aluminium")
        .trim();
    }

    const materials = Object.entries(recyclingMaterialLabels)
      .filter(function ([tag]) {
        return tags[tag] === "yes";
      })
      .map(function ([tag, label]) {
        return label;
      });

    return [...new Set(materials)].join(", ");
  }

  function getBinDetails(wasteBin) {
    const tags = wasteBin.tags || {};
    const isRecycling = tags.amenity === "recycling";

    return {
      isRecycling,
      name: isRecycling && tags.name ? tags.name : "",
      materials: isRecycling ? getAcceptedMaterials(tags) : "",
    };
  }

  function updateResultBinInfo(wasteBin) {
    const details = getBinDetails(wasteBin);
    const info = document.getElementById("resultBinInfo");
    const name = document.getElementById("resultBinName");
    const materials = document.getElementById("resultBinMaterials");
    const resultIcon = document.querySelector("#resultBinIcon i");

    resultIcon.className = details.isRecycling
      ? "bi bi-recycle"
      : "bi bi-trash3-fill";

    if (!details.name && !details.materials) {
      info.hidden = true;
      name.textContent = "";
      materials.textContent = "";
      return;
    }

    name.textContent = details.name;
    name.hidden = !details.name;
    materials.textContent = details.materials
      ? `Accepts: ${details.materials}`
      : "";
    materials.hidden = !details.materials;
    info.hidden = false;
  }

  function renderNearbyBinsList(bins) {
    const container = document.getElementById("nearbyBinsList");

    container.innerHTML = "";

    bins.slice(0, VISIBLE_NEARBY_BINS).forEach(function (item, index) {
      const binDistance = Math.round(item.distance);

      const card = document.createElement("div");
      card.className = "nearby-bin-item" + (index === 0 ? " active" : "");
      const details = getBinDetails(item.bin);

      const binInfo = document.createElement("div");
      binInfo.className = "nearby-bin-info";

      const binTitle = document.createElement("div");
      binTitle.className = "nearby-bin-title";

      const typeIcon = document.createElement("i");
      typeIcon.className = details.isRecycling
        ? "bi bi-recycle nearby-bin-type-icon recycling-type-icon"
        : "bi bi-trash3-fill nearby-bin-type-icon public-type-icon";
      typeIcon.setAttribute("aria-hidden", "true");

      const titleText = document.createElement("span");
      titleText.textContent =
        details.name || (details.isRecycling ? "Recycling Bin" : "Public Bin");

      binTitle.append(typeIcon, titleText);
      binInfo.appendChild(binTitle);

      if (details.materials) {
        const materials = document.createElement("div");
        materials.className = "nearby-bin-materials";
        materials.textContent = `Accepts: ${details.materials}`;
        binInfo.appendChild(materials);
      }

      const routeInfo = document.createElement("div");
      routeInfo.className = "nearby-bin-route";

      const distance = document.createElement("div");
      distance.className = "nearby-bin-distance";
      distance.textContent = formatDistance(binDistance);

      const routeLabel = document.createElement("div");
      routeLabel.className = "nearby-bin-label";
      routeLabel.textContent = "Tap to select";

      routeInfo.append(distance, routeLabel);

      const arrow = document.createElement("span");
      arrow.className = "nearby-bin-arrow";
      arrow.textContent = "›";

      card.append(binInfo, routeInfo, arrow);

      card.addEventListener("click", function () {
        binMarkers[index].fire("click");

        document.querySelectorAll(".nearby-bin-item").forEach(function (item) {
          item.classList.remove("active");
        });

        card.classList.add("active");
      });

      container.appendChild(card);
    });
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

  function createUserIcon() {
    return L.divIcon({
      className: "custom-marker",
      html: `
        <div class="user-location">
          <div class="user-dot"></div>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }

  function createBinIcon(amenity, selected = false) {
    const isRecycling = amenity === "recycling";
    const typeClass = isRecycling
      ? "recycling-marker"
      : "public-bin-marker";
    const symbolClass = isRecycling
      ? "bi bi-recycle"
      : "bi bi-trash3-fill";
    const markerSize = selected ? 30 : 26;
    const markerAnchor = markerSize / 2;

    return L.divIcon({
      className: "custom-marker",
      html: `
        <div class="bin-marker ${typeClass}${selected ? " selected-bin" : ""}">
          <i class="${symbolClass}" aria-hidden="true"></i>
        </div>
      `,
      iconSize: [markerSize, markerSize],
      iconAnchor: [markerAnchor, markerAnchor],
    });
  }

  const userIcon = createUserIcon();

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
    selectedMarker = null;

    bins.forEach(function (item, index) {
      const wasteBin = item.bin;
      const binDistance = Math.round(item.distance);
      const amenity = wasteBin.tags?.amenity;
      const normalBinIcon = createBinIcon(amenity);
      const selectedBinIcon = createBinIcon(amenity, true);
      const popupLabel =
        amenity === "recycling"
          ? "Recycling Bin"
          : "Public Bin";
      const marker = L.marker([wasteBin.lat, wasteBin.lon], {
        icon: index === 0 ? selectedBinIcon : normalBinIcon,
      })
        .addTo(map)
        .bindPopup(
          `<span>${
            binType === "all"
              ? popupLabel
              : binDisplay.label
          } · ${formatDistance(binDistance)}</span>`,
          {
            className: "bin-popup",
            closeButton: false,
          },
        );

      marker.normalBinIcon = normalBinIcon;
      marker.selectedBinIcon = selectedBinIcon;

      marker.on("click", function () {
        if (selectedMarker) {
          selectedMarker.setIcon(selectedMarker.normalBinIcon);
        }

        marker.setIcon(marker.selectedBinIcon);
        selectedMarker = marker;

        selectedBinLatitude = wasteBin.lat;
        selectedBinLongitude = wasteBin.lon;

        document.getElementById("resultHeading").innerText = binDisplay.heading;
        document.getElementById("nearbyBinsHeading").innerText =
          binDisplay.nearbyHeading;

        document.getElementById("straightLineDistance").innerText =
          `${formatDistance(binDistance)} away`;

        updateResultBinInfo(wasteBin);

        loadWalkingRoute(selectedBinLatitude, selectedBinLongitude);
      });

      if (index === 0) {
        selectedMarker = marker;
        marker.openPopup();
        updateResultBinInfo(wasteBin);
      }

      binMarkers.push(marker);
    });
  }

  createBinMarkers(nearestBins);
  renderNearbyBinsList(nearestBins);
  updateResultHeadings();

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

      // Keep the user and destination visible without drawing a route line.
      map.fitBounds([
        [currentUserLatitude, currentUserLongitude],
        [destinationLatitude, destinationLongitude],
      ], {
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
              bin_type: binType,
            }),
          });

          const data = await response.json();

          if (!response.ok) {
            throw new Error(
              data.error || "Nearby bins could not be refreshed.",
            );
          }

          if (!data.nearestBins || data.nearestBins.length === 0) {
            throw new Error("No nearby matching bins were found.");
          }

          createBinMarkers(data.nearestBins);
          renderNearbyBinsList(data.nearestBins);

          const nearestBin = data.nearestBins[0];
          const nearestDistance = Math.round(nearestBin.distance);

          selectedBinLatitude = nearestBin.bin.lat;
          selectedBinLongitude = nearestBin.bin.lon;

          document.getElementById("resultHeading").innerText =
            binDisplay.heading;

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
