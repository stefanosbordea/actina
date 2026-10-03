import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from lightgbm import LGBMRegressor
import numpy as np
import joblib



df = pd.read_csv("data/features.csv",index_col=0,parse_dates=True)

train_x,rest_x,train_y,rest_y = train_test_split(df.drop(columns="target"),df["target"],test_size=0.4,shuffle=False)
cv_x,test_x,cv_y,test_y = train_test_split(rest_x,rest_y,test_size=0.5,shuffle=False)

full_x = pd.concat([train_x,cv_x])
full_y = pd.concat([train_y,cv_y])

test_baseline = mean_absolute_error(test_y,test_x["shortwave_radiation"])

print(f"Baseline test: {test_baseline:.2f}")

final_model = LGBMRegressor(
    n_estimators=148,
    learning_rate=0.05,
    verbose=-1,
    metric="l1"
)

final_model.fit(
    full_x,full_y
)

test_pred =np.clip(final_model.predict(test_x),0,None)

test_mae = mean_absolute_error(test_y,test_pred)
print(f"MAE test: {test_mae:.2f}")

joblib.dump(final_model,"model/lgbm_radiation.pkl")

results = pd.DataFrame({ "actual":test_y, "predicted":test_pred,"baseline":test_x["shortwave_radiation"]},index=test_x.index)
print(results.head())

results.to_csv("eval/test_predictions.csv")