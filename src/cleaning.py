"""
Builds the board error table from the raw collector snapshots.

Each row = one prediction (train, stop, snapshot) compared to the "actual"
time, which we take as the last prediction seen before the train passed.
"""
import glob
import os

import pandas as pd

INPUT_FOLDER = "../paris-data/snapshots"
OUTPUT_FILE = "data/processed/board_errors.parquet"
MAX_FINAL_HORIZON_MIN = 5

TIME_COLUMNS = ["snapshot_utc", "aimed_arrival", "expected_arrival",
                "aimed_departure", "expected_departure"]


def load_snapshots(folder):
    """Read all snapshot files into one table."""
    files = sorted(glob.glob(folder + "/**/*.parquet", recursive=True))
    if len(files) == 0:
        raise FileNotFoundError("no parquet files in " + folder)

    tables = []
    for f in files:
        tables.append(pd.read_parquet(f))
    df = pd.concat(tables, ignore_index=True)

    print(f"Loaded {len(files)} snapshots, {len(df):,} rows")
    return df


def add_prediction_columns(df):
    """Add one predicted time, one scheduled time and the horizon per row."""
    df = df.copy()

    # make sure all time columns are real dates
    for col in TIME_COLUMNS:
        df[col] = pd.to_datetime(df[col], utc=True)

    # use the departure, or the arrival if there is none (e.g. terminus)
    df["predicted"] = df["expected_departure"].fillna(df["expected_arrival"])
    df["scheduled"] = df["aimed_departure"].fillna(df["aimed_arrival"])

    df = df.dropna(subset=["predicted"])
    df = df.drop_duplicates(subset=["journey_ref", "stop_ref", "snapshot_utc"])

    # how many minutes ahead the board was predicting
    df["horizon_min"] = (df["predicted"] - df["snapshot_utc"]).dt.total_seconds() / 60
    return df


# the same train is seen at the same stop again this much later = a new passage
NEW_PASSAGE_JUMP_MIN = 30


NEW_PASSAGE_JUMP_MIN = 30


def build_board_errors(df):
    """Compare every prediction with the last one for that train at that stop."""
    df = df.sort_values(["journey_ref", "stop_ref", "snapshot_utc"])

    # termini are always first in the list, and their ids get reused for each departure
    first_share = (df["stop_order"] == 0).groupby(df["stop_ref"]).transform("mean")
    df = df[first_share < 0.9]

    # metro reuses journey_ref all day: a big jump = the train's next passage
    jump_min = df.groupby(["journey_ref", "stop_ref"])["predicted"].diff().dt.total_seconds() / 60
    df["passage"] = (jump_min > NEW_PASSAGE_JUMP_MIN).groupby([df["journey_ref"], df["stop_ref"]]).cumsum()

    groups = df.groupby(["journey_ref", "stop_ref", "passage"])
    df["actual"] = groups["predicted"].transform("last")
    df["final_horizon_min"] = groups["horizon_min"].transform("last")
    df["final_snapshot_utc"] = groups["snapshot_utc"].transform("last")

    df = df[df["final_horizon_min"] <= MAX_FINAL_HORIZON_MIN]
    df = df[df["snapshot_utc"] < df["final_snapshot_utc"]].copy()

    df["board_error_min"] = (df["actual"] - df["predicted"]).dt.total_seconds() / 60
    df["delay_min"] = (df["actual"] - df["scheduled"]).dt.total_seconds() / 60

    paris_time = df["snapshot_utc"].dt.tz_convert("Europe/Paris")
    df["date_paris"] = paris_time.dt.date
    df["hour_paris"] = paris_time.dt.hour
    df["weekday"] = paris_time.dt.dayofweek

    return df.reset_index(drop=True)

if __name__ == "__main__":
    raw = load_snapshots(INPUT_FOLDER)
    predictions = add_prediction_columns(raw)
    errors = build_board_errors(predictions)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    errors.to_parquet(OUTPUT_FILE, index=False)
    print(f"Saved {len(errors):,} predictions to {OUTPUT_FILE}")