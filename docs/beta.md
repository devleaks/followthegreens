# Notes to Beta Testers

Release 2 adds VERY little change.

Code has been refactored heavily but not changed.

Here are the noticable changes:


# Logging

FtG logs everything in a file called ftg_log.txt in the folder `followthegreens`.

If you have an issue, please submit this file with the issue.


# Rabbit Loop

Rabbit Loop has had little change. I just added a clean stop function and a clean restart function.


# Flight Loop

Flight loop as 1 big change: The is not an extra fuction call to monitor the taxi speed
of the aircraft and change the speed and length of the rabbit depending on the aircrfat speed
and the distance to the next turn or stop. NOTHING MORE.

Upon rabbit speed change, the rabbit is stopped then restarted.

That's it.

# External Configuration

Hooks are provided to allow user to set a few parameters in ftgconfig.toml file.
This is being set up right now. I will decide which paramters can be changed.


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

