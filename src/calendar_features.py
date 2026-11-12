"""Build data/reference/calendar.csv: one row per day with the kind of day it was."""
import holidays
import pandas as pd

OUT = "data/reference/calendar.csv"


def build_calendar(start, end):
    cal = pd.DataFrame({"date": pd.date_range(start, end, freq="D").date})

    fr_holidays = holidays.France(years=range(start.year, end.year + 1))
    cal["is_public_holiday"] = cal["date"].apply(lambda d: d in fr_holidays)
    cal["holiday_name"] = cal["date"].apply(lambda d: fr_holidays.get(d))

    school = pd.read_csv("data/reference/school_holidays_zone_c.csv", parse_dates=["start", "end"])
    cal["is_school_holiday"] = False
    for _, row in school.iterrows():
        inside = (cal["date"] >= row["start"].date()) & (cal["date"] <= row["end"].date())
        cal.loc[inside, "is_school_holiday"] = True

    strikes = pd.read_csv("data/reference/strike_days.csv", parse_dates=["date"])
    cal["is_strike"] = cal["date"].isin(strikes["date"].dt.date)

    weekday = pd.to_datetime(cal["date"]).dt.dayofweek
    cal["is_weekend"] = weekday >= 5
    return cal


if __name__ == "__main__":
    errors = pd.read_parquet("data/processed/board_errors.parquet")
    cal = build_calendar(errors["date_paris"].min(), errors["date_paris"].max())
    cal.to_csv(OUT, index=False)
    print(cal.sum(numeric_only=True))