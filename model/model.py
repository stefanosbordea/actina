import sklearn
import pandas as pd
from sklearn.model_selection import train_test_split


df = pd.read_csv("data/features.csv",index_col=0,parse_dates=True)

train_x,rest_x,train_y,rest_y = train_test_split(df.drop(columns="target"),df["target"],test_size=0.4,shuffle=False)
cv_x,test_x,cv_y,test_y = train_test_split(rest_x,rest_y,test_size=0.5,shuffle=False)
