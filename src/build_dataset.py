import pandas as pd


def build_dataset():
    errors = pd.read_parquet("data/processed/board_errors.parquet")
    stops = pd.read_csv("data/reference/stops.csv", dtype={"stop_number": str})
    weather = pd.read_csv("data/reference/weather.csv", parse_dates=["hour_utc"])
    calendar = pd.read_csv("data/reference/calendar.csv", parse_dates=["date"])

    n_rows = len(errors)

    df = errors.merge(stops, on="stop_ref", how="left")

    # weather is hourly
    df["hour_utc"] = df["snapshot_utc"].dt.floor("h")
    weather["hour_utc"] = pd.to_datetime(weather["hour_utc"], utc=True)
    df = df.merge(weather, on="hour_utc", how="left")

    df["date_paris"] = pd.to_datetime(df["date_paris"])
    df = df.merge(calendar, left_on="date_paris", right_on="date", how="left")
    df = df.drop(columns="date")

    assert len(df) == n_rows, "duplicated rows after join"

    for col in ["stop_name", "rain", "is_strike"]:
        print(f"missing {col}: {df[col].isna().mean():.1%}")

    return df


if __name__ == "__main__":
    df = build_dataset()
    df.to_parquet("data/processed/analysis_table.parquet", index=False)
    print(f"Saved {len(df):,} rows x {df.shape[1]} columns")