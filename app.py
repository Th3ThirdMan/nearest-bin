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
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                params={"data": query},
                headers=headers,
                timeout=(5, 12),
            )

            response.raise_for_status()

            data = response.json()
            data["source"] = "live"
            return data

        except requests.exceptions.JSONDecodeError:
            print("Overpass returned invalid JSON.")
            break

        except requests.exceptions.Timeout:
            print(f"Overpass attempt {attempt + 1} timed out.")

        except requests.exceptions.RequestException as error:
            print(f"Overpass request failed: {error}")

        if attempt == 0:
            time.sleep(1)

    print("Overpass API unavailable. Trying cached data.")

    try:
        with open("bins_cache.json", "r", encoding="utf-8") as file:
            data = json.load(file)
            data["source"] = "cache"
            print("Using cached bin data.")
            return data

    except (FileNotFoundError, json.JSONDecodeError) as error:
        print(f"Cached bin data unavailable: {error}")
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

