import pandas as pd
import requests
import sys

previous_url = "https://archive-api.open-meteo.com/v1/archive?latitude=34.7744&longitude=32.4229&start_date=2024-01-01&end_date=2026-09-28&hourly=temperature_2m,shortwave_radiation,relative_humidity_2m,cloud_cover&timezone=auto"
new_url = "https://previous-runs-api.open-meteo.com/v1/forecast?latitude=34.7744&longitude=32.4229&start_date=2024-01-01&end_date=2026-09-28&hourly=shortwave_radiation_previous_day1,cloud_cover_previous_day1&timezone=auto"
prev_r = requests.get(previous_url)
new_r = requests.get(new_url)

prev_status = prev_r.status_code
new_status = new_r.status_code

if prev_status != 200 or new_status != 200 :
    print("Error loading data from API")
    sys.exit(1)

previous_raw_data = prev_r.json()
new_raw_data = new_r.json()

prev_hourly = previous_raw_data["hourly"]
new_hourly = new_raw_data["hourly"]

print(f"Variables being checked: {prev_hourly.keys()}")
print(f"Length of time variable: {len(prev_hourly["time"])}")

print(f"Variables being checked: {new_hourly.keys()}")
print(f"Length of time variable: {len(new_hourly["time"])}")

df = pd.DataFrame(prev_hourly)
df["time"] = pd.to_datetime(df["time"])
df = df.set_index("time")

v2_df = pd.DataFrame(new_hourly)
v2_df["time"] = pd.to_datetime(v2_df["time"])
v2_df = v2_df.set_index("time")

print(f"empty values: {df.isna().sum()}\n")
print(df.head())
print(df.tail())

print(f"empty values: {v2_df.isna().sum()}\n")
print(v2_df.head())
print(v2_df.tail())

v2_df = v2_df.rename(columns={
    "shortwave_radiation_previous_day1": "nwp_radiation",
    "cloud_cover_previous_day1": "nwp_cloud",
})

print(v2_df["nwp_radiation"].first_valid_index())
print(v2_df.describe())

actual = df["shortwave_radiation"].groupby(df.index.hour).mean()
forecast = v2_df["nwp_radiation"].groupby(v2_df.index.hour).mean()

print(actual.idxmax())
print(forecast.idxmax())

df.to_csv("data/paphos_weather_datav2.csv")
v2_df.to_csv("data/paphos_nwp_data.csv")
