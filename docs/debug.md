# Follow the Greens Debugging

Follow the greens writes usage information in a log file named `ftg_log.txt`.

The log file is located in the home directory of Follow the greens plug in.

In case of misbehavior of the plugin, it is necessary to increase the level of information
sent to the `ftg_log.txt` file.

On startup, Follow the greens plugin created a preference file named `followthegreens.prf` located in

```
<X-Plane 12>
    /Output
        /preferences
            followthegreens.prf  (Preference file)
```

The plain text file, TOML formatted, and can be edited with a text editor.
In this file, ensure there is a line like so:

```
LOGGING_LEVEL = 10
```

with no `#` sign at the start of the line.

The lower the `LOGGING_LEVEL` number value the more information is stored into the `ftg_log.txt` file.
Some other additional files may also be created to help debugging, like:

```
<X-Plane 12>
    log.txt                              <--- X-Plane log file
    XPPython3Log.txt                     <--- XPPython3 plugin log file
    /Resources
        /plugins
            /PythonPlugins/
                PI_FollowTheGreens.py
                /followthegreens/
                ftg_log.txt              <--- Follow the greens log file
                ftg_ls.geojson           <--- more Follow the greens log file
                ftg_route.geojson        
                ftg_smooth_route.geojson
                ftg_srvertices.geojson
                ...
```

GeoJSON files contain geographic information like paths, object positions, etc.
and can be visualized on sites like geojson.io.

# Important

When reporting an issue, please make sure you always transfert the following files:

```
<X-Plane 12>
    log.txt                              <--- X-Plane log file
    XPPython3Log.txt                     <--- XPPython3 plugin log file
    /Resources
        /plugins
            /PythonPlugins/
                ftg_log.txt              <--- Follow the greens log file
```

You can compress the three files in a zip archive for example.

Many thanks for your help.

Taxi safely.
