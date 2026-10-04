import pandas as pd 

df = pd.read_csv("data/paphos_weather_datav2.csv", index_col=0, parse_dates=True)
v2_df = pd.read_csv("data/paphos_nwp_data.csv", index_col=0, parse_dates=True)

full_df = pd.concat([df,v2_df],axis=1)

full_df["radiation_yesterday"] = full_df["shortwave_radiation"].shift(24) # radiation yesterday
full_df["hour"] = full_df.index.hour
full_df["month"] = full_df.index.month
full_df["nwp_cloud"] =full_df["nwp_cloud"].shift(-24) 
full_df["nwp_radiation"] = full_df["nwp_radiation"].shift(-24)
full_df["target"] = full_df["shortwave_radiation"].shift(-24)#radiation levels tommorow
full_df = full_df.dropna()

print(full_df.head())
print(full_df.tail())
print(full_df.shape)
print(full_df.columns)
full_df.to_csv("data/featuresv2.csv")