# from https://en.wikipedia.org/wiki/Sunrise_equation
#
from datetime import date, datetime, timedelta, timezone, tzinfo
from math import acos, asin, ceil, cos, degrees, fmod, radians, sin, sqrt
from time import time

from .globals import logger


def _ts2human(ts: int | float, debugtz: tzinfo | None) -> str:
    return str(datetime.fromtimestamp(ts, debugtz))


def j2ts(j: float | int) -> float:
    return (j - 2440587.5) * 86400


def ts2j(ts: float | int) -> float:
    return ts / 86400.0 + 2440587.5


def _j2human(j: float | int, debugtz: tzinfo | None) -> str:
    ts = j2ts(j)
    return f"{ts} = {_ts2human(ts, debugtz)}"


def _deg2human(deg: float | int) -> str:
    x = int(deg * 3600.0)
    num = f"∠{deg:.3f}°"
    rad = f"∠{radians(deg):.3f}rad"
    human = f"∠{x // 3600}°{x // 60 % 60}′{x % 60}″"  # N.B. not correct for negative x
    return f"{rad} = {human} = {num}"


def calc(
    current_timestamp: float,
    f: float,
    l_w: float,
    elevation: float = 0.0,
    *,
    debugtz: tzinfo | None = None,
) -> tuple[datetime, datetime, bool]:
    logger.log(7, f"Latitude               f       = {_deg2human(f)}")
    logger.log(7, f"Longitude              l_w     = {_deg2human(l_w)}")
    logger.log(7, f"Now                    ts      = {_ts2human(current_timestamp, debugtz)}")

    J_date = ts2j(current_timestamp)
    logger.log(7, f"Julian date            j_date  = {J_date:.3f} days")

    # Julian day
    # TODO: ceil ?
    n = ceil(J_date - (2451545.0 + 0.0009) + 69.184 / 86400.0)
    logger.log(7, f"Julian day             n       = {n:.3f} days")

    # Mean solar time
    J_ = n + 0.0009 - l_w / 360.0
    logger.log(7, f"Mean solar time        J_      = {J_:.9f} days")

    # Solar mean anomaly
    # M_degrees = 357.5291 + 0.98560028 * J_  # Same, but looks ugly
    M_degrees = fmod(357.5291 + 0.98560028 * J_, 360)
    M_radians = radians(M_degrees)
    logger.log(7, f"Solar mean anomaly     M       = {_deg2human(M_degrees)}")

    # Equation of the center
    C_degrees = 1.9148 * sin(M_radians) + 0.02 * sin(2 * M_radians) + 0.0003 * sin(3 * M_radians)
    # The difference for final program result is few milliseconds
    # https://www.astrouw.edu.pl/~jskowron/pracownia/praca/sunspot_answerbook_expl/expl-4.html
    # e = 0.01671
    # C_degrees = \
    #     degrees(2 * e - (1 / 4) * e ** 3 + (5 / 96) * e ** 5) * sin(M_radians) \
    #     + degrees(5 / 4 * e ** 2 - (11 / 24) * e ** 4 + (17 / 192) * e ** 6) * sin(2 * M_radians) \
    #     + degrees(13 / 12 * e ** 3 - (43 / 64) * e ** 5) * sin(3 * M_radians) \
    #     + degrees((103 / 96) * e ** 4 - (451 / 480) * e ** 6) * sin(4 * M_radians) \
    #     + degrees((1097 / 960) * e ** 5) * sin(5 * M_radians) \
    #     + degrees((1223 / 960) * e ** 6) * sin(6 * M_radians)

    logger.log(7, f"Equation of the center C       = {_deg2human(C_degrees)}")

    # Ecliptic longitude
    # L_degrees = M_degrees + C_degrees + 180.0 + 102.9372  # Same, but looks ugly
    L_degrees = fmod(M_degrees + C_degrees + 180.0 + 102.9372, 360)
    logger.log(7, f"Ecliptic longitude     L       = {_deg2human(L_degrees)}")

    Lambda_radians = radians(L_degrees)

    # Solar transit (Julian date)
    J_transit = 2451545.0 + J_ + 0.0053 * sin(M_radians) - 0.0069 * sin(2 * Lambda_radians)
    logger.log(7, f"Solar transit time     J_trans = {_j2human(J_transit, debugtz)}")

    # Declination of the Sun
    sin_d = sin(Lambda_radians) * sin(radians(23.4397))
    # cos_d = sqrt(1-sin_d**2) # exactly the same precision, but 1.5 times slower
    cos_d = cos(asin(sin_d))

    # Hour angle
    some_cos = (sin(radians(-0.833 - 2.076 * sqrt(elevation) / 60.0)) - sin(radians(f)) * sin_d) / (cos(radians(f)) * cos_d)
    try:
        w0_radians = acos(some_cos)
    except ValueError:
        return None, None, some_cos > 0.0
    w0_degrees = degrees(w0_radians)  # 0...180

    logger.log(7, f"Hour angle             w0      = {_deg2human(w0_degrees)}")

    j_rise = J_transit - w0_degrees / 360
    j_set = J_transit + w0_degrees / 360

    logger.log(7, f"Sunrise                j_rise  = {_j2human(j_rise, debugtz)}")
    logger.log(7, f"Sunset                 j_set   = {_j2human(j_set, debugtz)}")
    logger.log(7, f"Day length                       {w0_degrees / (180 / 24):.3f} hours")

    return datetime.fromisoformat(_ts2human(j2ts(j_rise), debugtz)), datetime.fromisoformat(_ts2human(j2ts(j_set), debugtz)), True


def daylight(timeutc: datetime, latitude: float, longitude: float, elevation=0.0) -> bool:
    sunrise, sunset, ignore = calc(time(), latitude, longitude, elevation, debugtz=timezone.utc)
    if sunrise is None or sunset is None:
        logger.warning(f"problem during calc({timeutc}, {latitude}, {longitude}, {elevation})")
        return True
    logger.debug(f"{sunrise} < {timeutc} < {sunset}")
    return sunrise < timeutc < sunset
