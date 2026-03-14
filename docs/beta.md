# Notes to Beta Testers

# Logging

FtG logs everything in a file called ftg_log.txt in the folder `followthegreens`.

If you have an issue, please submit this file with the issue.

Please DO ALSO INCLUDE the `XPPython3Log.txt` file as well as it contains Python specific errors
(that might not prevent FtG from working).


# Developer Mode

If preference

```
DEVELOPER_PREFERENCE_ONLY = true
```

is set, only the developer preference file is read and NOT the user one.
It also sets a few development features, see below.


# Follow Me Car Tests

Follow me car is available for testing.

If preference

```
DEVELOPER_PREFERENCE_ONLY = true
```

is set, the Follow Me Car is working TOGETHER WITH Follow the greens (i.e. green lights are visible.)
If not set or false (default value), Follow me car has a normal behavior.

## Normal Behavior

To get a Follow Me Car you have to set preferences as follow:

Either globally:

```
RABBIT_SPEED = 0
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
```

Or for a specific airport only:

```
[Airports.EBLG]
RABBIT_SPEED = 0
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
MOVEMENT = "arrival"
```

It is possible to get a follow me car for Arrival or Departure only with the MOVEMENT preference (default is both).

When NOT using a FMC for both movements, the opposite movement (without the FM car) uses the global default
for lights_ahead, rabbit length and speed. (since it is not possible to specify it otherwise)


# Follow Me Car Preferences

```
[FollowMeCar]
filename = "xcsl/FMC.obj"  # "xcsl/FMC.obj", "xcsl/FMC2.obj", "follow_me/fm_van.obj"
indicator = true
indicator_shift = [1.95, -0.70]  # both in meters
# [height above ground, distance forward from center of above car object (distance can be negative to move backwards)]
turn_radius = 22.0  # m
normal_speed = 10  # m/s
```


Taxi safely
