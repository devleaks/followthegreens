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



# Programming of the Follow Me car behavior

To minimize computation in flight loops, the general idea is as follow.

Some computation where already done effectively for Follow the greens.
We dit not change that, we start from the same data set for the Follow Me car (fmc).

To minimize the impact of the these computation,
we carefully monitor the behavior of the aircraft and adjust computation frequency accordingly.

If the aircraft is stopped, or moves fast, no computation other than monitoring its speed occurs.
Typically it is run every 1 to 5 seconds.

This is the _aircraft monitoring flight loop_.
This loop is the same for both Follow the greens and Follow the car.

Observation data from the _aircraft monitoring flight loop_ is passed
to the _follow me car directive flight loop_.

The goal of this flight loop is to set short term directive to the car:
Aim there, accelerate, decelerate, adjust speed, show that sign or turn indicator.
This loop involves computation and is performed as infrequently as possible.
(Typically it is run every 1 to 3 seconds when the follow me car is used.)
Again, the frequency of this loop is dynamic and adjusted to maintain
a smooth car ride.

The Follow Me car behaves autonomously.
It has is own _follow me car control loop_.

The _follow me car control loop_ reads directives from the _follow me car directive flight loop_
and adjust the car behavior to meet them.
This loop is done for each frame to draw the car at it's proper position
with indications visible to the pilot.

The behavior was designed with some safeguards in mind.
If, for some reason, the car is missing information, it smoothly brakes and stops.

# Route

For most of its trip, the FMC follows the lights Follow the greens would have laid.

Two small trips are added for cosmetic reason:
 - On start, the FM car is created next to the aircraft, randomly, on its left or right.
   The car then travel to the estimated stating position in front of the aircraft in a straight line.
   It then either stops and wait for the aircraft to move, or starts giving directions if the aircraft
   is already moving.
 - At the end, when the car reaches the last point of its strip, it continues on a straight line
   for about 200m then turns 90° in the direction if was coming from, continue 50 meters, stops,
   then vanishes. This marks the end if the FM car taxi direction.

FtG permanently monitors the distance between the aircraft and the car and adjusts the speed of the car
to remain in front of the aircraft at a desired distance. Recall that the distance in front is computed
from numerous factors:
 - The size of the aircraft (further if large aircraft)
 - The taxi speed of the aircraft (to remain in front and give a braking distance security)
 - The overall visibility (closer if foggy, etc.)
 - Invitation to acceletate (long straight ride) or slow down (closing to a turn or stop)
 - The car will stop at holding position.

I the car is too far in front, it will slow down, even stop.
If it is too close, there probably is a reason why it stays there: Turn, stop, end of route...

