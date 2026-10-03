import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from lightgbm import LGBMRegressor,early_stopping
import numpy as np



df = pd.read_csv("data/features.csv",index_col=0,parse_dates=True)

train_x,rest_x,train_y,rest_y = train_test_split(df.drop(columns="target"),df["target"],test_size=0.4,shuffle=False)
cv_x,test_x,cv_y,test_y = train_test_split(rest_x,rest_y,test_size=0.5,shuffle=False)

cv_baseline = mean_absolute_error(cv_y,cv_x["shortwave_radiation"])
test_baseline = mean_absolute_error(test_y,test_x["shortwave_radiation"])

print(f"Baseline CV: {cv_baseline:.2f}")
print(f"Baseline test: {test_baseline:.2f}")

model = LGBMRegressor(
    n_estimators=1000,
    learning_rate=0.05,
    verbose=-1,
    metric ="l1"
)

model.fit(
    train_x,train_y, 
    eval_set=[(cv_x,cv_y)],
    callbacks=[early_stopping(50)]
)
print(f"Best number of trees: {model.best_iteration_}")

cv_pred =np.clip(model.predict(cv_x),0,None)

cv_mae = mean_absolute_error(cv_y,cv_pred)
print(f"MAE CV: {cv_mae:.2f}")

results = pd.DataFrame({ "actual":cv_y, "predicted":cv_pred,"baseline":cv_x["shortwave_radiation"]},index=cv_x.index)
print(results.head())

results.to_csv("eval/cv_predictions.csv")