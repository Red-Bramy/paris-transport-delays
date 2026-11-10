"""Download hourly Paris weather for the collection period into data/reference/weather.csv."""
from datetime import date, timedelta

import pandas as pd
import requests

PARIS = {"latitude": 48.8566, "longitude": 2.3522}
VARIABLES = "temperature_2m,precipitation,rain,wind_speed_10m,weather_code"
OUT = "data/reference/weather.csv"


def to_frame(response):
    response.raise_for_status()
    hourly = pd.DataFrame(response.json()["hourly"])
    hourly["hour_utc"] = pd.to_datetime(hourly.pop("time"), utc=True)
    return hourly


def fetch_archive(start, end):
    params = {**PARIS, "start_date": str(start), "end_date": str(end),
              "hourly": VARIABLES, "timezone": "GMT"}
    return to_frame(requests.get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=30))


def fetch_recent(days=10):
    params = {**PARIS, "past_days": days, "forecast_days": 1,
              "hourly": VARIABLES, "timezone": "GMT"}
    return to_frame(requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=30))


def fetch_weather(start):
    archive_end = date.today() - timedelta(days=6)
    parts = []
    if start <= archive_end:
        parts.append(fetch_archive(start, archive_end))
    parts.append(fetch_recent())
    weather = pd.concat(parts, ignore_index=True)
    # archive comes first, so keep="first" prefers it when an hour is in both
    weather = weather.drop_duplicates("hour_utc", keep="first").sort_values("hour_utc")
    return weather[weather["hour_utc"].dt.date >= start]


if __name__ == "__main__":
    import sys
    start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(2026, 11, 5)
    weather = fetch_weather(start)
    weather.to_csv(OUT, index=False)
    print(f"Saved {len(weather)} hours to {OUT}, max rain {weather['rain'].max()} mm/h")