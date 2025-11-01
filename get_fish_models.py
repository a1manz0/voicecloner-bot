import requests

url = "https://api.fish.audio/model"

headers = {"Authorization": "Bearer be9844b9995e489396ccba5e48848f64"}

response = requests.get(url, headers=headers)

print(response.json())
