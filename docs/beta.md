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

Follow me car is available with limited functions.
The car still does not move on its own and follows edges with sharp turn.

If preference

```
DEVELOPER_PREFERENCE_ONLY = true
```

is set, the Follow Me Car is working TOGETHER WITH Follow the greens (i.e. green lights are visible.)
If not set or false (default value), Follow me car has a normal behavior.

To get a Follow Me Car you have to set preferences as follow:

Either globally:

```
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
```

Or for a specific airport only:

```
[Airports.EBLG]
RABBIT_LENGTH = 0
LIGHTS_AHEAD = 42
```

It is not possible to get a follow me car for Arrival or Departure only.
(Mmovement, Departure or Arrival is not an option in preference file. Thinking about it.)


Taxi safely
