"""First test call to the PRIM real-time departures API (Prochains passages)."""
import os
import sys
from datetime import datetime

import requests
from dotenv import load_dotenv

URL = "https://prim.iledefrance-mobilites.fr/marketplace/stop-monitoring"
# Chatelet interchange area (example ID from the PRIM documentation)
STOP_ID = "STIF:StopArea:SP:71264:"


def main():
    load_dotenv()
    api_key = os.getenv("PRIM_API_KEY")
    if not api_key:
        sys.exit("PRIM_API_KEY not found. Did you create .env in the repo root?")

    response = requests.get(
        URL,
        headers={"apikey": api_key, "Accept": "application/json"},
        params={"MonitoringRef": STOP_ID},
        timeout=10,
    )
    print("HTTP status:", response.status_code)
    if response.status_code == 401:
        sys.exit("401 Unauthorized: the key is wrong, or not subscribed to this API.")
    response.raise_for_status()

    data = response.json()
    visits = (
        data["Siri"]["ServiceDelivery"]["StopMonitoringDelivery"][0]
        .get("MonitoredStopVisit", [])
    )
    print(f"{len(visits)} upcoming departures found. First 10:\n")

    for visit in visits[:10]:
        journey = visit["MonitoredVehicleJourney"]
        call = journey["MonitoredCall"]
        line = journey["LineRef"]["value"]
        destination = (call.get("DestinationDisplay") or [{}])[0].get("value", "?")
        aimed = call.get("AimedDepartureTime") or call.get("AimedArrivalTime")
        expected = call.get("ExpectedDepartureTime") or call.get("ExpectedArrivalTime")

        delay = ""
        if aimed and expected:
            a = datetime.fromisoformat(aimed.replace("Z", "+00:00"))
            e = datetime.fromisoformat(expected.replace("Z", "+00:00"))
            delay = f"{(e - a).total_seconds() / 60:+.0f} min"

        print(f"{line:<22} -> {destination:<30} expected {expected}  {delay}")


if __name__ == "__main__":
    main()