#!/usr/bin/env python3
import json

from stravalib.client import Client
from dotenv import load_dotenv, dotenv_values

load_dotenv()

client_id_str, client_secret = open("client_secrets.txt").read().strip().split(",")
client_id = int(client_id_str)

# Open the token JSON file that you saved earlier
with open('tokens.json', "r") as f:
    token_response_refresh = json.load(f)

# Create a client object
client = Client()

refresh_response = client.refresh_access_token(
    client_id=client_id,
    client_secret=client_secret,
    refresh_token=token_response_refresh['refresh_token'],
)

print(refresh_response)

# Check that the refresh worked
athlete = client.get_athlete()

print(f"Hi, {athlete.firstname}!")
