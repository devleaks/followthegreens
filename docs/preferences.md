# Advanced Preference Set up

A number of FtG parameters are exposed as _Preferences_.
It means that chaing the value of a preference will modify the behavior and aspect of FtG.

Please recall that setting inappropriate values may cause FtG to malfunction,
degrade X-Plane overall performances, even make X-Plane crash in some instances.


# How Preferece Works

Preferences are read each time a new FtG guidance session is started.

FtG opens the following preference file:

`<X-Plane 12 Folder> / Output / preferences / followthegreens.prf`

If not found, there simply won't be any preference set up.
FtG will create an empty file at that location for later use.

If a preference file is found, loaded preferences are logged in the ftglog.txt file.


# Preference Hierarchy

Some preferences can be set at different level.
For example, the length of the rabbit can be set

1. At the global, FtG level,
1. At the level of a given airport,
1. At the level of an aircraft model.

In the above example, the value of the preference is the value found at the highest level,
global first, particular last.


# Global Preferences

Global preferences are set at the highest level and apply to the entire FtG system.

1. ADD_LIGHT_AT_VERTEX (true/false)
1. ADD_LIGHT_AT_LAST_VERTEX (true/false)
1. DISTANCE_BETWEEN_STOPLIGHTS (in meters, a small distance like 1 (dense) to 3 (loose) meters.)


# Airport Preferences

Airports may have particular setup for FtG.
The following preferences can be set at an individual airport level:

1. Distance between taxiway center lights (expressed in meters.)
1. Rabbit speed, including completely disabled by setting the speed to `0`. (Expressed in fraction of a second; would be the same for all aicrafts.)
1. Rabbit length (would be the same for all aicrafts.)
1. Distance between lights when illuminating the whole taxiway network (Show taxiway, expressed in meters.).

To adjust preferences for a precise airport, use the following snippet.
Please notice the use of the airport ICAO code in the preference section part.

```
[Airports.EBBR]
DISTANCE_BETWEEN_GREEN_LIGHTS = 8  # meters
RABBIT_SPEED = 0.1  # seconds

[Airports.EHAM]
LIGHTS_AHEAD = 100  # meters
RABBIT_LENGTH = 100  # meters
DISTANCE_BETWEEN_GREEN_LIGHTS = 12  # meters
```


# Aircraft Preferences

The following preferences are set depending on the detected aircraft type:

1. Rabbit speed
1. Rabbit length
1. (Static) lights ahead of the rabbit

These preferences are always applied, unless a global preference has been imposed.

To adjust aircraft preferences, length must be expressed "physically", with metric units:

For example, for a 40 meter aircraft (A320, B737), rabbit length should be 80m in front of the aircraft,
and lights ahead another 50 meters ahead of the rabbit.

The reason to express aircraft requirements in physical units is that the number of lights
to be used for the rabbit is dependent on other paramters like the distance between lights,
a parameter that may vary from airport to airport, and is not related to an aircraft.

It is possible to adjust the preferences for an entire aircraft category (class `A` to `F`),
or for a specific aircraft ICOA identifier.

```
[Aircrafts.C]
LIGHTS_AHEAD = 100  # meters
RABBIT_LENGTH = 150  # meters
RABBIT_SPEED = 0.20  # seconds

[Aircrafts.A339]
LIGHTS_AHEAD = 200  # meters
RABBIT_LENGTH = 200  # meters
RABBIT_SPEED = 0.20  # seconds
```


# Lights

FtG lights different _types of lights_ at precise location.
You can adjust some of the light parameters to change the size, color, and intensity of each _type of light_.

The different types of lights are:

- FIRST: First light of follow the greens.
- TAXIWAY: Regular "green" taxiway light used for the path and the "rabbit".
- TAXIWAY_ALT: On runway lead-on and lead-off, this is the actual 
- STOP: Lights used to build the stop bar across the taxiway when clearance is requested.
- VERTEX: Additional light added at taxiway network vertex, as published in the airport data file. Used for development mainly.
- WARNING: Additional light, no longer used.
- LAST: Last light of follow the greens.
- ACTIVE: Light on a departure, arrival or ILS active segment.
- DEFAULT: Light used by Show Taxiway to illuminate all taxiways.

To change lights parameters for a type of light, insert the following preference:

```
[Lights.TAXIWAY_ALT]
color = [1.0, 1.0, 0.0]
intensity = 30
size = 20
```

This would change the `TAXIWAY_ALT` light type to a bright yellow light.
