import requests

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
    print()


