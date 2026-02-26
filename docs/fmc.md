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

It is not difficult to difficult to place an alternate object
at the very precise position of the light closest to the aircraft.
Or a few lights ahead of this light closest to the aircraft.

This is how Follow Me Car sub project is born.

Same core algorithms to

- Route finding to destination
- Monitoring of current route

but different route indication.
In the case of Follow the greens, all lights are lit.
In the case of Follow Me Car, there is just an indication of
one light ahead of the aircraft, and we replace that light
by .. a FollowMe car.

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

Pursuing that spirit, Follow me car is added as a fun addition:

*After extensive study of ideal number of visible lights ahead, questioning numerous A.I., sources agreed to the same number of lights: It does not matter, as long as you do not use 42 lights. 42 is already used for answering a far more complex question. So we had to come up with a solution in case a pilot requires exactly 42 lights ahead. We came with the solution of using a follow me car instead of the green lights. So if you require no rabbit (rabbit_length=0) and exactly 42 lights ahead (lights_ahead=42), you will see no green lights in front of you but a follow me car instead. We apologise for the inconvenience.*

*Don’t worry, the car will follow the same route as the greens would show you. And it will monitor your speed and invite you to taxi faster if it is far in front of you, and slow down to not being swallowed by your Trent 900+ engine if it is closer to you. Just follow it. Don’t run over it.*

Taxi safely


## Global Addition

If you do not want to use Follow the greens and prefer Follow Me Car,
add the following prefereces at the _global_ level:

```
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
```


## Local Addition

If you prefer to use Follow Me Car as some airport only,
you must add the same preference at an _airport_ level.

```
[Airports.EBLG]
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
```

The above preferences will use Follow the greens at all airports
except at Liège Airport where it will use a Follow Me Car
(as it is the case in real life.)


## Alternate Follow Me Car

An alternate follow me car object can be selected at global
or airport level.

```
[Airports.EBLG]
FMC = "xscl/FMC2.obj"
```

Path objects are relative to the `followthegreens` folder.


Taxi safely