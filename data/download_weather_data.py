import pandas as pd
import requests
import sys

url = "https://archive-api.open-meteo.com/v1/archive?latitude=34.7744&longitude=32.4229&start_date=2024-09-14&end_date=2026-09-28&hourly=temperature_2m,shortwave_radiation,relative_humidity_2m,cloud_cover&timezone=auto"

r = requests.get(url)
status = r.status_code

if status != 200:
    print("Error loading data from API")
    sys.exit(1)

raw_data = r.json()
hourly = raw_data["hourly"]
print(f"Variables being checked: {hourly.keys()}")
print(f"Length of time variable: {len(hourly["time"])}")

df = pd.DataFrame(hourly)
df["time"] = pd.to_datetime(df["time"])
df = df.set_index("time")

print(f"empty values: {df.isna().sum()}\n")
print(df.head())
print(df.tail())

df.to_csv("data/paphos_weather_data.csv")
