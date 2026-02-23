# https://github.com/MED-1996/kinematics5
from typing import Optional


def __arg_count(local: dict) -> None:
    var_count = 0
    for key in local:
        if local[key] is not None:
            var_count += 1

    if var_count < 3:
        raise Exception(f"Need at least 3 args: [{var_count}]")


# FIRST KINEMATIC EQUATION:
# final_velocity = initial_velocity + (acceleration * time)
def eq1(
    initial_velocity: Optional[int | float] = None, final_velocity: Optional[int | float] = None, acceleration: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:

    __arg_count(locals())

    if time and time < 0:
        raise Exception(f"The time you entered is negative: [{time}]")

    if initial_velocity is None:
        initial_velocity = final_velocity - (acceleration * time)

    elif final_velocity is None:
        final_velocity = initial_velocity + (acceleration * time)

    elif acceleration is None:
        acceleration = (final_velocity - initial_velocity) / float(time)

    elif time is None:
        time = (final_velocity - initial_velocity) / float(acceleration)

        if time < 0:
            raise Exception(f"Time is Negative: [{time}]")

    else:
        _vf = initial_velocity + (acceleration * time)
        err = _vf * 0.01

        if abs(final_velocity - _vf) <= err:
            return True

        return False

    return (float(initial_velocity), float(final_velocity), float(acceleration), float(time))


# SECOND KINEMATIC EQUATION:
# displacement = [(final_velocity + initial_velocity) / 2] * time
def eq2(
    displacement: Optional[int | float] = None, initial_velocity: Optional[int | float] = None, final_velocity: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:

    __arg_count(locals())

    if time and time < 0:
        raise Exception(f"The time you entered is negative: [{time}]")

    if displacement is None:
        displacement = ((final_velocity + initial_velocity) / 2) * time

    elif initial_velocity is None:
        initial_velocity = ((2 * displacement) / float(time)) - final_velocity

    elif final_velocity is None:
        final_velocity = ((2 * displacement) / float(time)) - initial_velocity

    elif time is None:
        time = (2 * displacement) / float(final_velocity + initial_velocity)

        if time < 0:
            raise Exception(f"Time is Negative: [{time}]")

    else:
        _displacement = ((final_velocity + initial_velocity) / 2) * time
        err = _displacement * 0.01

        if abs(displacement - _displacement) <= err:
            return True

        return False

    return (float(displacement), float(initial_velocity), float(final_velocity), float(time))


# THIRD KINEMATIC EQUATION:
# displacement = (initial_velocity * time) + [(0.5) * acceleration * (time ^ 2)]
def eq3(
    displacement: Optional[int | float] = None, initial_velocity: Optional[int | float] = None, acceleration: Optional[int | float] = None, time: Optional[int | float] = None
) -> tuple | bool:

    __arg_count(locals())

    if time and time < 0:
        raise Exception(f"The time you entered is negative: [{time}]")

    if displacement is None:
        displacement = (initial_velocity * time) + (0.5 * acceleration * time * time)

    elif initial_velocity is None:
        initial_velocity = (displacement - (0.5 * acceleration * time * time)) / float(time)

    elif acceleration is None:
        acceleration = (2 * (displacement - (initial_velocity * time))) / float(time * time)

    elif time is None:
        rad = (initial_velocity**2) + (2 * acceleration * displacement)

        if rad < 0:
            raise ValueError("Time Will be a Complex Number.")

        time_1 = ((-1 * initial_velocity) + (rad**0.5)) / float(acceleration)
        time_2 = ((-1 * initial_velocity) - (rad**0.5)) / float(acceleration)

        if time_1 > time_2:
            time = [time_2, time_1]
        else:
            time = [time_1, time_2]

        return (float(displacement), float(initial_velocity), float(acceleration), [float(time[0]), float(time[1])])

    else:
        _displacement = (initial_velocity * time) + (0.5 * acceleration * (time**2))
        err = _displacement * 0.01

        if abs(displacement - _displacement) <= err:
            return True

        return False

    return (float(displacement), float(initial_velocity), float(acceleration), float(time))


# FOURTH KINEMATIC EQUATION:
# [final_velocity ^ 2] = [initial_velocity ^ 2] + [2 * acceleration * displacement]
def eq4(
    displacement: Optional[int | float] = None,
    initial_velocity: Optional[int | float] = None,
    final_velocity: Optional[int | float] = None,
    acceleration: Optional[int | float] = None,
) -> tuple | bool:

    __arg_count(locals())

    if displacement is None:
        displacement = ((final_velocity**2) - (initial_velocity**2)) / float(2 * acceleration)

    elif initial_velocity is None:
        rad = (final_velocity**2) - (2 * acceleration * displacement)

        if rad < 0:
            raise ValueError("Initial Velocity Will be a Complex Number.")

        initial_velocity_1 = rad**0.5
        initial_velocity_2 = -1 * (rad**0.5)

        if initial_velocity_1 > initial_velocity_2:
            initial_velocity = [initial_velocity_2, initial_velocity_1]
        else:
            initial_velocity = [initial_velocity_1, initial_velocity_2]

        return (float(displacement), [float(initial_velocity[0]), float(initial_velocity[1])], float(final_velocity), float(acceleration))

    elif final_velocity is None:
        rad = (initial_velocity**2) + (2 * acceleration * displacement)

        if rad < 0:
            raise ValueError("Final Velocity Will be a Complex Number.")

        final_velocity_1 = rad**0.5
        final_velocity_2 = -1 * (rad**0.5)

        if final_velocity_1 > final_velocity_2:
            final_velocity = [final_velocity_2, final_velocity_1]
        else:
            final_velocity = [final_velocity_1, final_velocity_2]

        return (float(displacement), float(initial_velocity), [float(final_velocity[0]), float(final_velocity[1])], float(acceleration))

    elif acceleration is None:
        acceleration = ((final_velocity**2) - (initial_velocity**2)) / float(2 * displacement)

    else:
        _displacement = ((final_velocity**2) - (initial_velocity**2)) / float(2 * acceleration)
        err = _displacement * 0.01

        if abs(displacement - _displacement) <= err:
            return True

        return False

    return (float(displacement), float(initial_velocity), float(final_velocity), float(acceleration))
