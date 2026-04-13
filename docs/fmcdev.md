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



# Ahead RANGE

Initial range for a given aircraft or aircraft class (A-F).

First adjustment for aircraft speed:

```
if acf_speed > 10:
    f = 1.5
    r = [r[0] * f, r[1] * f]
```

Second adjustment for visibility (asymmetric):

```
f = 1
if visibility < 500:
    f = 0.5
    r = [l[0], r[1] * f]
if visibility < 1000:
    f = 0.5
    r = [r[0] * f, r[1] * f]
elif visibility < 1500:
    f = 0.75
    r = [r[0] * f, r[1] * f]
```

Third adjustment for rabbit_mode (= acf speed monitor, invite to accelerate/brake):

```
RABBIT_FACTOR = {
    RABBIT_MODE.SLOWEST: 0.50,  # invite to go slow
    RABBIT_MODE.SLOWER: 0.70,
    RABBIT_MODE.MED: 1.00,
    RABBIT_MODE.FASTER: 1.25,
    RABBIT_MODE.FASTEST: 1.5    # invite to go faster
}
r[0] *= RABBIT_FACTOR[rabbit_mode]
r[1] *= RABBIT_FACTOR[rabbit_mode]

```

Each step is clipped to absolute max range [30, 200].

```
HARDCODED_AHEAD_LIMITS = [30, 200]
r[0] = max(r[0], HARDCODED_AHEAD_LIMITS[0])
r[1] = min(r[1], HARDCODED_AHEAD_LIMITS[1])

```

# Ahead

```
ahead = acf_length * 1.5 + acf_speed * 10.0  # in meters
```

Ahead clipped to above estimated range.

Examples:

- Aircraft slow, ahead small, but lower bound of clipping invite to go faster (or not!).
- Aircraft normal, ahead normal, within range, no clipping.
- Aircraft fast, ahead large, need to brake: small range, ahead clipped to lower value.


# FM Car Speed Control

The speed of the car is adjusted to have the car remain between the ahead range.


## Architecture

There are two loops to control the speed of the car.
 - Strategic Loop (run from aircraft position flight loop)
 - Technical Loop (run every frame)


### Strategic Loop

Loop compute not very often the *aim speed* of the car.



### Technical Loop

At each frame or so, speed of the car is progressively adjusted from current speed towards *aim speed*.



## Issues

When rabbit mode changes, ahead ranges changes abruptly, leading to abrupt speed changes to conform to rules.

