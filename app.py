import json
import requests
import time
from math import radians, sin, cos, sqrt, atan2


# Configuration
user_lat = 53.3498
user_lon = -6.2603
search_radius = 3000

url = "https://overpass-api.de/api/interpreter"

query = f"""
[out:json];
node["amenity"="waste_basket"]
(around:{search_radius},{user_lat},{user_lon});
out;
"""

headers = {
    "User-Agent": "NearestBin/1.0"
}


def calculate_distance(lat1, lon1, lat2, lon2):
    earth_radius = 6371000

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    difference_lat = lat2 - lat1
    difference_lon = lon2 - lon1

    a = (
        sin(difference_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(difference_lon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return earth_radius * c


def get_bins(url, query, headers):
    response = None

    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params={"data": query},
                headers=headers,
                timeout=40
            )

        except requests.exceptions.Timeout:
            if attempt < 2:
                print(f"Attempt {attempt + 1} timed out. Retrying...")
                time.sleep(2)
            continue

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            break

        if response.status_code == 200:
            try:
                data = response.json()
                data["source"] = "live"
                return data

            except requests.exceptions.JSONDecodeError:
                print("The server returned invalid JSON.")
                break

        if attempt < 2:
            print(f"Attempt {attempt + 1} failed. Retrying...")
            time.sleep(2)

    print("Overpass API is unavailable. Trying cached data.")

    try:
        with open("bins_cache.json", "r") as file:
            data = json.load(file)
            data["source"] = "cache"
            print("Using cached bin data.")
            return data

    except FileNotFoundError:
        print("No cached bin data was found.")
        return None


def find_nearest_bins(bins, user_lat, user_lon, limit=10):
    bins_with_distance = []

    for waste_bin in bins:
        distance = calculate_distance(
            user_lat,
            user_lon,
            waste_bin["lat"],
            waste_bin["lon"]
        )

        bins_with_distance.append(
            {
                "bin": waste_bin,
                "distance": distance
            }
        )
        
    bins_with_distance.sort(
        key=lambda item: item["distance"]
    )
    
    return bins_with_distance[:limit]

