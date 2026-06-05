# Follow Me Car

Follow the greens plugin now offers a Follow Me car as an alternative
to guide aircrafts on the ground.

To get a Follow Me car rather than green taxiway lights indication
select Follow the car... plugin menu entry.


# Follow Me Car Preferences

Follow Me Car was always considered as a side project,
an addition to the core, hi-tech Follow the greens.

 - Follow the greens is A-SMGCS (Advanced Surface Movement Guidance and Control System)
 - A Follow Me Car is also A-SMGCS (_Antique_ Surface Movement Guidance and Control System)



## Follow Me Car Preferences

```
[FollowMeCar]
filename: str = "xcsl/FMC.obj"
above_ground: float = 0.0  # vertical offset for above object

indicator: bool = False  # use additionl indicator
indicator_shift: tuple = (0.0, 0.0)  # offset for indicator (height, forward), in meters

slow_speed: float = 3.0  # turns, careful move, all speed m/s
normal_speed: float = 7.0  # 25km/h
leave_speed: float = 10.0  # expedite speed to leave/clear an area
fast_speed: float = 14.0  # running fast to a destination far away

max_speed: float = 18.0

turn_radius: float = 25.0  # m

acceleration: float = 1.0  # m/s^2, same deceleration
deceleration: float = -1.0  # m/s^2, same deceleration

indicator_warning_distance: float = 50.0  # m
```

Path objects are relative to the `followthegreens` folder.

Follow the greens provides two follow me cars alternative
courtesy of X-CSL team, with permission.
Many thanks to them for their generosity and their hard work.


# Troubleshooting and Limitations

Follow the greens and Follow Me car are software development.
They are subject to limitations and bugs.

Here is a small list of limitations, and known issues.

Follow Me Car are limited in their U-turn capabilities.
They will do it, but almost immediately at their current place.
Turns of more than about 150° are subject to the same limitation.

If lost, or if the aircraft did not follow indicated paths, it might get lost.
Follow the greens provides a instruction to generate, on the fly, a new route
to the desired destination.
It is called "New greens", to create a new route to the same destination.
The new route might not start close to the aircraft, but an alternate route will be provided.

Recall that with a Follow me car, pilot will NOT see the path to destination,
but rather discover it by following the car.

If the new proposed route is not suitable to bring the aircraft back on route,
the pilot may call "New greens" over and over again, until FtG satisfies the requirements.
If the aircraft is moving, new path will be generated and may be more appropriate.

In normal condition, FtG has been tested thouroughly.
Follow the greens, within its known limitations, works reliably.
The addition of Follow me car did not impact Follow the greens.

The Follow Me car is more complicated, because the smooth management of the car
involves numerous tradeoffs are are known to have limitations too, like explained above.

Overall, Follow the greens brings more joy than pain.
In case of trouble, never hesitate to reset it,
and/or reset python scripts through the XPPython3 plugin menu item "Reload scripts".

In case of trouble, please send the `ftg_log.txt` file, along with the `XPPython3Log.txt` file,
to understand what went wrong and we will correct it.


Taxi safely.
