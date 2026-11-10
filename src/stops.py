"""Build data/reference/stops.csv: one row per stop """
import zipfile

import pandas as pd

STOPS_CSV = "data/raw/arrets-lignes.csv"
OUT = "data/reference/stops.csv"


def stop_number(ids):
    """'STIF:StopPoint:Q:41087:' and 'IDFM:41087' both become '41087'."""
    return ids.astype(str).str.extract(r"(\d+)\D*$")[0]


def load_gtfs_stops(path=STOPS_CSV):
    stops = pd.read_csv(path, sep=";", dtype=str)
    stops["stop_number"] = stop_number(stops["stop_id"])
    stops["stop_lat"] = stops["stop_lat"].astype(float)
    stops["stop_lon"] = stops["stop_lon"].astype(float)
    # the file has one row per stop AND per line, so keep one row per stop
    return stops.drop_duplicates("stop_number")[["stop_number", "stop_name", "stop_lat", "stop_lon"]]



def build_stops_table(errors):
    observed = errors[["stop_ref"]].drop_duplicates()
    observed["stop_number"] = stop_number(observed["stop_ref"])
    table = observed.merge(load_gtfs_stops(), on="stop_number", how="left")

    rate = table["stop_name"].notna().mean()
    print(f"{len(table)} stops observed, {rate:.1%} matched in GTFS")
    if rate < 0.95:
        print("Unmatched examples:", table.loc[table["stop_name"].isna(), "stop_ref"].head(10).tolist())
    return table


if __name__ == "__main__":
    errors = pd.read_parquet("data/processed/board_errors.parquet")
    build_stops_table(errors).to_csv(OUT, index=False)
    print(f"Saved {OUT}")