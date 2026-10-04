import pandas as pd
from sklearn.metrics import mean_absolute_error
from lightgbm import LGBMRegressor,early_stopping
import numpy as np


data = pd.read_csv("data/featuresv2.csv", index_col=0,parse_dates=True)

features = data.drop(columns="target")
target = data["target"]


train_x = features.loc[:"2025-12-03 18:00"]
train_y = target.loc[:"2025-12-03 18:00"]
cv_x =  features.loc["2025-12-04 19:00":"2026-05-02 08:00"]
cv_y = target.loc["2025-12-04 19:00":"2026-05-02 08:00"]

yesterday_mae = mean_absolute_error(cv_y,cv_x["shortwave_radiation"])
raw_forecast_mae = mean_absolute_error(cv_y,cv_x["nwp_radiation"])

print(f"yesterday's mae: {yesterday_mae:.2f}")
print(f"raw forecast mae: {raw_forecast_mae:.2f}")

model_v2 =LGBMRegressor(
    n_estimators=1000,
    learning_rate=0.05,
    verbose=-1,
    metric ="l1"
)

model_v2.fit (
    train_x,train_y,
    eval_set=[(cv_x,cv_y)],
    callbacks=[early_stopping(50)]
)

print(f"Best number of trees: {model_v2.best_iteration_}")

cv_pred =np.clip(model_v2.predict(cv_x),0,None)

cv_mae = mean_absolute_error(cv_y,cv_pred)
print(f"MAE CV: {cv_mae:.2f}")

results = pd.DataFrame({ "actual":cv_y, "predicted":cv_pred,"baseline":cv_x["shortwave_radiation"],"forecast":cv_x["nwp_radiation"]},index=cv_x.index)
results.to_csv("eval/cv_predictions_v2.csv")

feature_importance = pd.Series(model_v2.feature_importances_, index=train_x.columns).sort_values(ascending=False)
print(feature_importance)