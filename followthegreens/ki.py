# Wrapper around OneD kinetic equation, with logging
#
from typing import Optional

# https://github.com/MED-1996/kinematics5
from .oned import eq1, eq2, eq3, eq4

from .globals import logger


def f(a: float | None) -> float | str:
    if a is None:
        return "none"
    return round(a, 1)


def leq1(
    initial_velocity: Optional[int | float] = None, final_velocity: Optional[int | float] = None, acceleration: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:
    logger.debug(f"eq1: initial_velocity={f(initial_velocity)}m, final_velocity={f(final_velocity)}, acceleration={f(acceleration)}, time={f(time)}")
    r = eq1(initial_velocity=initial_velocity, final_velocity=final_velocity, acceleration=acceleration, time=time)
    logger.debug(f"eq1: {r}")
    return r


def leq2(
    displacement: Optional[int | float] = None, initial_velocity: Optional[int | float] = None, final_velocity: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:
    logger.debug(f"eq2: displacement={f(displacement)}m, initial_velocity={f(initial_velocity)}, final_velocity={f(final_velocity)}, time={f(time)}")
    r = eq2(displacement=displacement, initial_velocity=initial_velocity, final_velocity=final_velocity, time=time)
    logger.debug(f"eq2: {r}")
    return r


def leq3(
    displacement: Optional[int | float] = None, initial_velocity: Optional[int | float] = None, acceleration: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:
    logger.debug(f"eq3: displacement={f(displacement)}m, initial_velocity={f(initial_velocity)}, acceleration={f(acceleration)}, time={f(time)}")
    r = eq3(displacement=displacement, initial_velocity=initial_velocity, acceleration=acceleration, time=time)
    logger.debug(f"eq3: {r}")
    return r


def leq4(
    displacement: Optional[int | float] = None,
    initial_velocity: Optional[int | float] = None,
    final_velocity: Optional[int | float] = None,
    acceleration: Optional[int | float] = None,
) -> tuple | bool:
    logger.debug(f"eq4: displacement={f(displacement)}m, initial_velocity={f(initial_velocity)}, final_velocity={f(final_velocity)}, acceleration={f(acceleration)}")
    r = eq4(displacement=displacement, initial_velocity=initial_velocity, final_velocity=final_velocity, acceleration=acceleration)
    logger.debug(f"eq4: {r}")
    return r


def getTime(displacement: float, initial_velocity: float, final_velocity: float) -> float:
    r = leq2(displacement=displacement, initial_velocity=initial_velocity, final_velocity=final_velocity, time=None)
    return r[3]


def getDistance(initial_velocity: float, final_velocity: float, acceleration: float) -> float:
    r = leq4(displacement=None, initial_velocity=initial_velocity, final_velocity=final_velocity, acceleration=acceleration)
    return r[0]
