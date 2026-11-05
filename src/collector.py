# collector.py
# Gets the live predictions (estimated timetable) from the PRIM API
# and saves the ones for my lines in a parquet file.
#
# To run it (from the project folder):
#   python -m src.collector --out-dir data/raw/snapshots

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from src.config import FOCUS_LINES

URL = "https://prim.iledefrance-mobilites.fr/marketplace/estimated-timetable"

# I only keep the stops where the train is expected in the next hour
HORIZON_MINUTES = 60


def fetch_feed(api_key):
    headers = {"apikey": api_key, "Accept": "application/json"}
    params = {"LineRef": "ALL"}  # ALL is the only value this API accepts

    # try 3 times in case the API or the network has a problem
    for attempt in range(3):
        try:
            response = requests.get(URL, headers=headers, params=params, timeout=90)
        except requests.RequestException as e:
            print("Network error:", e)
            time.sleep(10)
            continue

        if response.status_code == 200:
            return response.json()

        print("Error", response.status_code, response.text[:200])
        if response.status_code in (401, 403):
            break  # the key is wrong, no point trying again
        time.sleep(10)

    # exit with an error so the GitHub Actions run shows up red
    sys.exit("Could not get the data from PRIM")


def get_value(field):
    # SIRI puts most text inside {"value": ...} or [{"value": ...}]
    # this function gets the text out in both cases
    if isinstance(field, list):
        if len(field) == 0:
            return None
        field = field[0]
    if isinstance(field, dict):
        return field.get("value")
    return field


def parse_feed(data, snapshot_time):
    my_lines = list(FOCUS_LINES.values())
    rows = []

    # the trains are 3 lists deep in the response (same loops as in my notebook)
    deliveries = data["Siri"]["ServiceDelivery"].get("EstimatedTimetableDelivery", [])
    for delivery in deliveries:
        for frame in delivery.get("EstimatedJourneyVersionFrame", []):
            for journey in frame.get("EstimatedVehicleJourney", []):

                line = get_value(journey.get("LineRef"))
                if line not in my_lines:
                    continue

                # one row for each stop of the train
                stops = journey.get("EstimatedCalls", {}).get("EstimatedCall", [])
                for i, stop in enumerate(stops):
                    row = {
                        "snapshot_utc": snapshot_time,
                        "line_ref": line,
                        "line_name": get_value(journey.get("PublishedLineName")),
                        "vehicle_mode": get_value(journey.get("VehicleMode")),
                        "direction": get_value(journey.get("DirectionRef")),
                        "journey_ref": get_value(journey.get("DatedVehicleJourneyRef")),
                        "mission": get_value(journey.get("JourneyNote")),
                        "train_number": get_value(journey.get("VehicleJourneyName")),
                        "cancelled": journey.get("Cancellation"),
                        "stop_ref": get_value(stop.get("StopPointRef")),
                        "stop_order": i,
                        "destination": get_value(stop.get("DestinationDisplay")),
                        "aimed_arrival": stop.get("AimedArrivalTime"),
                        "expected_arrival": stop.get("ExpectedArrivalTime"),
                        "aimed_departure": stop.get("AimedDepartureTime"),
                        "expected_departure": stop.get("ExpectedDepartureTime"),
                        "arrival_status": stop.get("ArrivalStatus"),
                        "departure_status": stop.get("DepartureStatus"),
                    }
                    rows.append(row)

    df = pd.DataFrame(rows)
    if len(df) == 0:
        return df

    # convert the times from text to real datetimes (in UTC)
    time_columns = ["aimed_arrival", "expected_arrival", "aimed_departure", "expected_departure"]
    for col in time_columns:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

    # keep only the stops coming up in the next hour
    # (some stops only have an arrival time, so I use that when departure is missing)
    expected_time = df["expected_departure"].fillna(df["expected_arrival"])
    limit = snapshot_time + timedelta(minutes=HORIZON_MINUTES)
    df = df[(expected_time >= snapshot_time) & (expected_time <= limit)]

    return df.reset_index(drop=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="data/raw/snapshots")
    args = parser.parse_args()

    # the key comes from .env on my laptop, or from the GitHub secret
    load_dotenv()
    api_key = os.getenv("PRIM_API_KEY")
    if api_key is None:
        sys.exit("PRIM_API_KEY not found")

    snapshot_time = datetime.now(timezone.utc).replace(microsecond=0)

    data = fetch_feed(api_key)
    df = parse_feed(data, snapshot_time)
    if len(df) == 0:
        sys.exit("No rows for my lines, check the line IDs in config.py")

    # one file per run, e.g. snapshots/2026/11/06/081500.parquet
    folder = Path(args.out_dir) / snapshot_time.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    file_path = folder / (snapshot_time.strftime("%H%M%S") + ".parquet")
    df.to_parquet(file_path, index=False)

    print("Saved", len(df), "rows to", file_path)
    print(df.groupby("line_name", dropna=False)["journey_ref"].nunique())


if __name__ == "__main__":
    main()