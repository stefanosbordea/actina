"""NOAA approximate geometry; fixed +03 labels, preceding-hour integration."""
import calendar
import math
from datetime import timedelta

LATITUDE, LONGITUDE, OFFSET = 34.7744, 32.4229, 3


def position(local, latitude=LATITUDE, longitude=LONGITUDE, offset=OFFSET):
    hour = local.hour + local.minute / 60 + local.second / 3600
    gamma = 2 * math.pi / (366 if calendar.isleap(local.year) else 365) * (local.timetuple().tm_yday - 1 + (hour - 12) / 24)
    equation = 229.18 * (.000075 + .001868 * math.cos(gamma) - .032077 * math.sin(gamma) - .014615 * math.cos(2*gamma) - .040849 * math.sin(2*gamma))
    declination = .006918 - .399912*math.cos(gamma) + .070257*math.sin(gamma) - .006758*math.cos(2*gamma) + .000907*math.sin(2*gamma) - .002697*math.cos(3*gamma) + .00148*math.sin(3*gamma)
    solar_minutes = hour * 60 + equation + 4 * longitude - 60 * offset
    angle = math.radians(solar_minutes / 4 - 180)
    latitude = math.radians(latitude)
    coszen = math.sin(latitude)*math.sin(declination) + math.cos(latitude)*math.cos(declination)*math.cos(angle)
    phase = solar_minutes / 1440 * 2 * math.pi
    return coszen, math.sin(phase), math.cos(phase)


def solar_features(target, latitude=LATITUDE, longitude=LONGITUDE, offset=OFFSET):
    start = target - timedelta(hours=1)
    samples = [position(start + timedelta(minutes=minute), latitude, longitude, offset)[0] for minute in [5,15,25,35,45,55]]
    _, sine, cosine = position(start + timedelta(minutes=30), latitude, longitude, offset)
    scale = max(100.0, 1000 * math.fsum(max(c,0) for c in samples) / 6)
    return scale, math.fsum(samples) / 6, sine, cosine
