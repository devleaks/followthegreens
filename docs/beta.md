# Notes to Beta Testers

Release 2 adds VERY little change.

Code has been refactored heavily but not changed.

Here are the noticable changes:


# Logging

FtG logs everything in a file called ftg_log.txt in the folder `followthegreens`.

If you have an issue, please submit this file with the issue.

Pleas DO INCLUDE the `XPPython3Log.txt` file as well as it contains Python specific errors
(that might not prevent FtG from PARTIALLY working).


# Rabbit Loop

Rabbit Loop has had little change. I just added a clean stop function and a clean restart function.


# Flight Loop

Flight loop as 1 big change: The is now an extra fuction call to monitor the taxi speed
of the aircraft and change the speed and length of the rabbit depending on the aircrfat speed
and the distance to the next turn or stop. NOTHING MORE.

Upon rabbit speed change, the rabbit is stopped then restarted.

That's it.

That's the only NEW thing in this release.

All other code has been reviewed, refactored, but not logically changed.


# External Configuration

Hooks are provided to allow user to set a few parameters in ftgconfig.toml file.
This is being set up right now. I will decide which parameters can be changed.

Currently, only two parameters can be changed.


# Lights

If you have been using FtG for a long time, you know I struggle and keep struggling with LIGHTS.

I have a solution that works, but it is not very nice looking if people exagerate on parameters.

Here is "my" light:

```
I
800
OBJ

TEXTURE lights.png
TEXTURE_LIT lights.png

POINT_COUNTS    0 0 0 0

# Light repeated to make it brighter
# NAME             X   Y   Z    R   G   B   A   size <s1> <t1> <s2> <t2> dataref
LIGHT_CUSTOM       0   0   0    0.1 1.0 0.1 1   0.2  0.0  0.5  0.5  0.0  UNUSED
```

Key parameters are: RGB, the color, and size.

Size is a relative number. Relative to what? I don't know.
0.2 is large and visible, 0.3 is larger, 0.4 starts to be ugly in rendering (too large)
0.1 is very nice but small and sometimes difficult to see.

The key to bright light is to REPEAT the entire line `LIGHT_CUSTOM...` several times.

How many times? It is up to you! The more, the brighter the light.

The key is to find a combination of size/number of repeat that balances luminosity and rendering of the light.

BUT, it is now possible to have ugly bright light, or discreet nice looking taxi lights.

I'll keep investigting this a few more hours.

In all cases, lights should only differ by colors and be all the same.


# Route Search: STRICT MODE

If strict mode is enabled, the search for a route might take longer, as several searches are conducted
relaxing constraints one after the other.

For example, if we do no find a route when respecting one-ways, we may relax that condition and allow traffic in both ways.
FtG performs a search respecting one ways, then if it does not find a route, perform a second search not respecting one ways.
It does this for all contraints available to it. This might involve performing a few extra route search until one if found.

Non strict mode (default), just find a suitable route on the network of taxiways, not respecting any of the above constraints.
You may therefore by stuck with your A380 on a 15 meter wide taxiway with no U-turn escape. Just call the tow truck.
If you feel uneasy with that, you can enable strict mode.

```
USE_STRICT_MODE = True
```

at the expense of longer route search on large airport.

There is no garantee that strict mode will provide a route that respect all contraints.

- Respect taxiway width
- Use runways (yes / no)
- Respect Oneway or all taxiways are twoway




# Skunkcraft Updater

There are skunkcrafts updater file if you wish but I cannot manage to get a beta version with my setup (github).
So it currently only install the production version.

It might be easier for you to install it, that way each time I push a new update, you just have to skunkcrafts update it.

Just drop `skunkcrafts_updater.cfg` file next to `PI_FollowTheGreens.py`.


