import requests
from math import radians, sin, cos, sqrt, atan2

user_lat = 53.3498
user_lon = -6.2603

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

nearest_distance = float("inf")
nearest_bin = None

url = "https://overpass-api.de/api/interpreter"

query = """
[out:json];
node["amenity"="waste_basket"]
(around:300,53.3498,-6.2603);
out;
"""

headers = {
    "User-Agent": "NearestBin/1.0"
}

try:
    response = requests.get(
        url,
        params={"data": query},
        headers=headers,
        timeout=20
    )
except requests.exceptions.Timeout:
    print("The Overpass API took too long to respond.")
    exit()

print(response.status_code)

if response.status_code != 200:
    print("Overpass API is busy. Please try again.")
    exit()
    
try:
    data = response.json()
except requests.exceptions.JSONDecodeError:
    print("The server returned invalid data. Please try again.")
    exit()
    
print(f"Found {len(data['elements'])} bins.")
for waste_bin in data["elements"]:
    print(f"Street: {waste_bin['tags'].get('object:street', 'Unknown')}")
    print(f"Latitude: {waste_bin['lat']}")
    print(f"Longitude: {waste_bin['lon']}")
    
    distance = calculate_distance(
        user_lat,
        user_lon,
        waste_bin["lat"],
        waste_bin["lon"]
    )
    
    if distance < nearest_distance:
        nearest_distance = distance
        nearest_bin = waste_bin
        
if nearest_bin:
    print("\nNearest bin:")
    print(f"\nStreet: {nearest_bin['tags'].get('object:street', 'Unknown')}")
    print(f"Latitude: {nearest_bin['lat']}")
    print(f"Longitude: {nearest_bin['lon']}")
    print(f"Distance: {nearest_distance:.2f} metres")
    print()


