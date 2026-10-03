import pandas as pd 

df = pd.read_csv("data/paphos_weather_data.csv", index_col=0, parse_dates=True)

df["radiation_yesterday"] = df["shortwave_radiation"].shift(24) # radiation yesterday
df["hour"] = df.index.hour
df["month"] = df.index.month
df["target"] = df["shortwave_radiation"].shift(-24)#radiation levels tommorow
df = df.dropna()

print(df.head())
print(df.tail())
df.to_csv("data/features.csv")