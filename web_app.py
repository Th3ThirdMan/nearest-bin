import csv
import json
import math
import os
import threading
import time
from functools import lru_cache

import requests
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

from app import (
    find_nearest_bins,
    get_bins,
    headers,
    search_radius,
    url,
)

load_dotenv()
ORS_API_KEY = os.getenv("ORS_API_KEY")
GEOCODING_SEARCH_URL = os.getenv(
    "GEOCODING_SEARCH_URL",
    "https://nominatim.openstreetmap.org/search",
)

app = Flask(__name__)


RECYCLING_SEARCH_RADIUS = 10000
NOMINATIM_REQUEST_INTERVAL = 1.0

_nominatim_lock = threading.Lock()
_last_nominatim_request_at = 0.0


ASSET_LINKS = [
    {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.davidkennedy.findmybin",
            "sha256_cert_fingerprints": [
                "FC:57:B5:2A:56:F8:CF:38:DA:DE:C0:0C:73:FC:92:8E:93:AE:26:47:B9:5C:88:21:A2:06:23:41:9B:98:0C:A0",
                "B7:FA:16:50:DD:D2:DF:B5:C8:2F:83:6F:E9:A4:70:3D:89:38:88:3D:28:6E:DE:FD:4F:B9:98:97:E3:59:81:ED",
                "98:29:B5:3A:BA:C6:91:97:EA:F0:03:10:CD:77:F5:9E:FA:88:18:07:BB:9A:86:68:BA:22:2B:14:4E:00:7B:20",
            ],
        },
    }
]


# --------------------------------------------------
# Dublin City Council public-bin data
# --------------------------------------------------

DCC_DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dcc_public_bin_locations.geojson",
)

DCC_RECYCLING_DATA_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dcc_recycling_centres.geojson",
)

DCC_BOTTLE_BANKS_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dcc_bottle_banks.csv",
)

FINGAL_PUBLIC_BINS_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "fingal_public_bins.geojson",
)

FINGAL_BRING_BANKS_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "fingal_bring_banks.geojson",
)

FINGAL_RECYCLING_CENTRES_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "fingal_recycling_centres.geojson",
)

DLR_PUBLIC_BINS_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dlr_public_bins.csv",
)

DLR_BRING_BANKS_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dlr_bring_banks.geojson",
)

DLR_RECYCLING_CENTRES_FILE = os.path.join(
    os.path.dirname(__file__),
    "data",
    "dlr_recycling_centres.geojson",
)


def load_dcc_bins():
    try:
        with open(DCC_DATA_FILE, "r", encoding="utf-8") as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if (
                geometry.get("type") != "Point"
                or len(coordinates) < 2
            ):
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"dcc-{properties.get('Bin_ID', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "waste_basket",
                    "source": "Dublin City Council",
                    "bin_type": properties.get("Bin_Type"),
                    "electoral_area": properties.get("Electoral_Area"),
                },
            })

        print(f"DCC bins loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load DCC bin data: {error}")
        return []


DCC_BINS = load_dcc_bins()


def load_dcc_recycling_bins():
    try:
        with open(
            DCC_RECYCLING_DATA_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"dcc-recycling-{len(bins)}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "recycling",
                    "source": "Dublin City Council",
                    "name": properties.get("Name"),
                    "address": properties.get("Address"),
                    "eircode": properties.get("Eircode"),
                },
            })

        print(f"DCC recycling centres loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load DCC recycling data: {error}")
        return []


DCC_RECYCLING_BINS = load_dcc_recycling_bins()


def load_dcc_bottle_banks():
    """Load DCC/Glassco bottle-bank coordinates for outage coverage."""
    try:
        with open(
            DCC_BOTTLE_BANKS_FILE,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            rows = csv.DictReader(file)
            bins = []

            for index, row in enumerate(rows, start=1):
                latitude = float(row["Latitude"])
                longitude = float(row["Longitude"])

                # Reject obvious source-data coordinate errors outside Dublin.
                if not (
                    53.20 <= latitude <= 53.50
                    and -6.45 <= longitude <= -6.05
                ):
                    continue

                facility_id = row.get("Facility ID") or index
                address_parts = [
                    row.get("Street"),
                    row.get("Locality Name"),
                    row.get("PostCode Name"),
                ]

                bins.append({
                    "id": f"dcc-bottle-bank-{facility_id}",
                    "lat": latitude,
                    "lon": longitude,
                    "tags": {
                        "amenity": "recycling",
                        "source": "Dublin City Council / Glassco",
                        "name": row.get("Facility Name"),
                        "address": ", ".join(
                            part for part in address_parts if part
                        ),
                        "accepted_materials": row.get("More Info"),
                        "facility_type": "bottle_bank",
                    },
                })

        print(f"DCC bottle banks loaded: {len(bins)}")
        return bins

    except (
        OSError,
        csv.Error,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(f"Could not load DCC bottle-bank data: {error}")
        return []


DCC_BOTTLE_BANKS = load_dcc_bottle_banks()


def load_fingal_public_bins():
    """Load Fingal public litter bins, excluding dog-only bins."""
    try:
        with open(FINGAL_PUBLIC_BINS_FILE, "r", encoding="utf-8") as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            # Fingal records dog-only bins in the same dataset. They are not
            # suitable as general public litter bins.
            bin_type = properties.get("type")
            if bin_type == "dog_bin":
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"fingal-{properties.get('bin_id', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "waste_basket",
                    "source": "Fingal County Council",
                    "bin_type": bin_type,
                    "park_name": properties.get("ParkName"),
                    "electoral_area": properties.get("LEA"),
                    "townland": properties.get("Townland"),
                },
            })

        print(f"Fingal public bins loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load Fingal public-bin data: {error}")
        return []


def load_fingal_bring_banks():
    """Load official Fingal bring-bank locations and accepted materials."""
    try:
        with open(FINGAL_BRING_BANKS_FILE, "r", encoding="utf-8") as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"fingal-bring-{properties.get('Id_No', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "recycling",
                    "source": "Fingal County Council",
                    "name": properties.get("Bring_Bank_Site"),
                    "address": properties.get("Full_Address_of_Bring_Bank_Loca"),
                    "accepted_materials": properties.get(
                        "What_it_Takes_in_Bring_Banks__e"
                    ),
                    "facility_type": "bottle_bank",
                    "ownership": properties.get("Ownership_FCC_Private"),
                },
            })

        print(f"Fingal bring banks loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load Fingal bring-bank data: {error}")
        return []


def load_fingal_recycling_centres():
    """Load Fingal's full-service recycling centres."""
    try:
        with open(
            FINGAL_RECYCLING_CENTRES_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"fingal-recycling-{properties.get('ID', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "recycling",
                    "source": "Fingal County Council",
                    "name": properties.get("NAME"),
                    "address": properties.get("ADDRESS"),
                    "eircode": properties.get("Eircode"),
                    "telephone": properties.get("Telephone"),
                    "facility_type": "recycling_centre",
                },
            })

        print(f"Fingal recycling centres loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load Fingal recycling-centre data: {error}")
        return []


FINGAL_PUBLIC_BINS = load_fingal_public_bins()
FINGAL_BRING_BANKS = load_fingal_bring_banks()
FINGAL_RECYCLING_CENTRES = load_fingal_recycling_centres()


def load_dlr_public_bins():
    """Load DLR's published public-bin file, last updated in 2016."""
    try:
        with open(
            DLR_PUBLIC_BINS_FILE,
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            bins = []

            for index, row in enumerate(csv.DictReader(file), start=1):
                bins.append({
                    "id": f"dlr-{row.get('Bin no.') or index}",
                    "lat": float(row["Latitude"]),
                    "lon": float(row["Longitude"]),
                    "tags": {
                        "amenity": "waste_basket",
                        "source": (
                            "Dún Laoghaire–Rathdown County Council"
                        ),
                        "description": row.get("Description"),
                        "data_last_updated": "2016",
                    },
                })

        print(f"DLR public bins loaded: {len(bins)}")
        return bins

    except (
        OSError,
        csv.Error,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        print(f"Could not load DLR public-bin data: {error}")
        return []


def load_dlr_bring_banks():
    """Load DLR's 2025 bring-bank locations and accepted materials."""
    try:
        with open(DLR_BRING_BANKS_FILE, "r", encoding="utf-8") as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            lon, lat = coordinates[:2]
            accepted_materials = [
                label
                for field, label in (
                    ("glass", "Glass"),
                    ("cans", "Cans"),
                    ("textiles", "Textiles"),
                )
                if str(properties.get(field, "")).strip().casefold() == "yes"
            ]

            bins.append({
                "id": f"dlr-bring-{properties.get('FID', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "recycling",
                    "source": "Dún Laoghaire–Rathdown County Council",
                    "name": properties.get("centre"),
                    "address": properties.get("sitelocati"),
                    "accepted_materials": ", ".join(accepted_materials),
                    "facility_type": "bottle_bank",
                    "opening": (
                        "24 hours"
                        if str(properties.get("f24hours", ""))
                        .strip()
                        .casefold() == "yes"
                        else None
                    ),
                },
            })

        print(f"DLR bring banks loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load DLR bring-bank data: {error}")
        return []


def load_dlr_recycling_centres():
    """Load DLR's 2025 full-service recycling centres."""
    try:
        with open(
            DLR_RECYCLING_CENTRES_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            geojson = json.load(file)

        bins = []

        for feature in geojson.get("features", []):
            geometry = feature.get("geometry", {})
            properties = feature.get("properties", {})
            coordinates = geometry.get("coordinates", [])

            if geometry.get("type") != "Point" or len(coordinates) < 2:
                continue

            lon, lat = coordinates[:2]

            bins.append({
                "id": f"dlr-recycling-{properties.get('objectid', len(bins))}",
                "lat": float(lat),
                "lon": float(lon),
                "tags": {
                    "amenity": "recycling",
                    "source": "Dún Laoghaire–Rathdown County Council",
                    "name": properties.get("name"),
                    "website": properties.get("url"),
                    "facility_type": "recycling_centre",
                },
            })

        print(f"DLR recycling centres loaded: {len(bins)}")
        return bins

    except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
        print(f"Could not load DLR recycling-centre data: {error}")
        return []


DLR_PUBLIC_BINS = load_dlr_public_bins()
DLR_BRING_BANKS = load_dlr_bring_banks()
DLR_RECYCLING_CENTRES = load_dlr_recycling_centres()


def distance_metres(lat1, lon1, lat2, lon2):
    earth_radius = 6371000

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius * c


def get_official_public_bins_nearby(user_lat, user_lon):
    nearby = []

    for bin_item in DCC_BINS + FINGAL_PUBLIC_BINS + DLR_PUBLIC_BINS:
        distance = distance_metres(
            user_lat,
            user_lon,
            bin_item["lat"],
            bin_item["lon"],
        )

        if distance <= search_radius:
            nearby.append(bin_item)

    return nearby


def get_official_recycling_bins_nearby(user_lat, user_lon):
    nearby = []

    # Bring banks contain the broad mapped coverage. The smaller recycling-
    # centre files add full-service sites, with close duplicates removed.
    official_bins = merge_recycling_bins(
        DCC_RECYCLING_BINS,
        DCC_BOTTLE_BANKS,
    )
    official_bins = merge_recycling_bins(
        FINGAL_RECYCLING_CENTRES,
        official_bins,
    )
    official_bins = merge_recycling_bins(
        FINGAL_BRING_BANKS,
        official_bins,
    )
    official_bins = merge_recycling_bins(
        DLR_RECYCLING_CENTRES,
        official_bins,
    )
    official_bins = merge_recycling_bins(
        DLR_BRING_BANKS,
        official_bins,
    )

    for bin_item in official_bins:
        distance = distance_metres(
            user_lat,
            user_lon,
            bin_item["lat"],
            bin_item["lon"],
        )

        if distance <= RECYCLING_SEARCH_RADIUS:
            nearby.append(bin_item)

    return nearby


def describe_data_source(data, osm_bins, official_bins):
    """Build a precise attribution label for the records in a result."""
    authorities = []
    source_values = {
        bin_item.get("tags", {}).get("source", "")
        for bin_item in official_bins
    }

    if any(source.startswith("Dublin City Council") for source in source_values):
        authorities.append("Dublin City Council")

    if "Fingal County Council" in source_values:
        authorities.append("Fingal County Council")

    if "Dún Laoghaire–Rathdown County Council" in source_values:
        authorities.append("Dún Laoghaire–Rathdown County Council")

    sources = []

    if (
        data is not None
        and data.get("source") == "live"
        and osm_bins
    ):
        sources.append("OSM")

    sources.extend(authorities)

    if sources:
        return " + ".join(sources)

    if data is not None:
        return data.get("source")

    return None


@app.template_filter("data_attribution")
def data_attribution(data_source):
    """Format source labels for display beneath a result."""
    if not data_source:
        return ""

    labels = []

    if "OSM" in data_source:
        labels.append("OpenStreetMap contributors")

    for authority in (
        "Dublin City Council",
        "Fingal County Council",
        "Dún Laoghaire–Rathdown County Council",
    ):
        if authority in data_source:
            labels.append(authority)

    if not labels:
        return ""

    if len(labels) == 1:
        source_text = labels[0]
    else:
        source_text = ", ".join(labels[:-1]) + f" and {labels[-1]}"

    council_credit = any("Council" in label for label in labels)
    licence_text = " (CC BY 4.0)" if council_credit else ""

    return f"Data © {source_text}{licence_text}."


def merge_public_bins(osm_bins, dcc_bins):
    """
    Prefer official DCC records when an OSM bin appears to represent
    the same physical bin.

    OSM bins within 8 metres of a DCC bin are treated as duplicates.
    """

    merged = list(dcc_bins)

    for osm_bin in osm_bins:
        osm_lat = osm_bin.get("lat")
        osm_lon = osm_bin.get("lon")

        if osm_lat is None or osm_lon is None:
            continue

        # Recycling points are a different amenity and must not be removed
        # merely because they happen to be close to a public-bin record.
        if osm_bin.get("tags", {}).get("amenity") == "recycling":
            merged.append(osm_bin)
            continue

        duplicate = False

        for dcc_bin in dcc_bins:
            distance = distance_metres(
                osm_lat,
                osm_lon,
                dcc_bin["lat"],
                dcc_bin["lon"],
            )

            if distance <= 8:
                duplicate = True
                break

        if not duplicate:
            merged.append(osm_bin)

    return merged


def merge_recycling_bins(osm_bins, dcc_bins):
    """Prefer official recycling centres over nearby duplicate OSM records."""
    merged = list(dcc_bins)

    for osm_bin in osm_bins:
        osm_lat = osm_bin.get("lat")
        osm_lon = osm_bin.get("lon")

        if osm_lat is None or osm_lon is None:
            continue

        if osm_bin.get("tags", {}).get("amenity") != "recycling":
            merged.append(osm_bin)
            continue

        duplicate = any(
            distance_metres(
                osm_lat,
                osm_lon,
                dcc_bin["lat"],
                dcc_bin["lon"],
            ) <= 30
            for dcc_bin in dcc_bins
        )

        if not duplicate:
            merged.append(osm_bin)

    return merged


def merge_with_official_bins(osm_bins, bin_type, user_lat, user_lon):
    public_bins = []
    recycling_bins = []
    bins = list(osm_bins)

    if bin_type in ("public", "all"):
        public_bins = get_official_public_bins_nearby(user_lat, user_lon)
        bins = merge_public_bins(bins, public_bins)

    if bin_type in ("recycling", "all"):
        recycling_bins = get_official_recycling_bins_nearby(
            user_lat,
            user_lon,
        )
        bins = merge_recycling_bins(bins, recycling_bins)

    return bins, public_bins, recycling_bins


def get_search_radius(bin_type):
    if bin_type == "recycling":
        return RECYCLING_SEARCH_RADIUS

    return search_radius


def official_results_cover_search(
    bin_type,
    official_public_bins,
    official_recycling_bins,
):
    """Avoid a slow live lookup when official data covers the request."""
    if bin_type == "public":
        return bool(official_public_bins)

    if bin_type == "recycling":
        return bool(official_recycling_bins)

    return bool(official_public_bins and official_recycling_bins)


def build_bins_query(bin_type, user_lat, user_lon):
    if bin_type == "all":
        return f"""
        [out:json];
        (
          node["amenity"="waste_basket"]
          (around:{search_radius},{user_lat},{user_lon});

          nwr["amenity"="recycling"]
          (around:{RECYCLING_SEARCH_RADIUS},{user_lat},{user_lon});
        );
        out center;
        """

    if bin_type == "recycling":
        return f"""
        [out:json];
        nwr["amenity"="recycling"]
        (around:{RECYCLING_SEARCH_RADIUS},{user_lat},{user_lon});
        out center;
        """

    return f"""
    [out:json];
    node["amenity"="waste_basket"]
    (around:{search_radius},{user_lat},{user_lon});
    out;
    """


def normalise_osm_bins(elements):
    """Give Overpass nodes, ways and relations a common lat/lon shape."""
    bins = []

    for element in elements:
        latitude = element.get("lat")
        longitude = element.get("lon")

        if latitude is None or longitude is None:
            center = element.get("center", {})
            latitude = center.get("lat")
            longitude = center.get("lon")

        if latitude is None or longitude is None:
            continue

        normalised = dict(element)
        normalised["lat"] = latitude
        normalised["lon"] = longitude
        bins.append(normalised)

    return bins


@lru_cache(maxsize=256)
def geocode_address(query):
    """Resolve one user-submitted Irish place search through Nominatim."""
    global _last_nominatim_request_at

    with _nominatim_lock:
        elapsed = time.monotonic() - _last_nominatim_request_at
        wait_time = NOMINATIM_REQUEST_INTERVAL - elapsed

        if wait_time > 0:
            time.sleep(wait_time)

        _last_nominatim_request_at = time.monotonic()

        response = requests.get(
            GEOCODING_SEARCH_URL,
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
                "countrycodes": "ie",
                "addressdetails": 0,
            },
            headers={
                "User-Agent": (
                    "FindMyBin/1.0 "
                    "(https://findmybin.app/privacy)"
                ),
                "Referer": "https://findmybin.app/",
                "Accept-Language": "en",
            },
            timeout=(5, 12),
        )
        response.raise_for_status()
        results = response.json()

    if not isinstance(results, list) or not results:
        return None

    result = results[0]

    return {
        "latitude": float(result["lat"]),
        "longitude": float(result["lon"]),
        "displayName": result.get("display_name", query),
    }


# --------------------------------------------------
# Home
# --------------------------------------------------

@app.route("/")
def home():
    return render_template(
        "index.html",
        title="FindMyBin",
        nearest_bin=None,
        nearest_bins=[],
        nearest_distance=None,
        error_message=None,
        data_source=None,
        user_lat=None,
        user_lon=None,
    )


@app.route("/privacy")
def privacy_policy():
    return render_template("privacy.html")


@app.route("/geocode-location", methods=["POST"])
def geocode_location():
    request_data = request.get_json(silent=True) or {}
    raw_query = request_data.get("query", "")

    if not isinstance(raw_query, str):
        return jsonify({"error": "Enter a valid location."}), 400

    query = " ".join(raw_query.split())

    if len(query) < 3 or len(query) > 160:
        return jsonify({
            "error": "Enter an address, area or Eircode."
        }), 400

    try:
        result = geocode_address(query.casefold())

    except (
        KeyError,
        TypeError,
        ValueError,
        requests.RequestException,
    ) as error:
        print(f"Location search failed: {error}")
        return jsonify({
            "error": "Location search is temporarily unavailable."
        }), 503

    if result is None:
        return jsonify({
            "error": "That location could not be found in Ireland."
        }), 404

    return jsonify(result)


@app.route("/.well-known/assetlinks.json")
def asset_links():
    return jsonify(ASSET_LINKS)


# --------------------------------------------------
# Find nearest bin
# --------------------------------------------------

@app.route("/find-bin", methods=["POST"])
def find_bin():
    nearest_bin = None
    nearest_bins = []
    nearest_distance = None
    error_message = None
    data_source = None

    try:
        user_lat = float(request.form["latitude"])
        user_lon = float(request.form["longitude"])
        bin_type = request.form.get("bin_type", "public")

        print(f"Selected bin type: {bin_type}")

    except (KeyError, TypeError, ValueError):
        error_message = "Your location could not be read."

        return render_template(
            "index.html",
            title="FindMyBin",
            nearest_bin=None,
            nearest_bins=[],
            nearest_distance=None,
            error_message=error_message,
            data_source=None,
            user_lat=None,
            user_lon=None,
        )

    if bin_type not in ("public", "recycling", "all"):
        bin_type = "public"

    _, initial_public_bins, initial_recycling_bins = merge_with_official_bins(
        [],
        bin_type,
        user_lat,
        user_lon,
    )

    if official_results_cover_search(
        bin_type,
        initial_public_bins,
        initial_recycling_bins,
    ):
        data = None
    else:
        query = build_bins_query(bin_type, user_lat, user_lon)
        data = get_bins(
            url,
            query,
            headers,
            allow_cache=bin_type != "recycling",
        )

    if data is not None:
        osm_bins = normalise_osm_bins(data.get("elements", []))

        print(f"Bins returned by Overpass: {len(osm_bins)}")

        bins, official_public_bins, official_recycling_bins = (
            merge_with_official_bins(
                osm_bins,
                bin_type,
                user_lat,
                user_lon,
            )
        )

        print(f"Official public bins nearby: {len(official_public_bins)}")
        print(
            "Official recycling sites nearby: "
            f"{len(official_recycling_bins)}"
        )

        official_bins = official_public_bins + official_recycling_bins
        data_source = describe_data_source(data, osm_bins, official_bins)

        print(f"Combined bins: {len(bins)}")

        if bins:
            nearest_bins = find_nearest_bins(
                bins,
                user_lat,
                user_lon,
            )

            print(
                f"Nearest bins found: "
                f"{len(nearest_bins)}"
            )

            for index, item in enumerate(
                nearest_bins,
                start=1,
            ):
                print(
                    f"{index}: "
                    f"{item['distance']:.0f}m "
                    f"({item['bin']['lat']}, "
                    f"{item['bin']['lon']})"
                )

            nearest_bin = nearest_bins[0]["bin"]
            nearest_distance = nearest_bins[0]["distance"]

            # Only apply the old cache-distance safeguard when
            # we have no official local-authority results supplementing it.
            if (
                data_source == "cache"
                and nearest_distance is not None
                and nearest_distance > 1000
            ):
                nearest_bin = None
                nearest_distance = None

                error_message = (
                    "Live bin data is temporarily unavailable, "
                    "and the saved data is not near your current location."
                )

        else:
            result_radius = get_search_radius(bin_type)
            bin_label = "recycling bins" if bin_type == "recycling" else "bins"
            error_message = (
                f"No {bin_label} were found within "
                f"{result_radius} metres."
            )

    else:
        bins, official_public_bins, official_recycling_bins = (
            merge_with_official_bins(
                [],
                bin_type,
                user_lat,
                user_lon,
            )
        )

        if bins:
            nearest_bins = find_nearest_bins(
                bins,
                user_lat,
                user_lon,
            )

            nearest_bin = nearest_bins[0]["bin"]
            nearest_distance = nearest_bins[0]["distance"]
            data_source = describe_data_source(
                None,
                [],
                official_public_bins + official_recycling_bins,
            )
        else:
            error_message = (
                "The bin service is temporarily unavailable. "
                "Please try again."
            )

    return render_template(
        "index.html",
        title="FindMyBin",
        nearest_bin=nearest_bin,
        nearest_bins=nearest_bins,
        nearest_distance=nearest_distance,
        error_message=error_message,
        data_source=data_source,
        user_lat=user_lat,
        user_lon=user_lon,
        bin_type=bin_type,
    )


# --------------------------------------------------
# Nearby bins API
# --------------------------------------------------

@app.route("/nearby-bins", methods=["POST"])
def nearby_bins():
    request_data = request.get_json()

    if not request_data:
        return jsonify({
            "error": "No coordinates were supplied."
        }), 400

    try:
        user_lat = float(
            request_data["latitude"]
        )
        user_lon = float(
            request_data["longitude"]
        )
        bin_type = request_data.get("bin_type", "public")

    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Invalid coordinates."
        }), 400

    if bin_type not in ("public", "recycling", "all"):
        bin_type = "public"

    _, initial_public_bins, initial_recycling_bins = merge_with_official_bins(
        [],
        bin_type,
        user_lat,
        user_lon,
    )

    if official_results_cover_search(
        bin_type,
        initial_public_bins,
        initial_recycling_bins,
    ):
        data = None
    else:
        query = build_bins_query(bin_type, user_lat, user_lon)
        data = get_bins(
            url,
            query,
            headers,
            allow_cache=bin_type != "recycling",
        )

    osm_bins = []

    if data is not None:
        osm_bins = normalise_osm_bins(data.get("elements", []))

    bins, official_public_bins, official_recycling_bins = (
        merge_with_official_bins(
            osm_bins,
            bin_type,
            user_lat,
            user_lon,
        )
    )

    if not bins:
        result_radius = get_search_radius(bin_type)
        bin_label = "recycling bins" if bin_type == "recycling" else "bins"
        return jsonify({
            "error": (
                f"No {bin_label} were found within "
                f"{result_radius} metres."
            )
        }), 404

    nearest_bins = find_nearest_bins(
        bins,
        user_lat,
        user_lon,
    )

    official_bins = official_public_bins + official_recycling_bins
    data_source = describe_data_source(data, osm_bins, official_bins)

    return jsonify({
        "userLatitude": user_lat,
        "userLongitude": user_lon,
        "nearestBins": nearest_bins,
        "dataSource": data_source,
        "binType": bin_type,
    })


# --------------------------------------------------
# Walking route
# --------------------------------------------------

@app.route("/walking-route", methods=["POST"])
def walking_route():
    route_data = request.get_json()

    if not route_data:
        return {
            "error": (
                "No route coordinates were supplied."
            )
        }, 400

    try:
        user_lat = float(
            route_data["user_lat"]
        )
        user_lon = float(
            route_data["user_lon"]
        )
        bin_lat = float(
            route_data["bin_lat"]
        )
        bin_lon = float(
            route_data["bin_lon"]
        )

    except (KeyError, TypeError, ValueError):
        return {
            "error": "Invalid route coordinates."
        }, 400

    if not ORS_API_KEY:
        return {
            "error": (
                "Routing API key is not configured."
            )
        }, 500

    ors_url = (
        "https://api.openrouteservice.org/"
        "v2/directions/foot-walking/geojson"
    )

    ors_headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "coordinates": [
            [user_lon, user_lat],
            [bin_lon, bin_lat],
        ]
    }

    try:
        response = requests.post(
            ors_url,
            json=payload,
            headers=ors_headers,
            timeout=20,
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        print(
            f"Walking route request failed: "
            f"{error}"
        )

        return {
            "error": (
                "Walking directions are "
                "temporarily unavailable."
            )
        }, 503


if __name__ == "__main__":
    app.run(debug=True)
