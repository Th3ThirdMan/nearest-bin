import requests
import time
from math import radians, sin, cos, sqrt, atan2


# Configuration
user_lat = 53.3498
user_lon = -6.2603

url = "https://overpass-api.de/api/interpreter"

query = f"""
[out:json];
node["amenity"="waste_basket"]
(around:{user_lat},{user_lon});
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
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params={"data": query},
                headers=headers,
                timeout=20
            )
        except requests.exceptions.Timeout:
            print("The Overpass API took too long to respond.")
            return None

        if response.status_code == 200:
            break
        print(f"Attempt {attempt + 1} failed. Retrying...")
        time.sleep(2)
    

    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        print("The server returned invalid data. Please try again.")
        return None


def find_nearest_bin(bins, user_lat, user_lon):
    nearest_distance = float("inf")
    nearest_bin = None

    for waste_bin in bins:
        distance = calculate_distance(
            user_lat,
            user_lon,
            waste_bin["lat"],
            waste_bin["lon"]
        )

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_bin = waste_bin

    return nearest_bin, nearest_distance


# Main program
data = get_bins(url, query, headers)

if data is None:
    exit()

print(f"Found {len(data['elements'])} bins.")

nearest_bin, nearest_distance = find_nearest_bin(
    data["elements"],
    user_lat,
    user_lon
)

if nearest_bin:
    print("\nNearest bin:")
    print(
        f"Street: "
        f"{nearest_bin['tags'].get('object:street', 'Unknown')}"
    )
    print(f"Latitude: {nearest_bin['lat']}")
    print(f"Longitude: {nearest_bin['lon']}")
    print(f"Distance: {nearest_distance:.2f} metres")
else:
    print("No bins were found nearby.")


