import requests

url = (
    "https://www.digitec.ch/en/s1/product/"
    "asus-rog-astral-geforce-rtx-5090-oc-32-gb-gddr7-"
    "graphics-card-54237902"
)

response = requests.get(
    url,
    headers={
        "User-Agent": "HSLU-DataEngineering-Project/1.0"
    },
    timeout=20
)

print("Status:", response.status_code)
print("Final URL:", response.url)
print("Server:", response.headers.get("Server"))

with open("debug_response.html", "w", encoding="utf-8") as file:
    file.write(response.text)