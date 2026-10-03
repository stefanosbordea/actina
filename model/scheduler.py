import pandas as pd

## Illustrative assumptions
TANK_CAPACITY = 4000
TANK_START = 2000
TANK_MIN = 800
PLANT_MAX = 400
PLANT_MIN = 100
KWH_PER_M3 = 3.4
PRICE_SURPLUS =101
PRICE_NORMAL = 183
SURPLUS_THRESHOLD = 600

BASE_DEMAND =200

HOURLY_SHAPE = [0.6]*6 + [1.3]*4 + [1.0]*8 + [1.4]*5 + [0.8]

def water_demand(hour,month,temperature):
    demand = BASE_DEMAND * HOURLY_SHAPE[hour]
    if month in (6,7,8,9): ## tourist season
        demand *= 1.15
    if temperature > 30: ## hot day
        demand *= 1.10
    return demand

#print(water_demand(3,1,12), water_demand(19,8,33), water_demand(13, 4, 22))

def simulate_tank(production, demand, start): ## tank level after each hour
    levels=[]
    level = start
    for p, d in zip(production, demand):
        level = level +p -d
        levels.append(level)
    return levels

def flat_plan(demand):
    return [sum(demand)/24] *24


"""print(simulate_tank([100]*24, [100]*24, 2000)[:3])
print(simulate_tank([300]*24, [100]*24, 2000)[:3])"""

def make_plan(forecast, demand, start):
    plan = [PLANT_MAX if f > SURPLUS_THRESHOLD else PLANT_MIN for f in forecast]

    sunniest= sorted(range(24), key= lambda h: forecast[h], reverse= True)

    for _ in range(1000):
        level = start
        for h in range(24):
            space = TANK_CAPACITY - level + demand[h]
            plan[h] = max(PLANT_MIN, min(plan[h], space))
            level = level + plan[h] - demand[h]

        levels = simulate_tank(plan, demand, start)
        low_hours = [h for h in range(24) if levels[h] <TANK_MIN]
        if not low_hours:
            return plan
        first_low = low_hours[0]
        shortfall = TANK_MIN - levels[first_low]

        options = [h for h in sunniest if h <= first_low and plan[h] < PLANT_MAX]
        if not options:
            return plan
        h = options[0]
        plan[h] += min(shortfall, PLANT_MAX - plan[h])
    return plan

"""demand = [water_demand(h, 7, 28) for h in range(24)]
sunny = [900 if 10 <= h <= 15 else 0 for h in range(24)]
cloudy = [0] * 24
for name, fc in [("sunny", sunny), ("cloudy", cloudy)]:
    plan = make_plan(fc, demand, 2000)
    levels = simulate_tank(plan, demand, 2000)
    print(name, [round(p) for p in plan])
    print("   tank min/max:", round(min(levels)), round(max(levels)))"""

def day_cost(plan,actual):
    cost = 0
    for p, a in zip(plan, actual):
        mwh = p * KWH_PER_M3 / 1000
        price = PRICE_SURPLUS if a> SURPLUS_THRESHOLD else PRICE_NORMAL
        cost += mwh * price
    return cost

def load_days(path):
    p = pd.read_csv(path, index_col=0, parse_dates=True)
    p.index = p.index + pd.Timedelta(hours=24)
    weather = pd.read_csv("data/paphos_weather_data.csv", index_col=0, parse_dates=True)
    p["temperature"] = weather["temperature_2m"].reindex(p.index)
    p["demand"] = [water_demand(t.hour, t.month, temp) for t, temp in zip(p.index, p["temperature"])]
    hours_in_Day = p.groupby(p.index.date)["actual"].transform("size")
    return p[hours_in_Day == 24]

def run(path,name):
    days = load_days(path)
    tank =TANK_START
    flat_cost = aktina_cost = flat_water = aktina_water = 0
    lowest =TANK_START
    rows=[]
    for date, day in days.groupby(days.index.date):
        forecast, actual, demand = list(day["predicted"]), list(day["actual"]),list(day["demand"])
        flat = flat_plan(demand)
        plan = make_plan(forecast, demand, tank)
        levels = simulate_tank(plan,demand, tank)

        flat_cost += day_cost(flat, actual)
        aktina_cost += day_cost(plan, actual)
        flat_water +=sum(flat)
        aktina_water += sum(plan)
        lowest = min(lowest, min(levels))
        tank = levels[-1]

        for i, t in enumerate(day.index):
            rows.append({"time": t, "actual": actual[i], "forecast": forecast[i], "demand ": demand[i], "flat": flat[i], "aktina": plan[i], "tank": levels[i]})

    flat_unit, aktina_unit = flat_cost / flat_water, aktina_cost / aktina_water
    print(f"{name}: flat €{flat_unit:.3f}/m³, Aktina €{aktina_unit:.3f}/m³, "
          f"saving {1-aktina_unit/ flat_unit:.1%}. lowest tank {lowest:.0f} m³")
    return pd.DataFrame(rows)

cv_sched = run("eval/cv_predictions.csv", "Winter–spring")
test_sched = run("eval/test_predictions.csv", "Summer")
pd.concat([cv_sched, test_sched]).to_csv("eval/schedule_hourly.csv", index=False)

