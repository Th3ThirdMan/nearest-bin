import json
import math
import os

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

app = Flask(__name__)


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


def get_dcc_bins_nearby(user_lat, user_lon):
    nearby = []

    for bin_item in DCC_BINS:
        distance = distance_metres(
            user_lat,
            user_lon,
            bin_item["lat"],
            bin_item["lon"],
        )

        if distance <= search_radius:
            nearby.append(bin_item)

    return nearby


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

    if bin_type == "all":
        query = f"""
        [out:json];
        (
          node["amenity"="waste_basket"]
          (around:{search_radius},{user_lat},{user_lon});

          node["amenity"="recycling"]
          (around:{search_radius},{user_lat},{user_lon});
        );
        out;
        """

    else:
        amenity = (
            "recycling"
            if bin_type == "recycling"
            else "waste_basket"
        )

        query = f"""
        [out:json];
        node["amenity"="{amenity}"]
        (around:{search_radius},{user_lat},{user_lon});
        out;
        """

    data = get_bins(url, query, headers)

    if data is not None:
        data_source = data.get("source")
        osm_bins = data.get("elements", [])

        print(f"Bins returned by Overpass: {len(osm_bins)}")

        # DCC bins apply only to Public and All.
        if bin_type in ("public", "all"):
            dcc_bins = get_dcc_bins_nearby(
                user_lat,
                user_lon,
            )

            print(f"DCC bins nearby: {len(dcc_bins)}")

            bins = merge_public_bins(
                osm_bins,
                dcc_bins,
            )

            if dcc_bins:
                data_source = "OSM + Dublin City Council"

        else:
            bins = osm_bins

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
            # we have no official DCC results supplementing it.
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
            error_message = (
                f"No bins were found within "
                f"{search_radius} metres."
            )

    else:
        # Even if Overpass is unavailable, official DCC data
        # can still provide public bins.
        if bin_type in ("public", "all"):
            dcc_bins = get_dcc_bins_nearby(
                user_lat,
                user_lon,
            )

            if dcc_bins:
                nearest_bins = find_nearest_bins(
                    dcc_bins,
                    user_lat,
                    user_lon,
                )

                nearest_bin = nearest_bins[0]["bin"]
                nearest_distance = nearest_bins[0]["distance"]
                data_source = "Dublin City Council"

            else:
                error_message = (
                    "The bin service is temporarily unavailable. "
                    "Please try again."
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

    except (KeyError, TypeError, ValueError):
        return jsonify({
            "error": "Invalid coordinates."
        }), 400

    query = f"""
    [out:json];
    node["amenity"="waste_basket"]
    (around:{search_radius},{user_lat},{user_lon});
    out;
    """

    data = get_bins(url, query, headers)

    osm_bins = []

    if data is not None:
        osm_bins = data.get("elements", [])

    dcc_bins = get_dcc_bins_nearby(
        user_lat,
        user_lon,
    )

    bins = merge_public_bins(
        osm_bins,
        dcc_bins,
    )

    if not bins:
        return jsonify({
            "error": (
                f"No public bins were found within "
                f"{search_radius} metres."
            )
        }), 404

    nearest_bins = find_nearest_bins(
        bins,
        user_lat,
        user_lon,
    )

    if dcc_bins and osm_bins:
        data_source = "OSM + Dublin City Council"
    elif dcc_bins:
        data_source = "Dublin City Council"
    elif data is not None:
        data_source = data.get("source")
    else:
        data_source = None

    return jsonify({
        "userLatitude": user_lat,
        "userLongitude": user_lon,
        "nearestBins": nearest_bins,
        "dataSource": data_source,
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
