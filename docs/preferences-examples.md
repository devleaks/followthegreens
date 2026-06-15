# Preferences

This is a collection of preference snippet with a short description.

## Adding Verbose Information for Debugging

```
# lower value is more verbose
LOGGING_LEVEL = 20  # default value
```


## Using Alternate Follow the greens at Specific Airport

```
[Airports.EBBR]
DISTANCE_BETWEEN_GREEN_LIGHTS = 8.0
USE_THRESHOLD = true
```


## Using Alternate Follow the greens for Aircraft Type

```
[Aircrafts.A21N]
VISUAL_RANGE.RANGE = [80, 120]   # in meters
VISUAL_RANGE.LIMITS = [70, 220]
```


## Using Alternate Follow the greens for Aircraft Class

```
# Classes are A (smaller aircraft) to F (A380)
[Aircrafts.F]
VISUAL_RANGE.RANGE = [80, 120]   # in meters
VISUAL_RANGE.LIMITS = [70, 220]
```


## Different First and Last Lights in Follow the greens

```
Lights.FIRST = "taxi_y.obj"
Lights.LAST = "taxi_r.obj"
```


## Alternate Object Light (no light, just the object)

```
Lights.OFF = "path/to/favourite-taxiway-light.obj"  # OBJ8 file
```


## Alternate Custom Omnidirectional Light

```
[Lights.TAXIWAY]
name="custom_white.obj"  # created in lights folder
color=[1, 1, 1]   # red, green, blue
size=30  # 20 is default
intensity=30  # 20 is default
```


## Alternate Custom Taxiway Light

```
[Lights.TAXIWAY_ALT]
taxiway = "r:2"  # first letter must be g (default), r, or y, number: 1 is default
```


