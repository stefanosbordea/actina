import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("data/paphos_weather_data.csv",index_col = "time", parse_dates = True)
print(df.index.dtype)

hourly_radiation = df.groupby(df.index.hour)["shortwave_radiation"].mean()
print(hourly_radiation)

plt.plot(hourly_radiation, label= "Mean Radiation")
plt.axhline(600, label = "Surplus threshold (600 W/m²)")
plt.title("Mean shortwave radiation per hour")
plt.xlabel("Hour of day")
plt.ylabel("Radiation(W/m²)")
plt.legend()
plt.savefig("eval/plots/radiation_average.png")
plt.show()

