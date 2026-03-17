# Follow Me Car

Surface movement guidance mainly requires

- Route finding to destination
- Route indication
- Monitoring of current route

Follow the greens does all of the above,
proposes to find a new route if an aircraft
runs out of its initial recommanded route.

Route indication is the green lights displayed in front of the aircraft.
And monitoring of current route is performed by detecting the light closest to the aircraft.

It is not difficult to place an alternate _object_
at the very precise position of the light closest to the aircraft.
Or a few lights ahead of this light closest to the aircraft.

This is how Follow Me Car sub project is born.
Placing a car instead of a light at the position a few lights ahead of the light closest to the aircraft.

Same core algorithms to

- Route finding to destination
- Monitoring of current route

but different route indication.
In the case of Follow the greens, all lights are lit.
In the case of Follow Me Car, there is just an indication of
one light ahead of the aircraft, and we replace that light
by .. a Follow Me car.

Above additions to get a Follow Me Car on top of Follow the greens development
took just a few minutes to complete.

Then came the refinements.

## Refinements

- Car cannot simply jump from one light position to the next,
- Car needs to turn smoothly, realistically,
- Car needs to accelerate or brake realistically.

Finally, for simulation, car has to somehow appears when requested
and disappear when no longer needed.

The above refinements took several hours to be added
to the Follow the green core software,
just for the smooth movement of the car.


# How to Get a Follow Me Car

Follow Me Car was always considered as a joke, a side project, an accident,
a funny addition to the core, serious, hi-tech Follow the greens.

 - Follow the greens is A-SMGCS (Advanced Surface Movement Guidance and Control System)
 - A Follow Me Car is also A-SMGCS (_Antique_ Surface Movement Guidance and Control System)

Pursuing that spirit, Follow me car is added as a seriously fun addition:

*After extensive study of ideal number of visible lights ahead, questioning numerous A.I.,
sources agreed to the same number of lights:
It does not matter, as long as you do not use 42 lights.
42 is already used for answering a far more complex question.
So we had to come up with a solution in case a pilot requires exactly 42 lights ahead.
We came with the solution of using a follow me car instead of the green lights.
So if you require no rabbit (rabbit_length=0, rabbit_speed=0) and exactly 42 lights ahead (lights_ahead=42),
you will see no green lights in front of you but a follow me car instead.
For 42 Universal Safety considerations. You understand.
We apologise for the inconvenience.*

*Don’t worry, the car will follow the same route as the greens would show you.
It will monitor your speed and invite you to taxi faster if it is far in front of you,
and you’ll have to slow down if you get closer to it,
to not mill the car with your RR Trent UltraFan engines.
Just follow it, keep a safe distance, don’t run over it.
It is a real 4D Follow Me car.
It might even use its turn indicator lights to warn you of an imminent sharp turn or
display a STOP message when there is a red line ahead.
The car will not run over the stop red lines.
It will also wait for clearance. Just like you.*

*Antique is the new Advanced.*

Taxi safely


## Global Follow Me Car

If you do not want to use Follow the greens and prefer Follow Me Car,
add the following preferences at the _global_ level:

```
RABBIT_LENGTH = 0
RABBIT_SPEED = 0
LIGHTS_AHEAD = 42
```

You will never get Follow the greens, all airports will use Follow Me Car.


## Local Follow Me Car

If you prefer to use Follow Me Car as some airport only,
you must add the same preferences at an _airport_ level.

```
[Airports.EBLG]
RABBIT_LENGTH = 0
RABBIT_SPEED = 0
LIGHTS_AHEAD = 42
```

The above preferences will use Follow the greens at all airports
except at Liège Airport where it will use a Follow Me Car
(as it is in real life.)


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
Turns of more that about 150° are subject to the same limitation.

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
