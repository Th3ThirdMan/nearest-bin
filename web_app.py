import os
import requests


from flask import Flask, render_template, request
from dotenv import load_dotenv

from app import (
    find_nearest_bins,
    get_bins,
    headers,
    search_radius,
    url
)

load_dotenv()
ORS_API_KEY = os.getenv("ORS_API_KEY")


app = Flask(__name__)


@app.route("/")
def home():
    return render_template(
        "index.html",
        title="FindMyBin",
        nearest_bin=None,
        nearest_bins = [],
        nearest_distance=None,
        error_message=None,
        data_source=None,
        user_lat=None,
        user_lon=None
    )


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
            user_lon=None
        )

    query = f"""
    [out:json];
    node["amenity"="waste_basket"]
    (around:{search_radius},{user_lat},{user_lon});
    out;
    """

    data = get_bins(url, query, headers)

    if data is not None:
        data_source = data.get("source")
        bins = data.get("elements", [])
        
        print(f"Bins returned by Overpass: {len(bins)}")

        if bins:
            nearest_bins = find_nearest_bins(
                bins,
                user_lat,
                user_lon
            )
            
            print(f"Nearest bins found: {len(nearest_bins)}")
            
            for index, item in enumerate(nearest_bins, start=1):
                print(
                    f"{index}: {item['distance']:.0f}m "
                    f"({item['bin']['lat']}, {item['bin']['lon']})"
            )
            nearest_bin = nearest_bins[0]["bin"]
            nearest_distance = nearest_bins[0]["distance"]

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
                f"No public bins were found within "
                f"{search_radius} metres."
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
        user_lon=user_lon
    )
    
    
@app.route("/walking-route", methods=["POST"])
def walking_route():
    route_data = request.get_json()

    if not route_data:
        return {"error": "No route coordinates were supplied."}, 400

    try:
        user_lat = float(route_data["user_lat"])
        user_lon = float(route_data["user_lon"])
        bin_lat = float(route_data["bin_lat"])
        bin_lon = float(route_data["bin_lon"])

    except (KeyError, TypeError, ValueError):
        return {"error": "Invalid route coordinates."}, 400

    if not ORS_API_KEY:
        return {"error": "Routing API key is not configured."}, 500

    ors_url = (
        "https://api.openrouteservice.org/"
        "v2/directions/foot-walking/geojson"
    )

    ors_headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "coordinates": [
            [user_lon, user_lat],
            [bin_lon, bin_lat]
        ]
    }

    try:
        response = requests.post(
            ors_url,
            json=payload,
            headers=ors_headers,
            timeout=20
        )

        response.raise_for_status()

        return response.json()

    except requests.RequestException as error:
        print(f"Walking route request failed: {error}")

        return {
            "error": "Walking directions are temporarily unavailable."
        }, 503


if __name__ == "__main__":
    app.run(debug=True)