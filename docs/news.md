# What's New?


## Follow the greens

For Follow the greens, nothing as changed compared to previous versions,
with the notable exception of user interface changes.

It is now possible to start Follow the greens with a better user interface
and change most important options from the user interface.

There are little options and little adjustments for Follow the greens.
Everything is very straightforward.

While monitoring aircraft movements, adjustments like variation
of the pulsating light frequency and number of lights visible in front of the aircraft
occurs automatically. Always. With no option or human intervention.

Follow the greens is automatic magic added to your taxi ride.


*The most remarkable change is the now available "Use Follow Me car instead of taxiway green lights"
for guidance.*

Your preference. Your choice.


## Follow Me Car

The Follow Me car is an addition to Follow the greens.
It is now possible to follow a car rather that green pulsing taxiway lights in front of the aircraft.

The car follows the _exact same path_ as the greens indicates.
Route finding is done by the exact same algorith as the one
used for Follow the greens.

The challenge of the Follow Me car is driving the car!

The car has
 - to follow the path, of course,
 - but also stop at holding positions,
 - remain at visible distance in front of the aircraft,
 - move as realistically as possible,
 - accelerate, brake, turn smoothly,
 - provide indications to the aircraft.

This involves monitoring the aircraft movement and speed,
and adjusting the behavior of the car accordingly.

Sounds simple. But not easy to code effectively.
Not easy to code while maintaining computation minimal to not hit the frame rate.

Car moves independently of other vehicle,
and is not aware of existing traffic, aircraft and ground support vehicle.

The car almost exclusively follow the taxi route.
It sometimes runs through everything when a new route is requested to join the new route.
In this case, if does not follow taxiways
or airport service roads, it drives in a straight line to its new position.


## X-dispatch Integration

[X-dispatch](https://x-dispatch.app) is a spectacular flight dispatching application
that allows you to plan and prepare your flight and then
launch X-Plane to execute that flight.

X-dispatch allows for taxi planning on both departure and arrival.
Taxi planning, route finding can either be automatic, or manual.
The manual planning allows to draw an arbitrary taxi path.
Taxi route is saved into a file.

If available, Follow the greens will read that file and
highlight the taxi route provided by X-dispatch,
whether is was automatically computed or manually drawn.

