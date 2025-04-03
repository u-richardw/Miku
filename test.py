import requests

CLIENT_ID = "9a6u2yky7kwe45fq8j3a4v1gf6mwhk"
CLIENT_SECRET = "993k8pv8gls3alv7xt00a30wjjj6ky"

url = "https://id.twitch.tv/oauth2/token"
params = {
    "client_id": CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "grant_type": "client_credentials"
}

response = requests.post(url, params=params)
data = response.json()

if "access_token" in data:
    print(f"OAuth Token: {data['access_token']}")
else:
    print("Error:", data)
oauth:1ashkq252nievdfihwpy491chkqmj2