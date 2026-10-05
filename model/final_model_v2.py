import pandas as pd
from sklearn.metrics import mean_absolute_error
from lightgbm import LGBMRegressor,early_stopping
import numpy as np
import joblib


data = pd.read_csv("data/featuresv2.csv", index_col=0,parse_dates=True)

features = data.drop(columns="target")
target = data["target"]


train_x = features.loc[:"2026-05-01 08:00"]
train_y = target.loc[:"2026-05-01 08:00"]
test_x =  features.loc["2026-05-02 09:00":"2026-09-27 23:00"]
test_y = target.loc["2026-05-02 09:00":"2026-09-27 23:00"]


yesterday_mae = mean_absolute_error(test_y,test_x["shortwave_radiation"])
raw_forecast_mae = mean_absolute_error(test_y,test_x["nwp_radiation"])

print(f"yesterday's mae: {yesterday_mae:.2f}")
print(f"raw forecast mae: {raw_forecast_mae:.2f}")

final_model_v2 =LGBMRegressor(
    n_estimators=146,
    learning_rate=0.05,
    verbose=-1,
    metric ="l1"
)

final_model_v2.fit (
    train_x,train_y,
)



test_pred =np.clip(final_model_v2.predict(test_x),0,None)

test_mae = mean_absolute_error(test_y,test_pred)
print(f"MAE TEST: {test_mae:.2f}")

results = pd.DataFrame({ "actual":test_y, "predicted":test_pred,"baseline":test_x["shortwave_radiation"],"forecast":test_x["nwp_radiation"]},index=test_x.index)
results.to_csv("eval/test_predictions_v2.csv")

feature_importance = pd.Series(final_model_v2.feature_importances_, index=train_x.columns).sort_values(ascending=False)
print(feature_importance)

joblib.dump(final_model_v2,"model/lgbm_radiation_v2.pkl")