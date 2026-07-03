"""Récupère les activités récentes du club Strava et les écrit dans data/raw_activities.json.

Variables d'environnement requises : STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET,
STRAVA_REFRESH_TOKEN, STRAVA_CLUB_ID.
"""

import json
import os
import sys
from pathlib import Path

import requests

TOKEN_URL = "https://www.strava.com/oauth/token"
RAW_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "raw_activities.json"


def get_access_token(client_id, client_secret, refresh_token):
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_club_activities(access_token, club_id, per_page=100):
    url = f"https://www.strava.com/api/v3/clubs/{club_id}/activities"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": per_page},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    client_id = os.environ["STRAVA_CLIENT_ID"]
    client_secret = os.environ["STRAVA_CLIENT_SECRET"]
    refresh_token = os.environ["STRAVA_REFRESH_TOKEN"]
    club_id = os.environ["STRAVA_CLUB_ID"]

    access_token = get_access_token(client_id, client_secret, refresh_token)
    activities = fetch_club_activities(access_token, club_id)

    RAW_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RAW_OUTPUT_PATH.write_text(json.dumps(activities, ensure_ascii=False, indent=2))
    print(f"{len(activities)} activités récupérées -> {RAW_OUTPUT_PATH}")


if __name__ == "__main__":
    sys.exit(main())
