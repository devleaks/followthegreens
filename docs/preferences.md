# Advanced Preference Set up

A number of FtG parameters are exposed as _Preferences_.
It means that changing the value of a preference will modify the behavior and aspect of FtG.

*Please recall that setting inappropriate values may cause FtG to malfunction,
degrade X-Plane overall performances, even make X-Plane crash in some instances.*


# How Preferece Works

Preferences are read each time a new FtG guidance session is started.

FtG opens the following preference file:

`<X-Plane 12 Folder> / Output / preferences / followthegreens.prf`

If not found, there simply won't be any preference set up.
FtG will create an empty file at that location for later use.

If a preference file is found, loaded preferences are logged in the ftg_log.txt file.


## Preference Raffinements

Some preferences only exists at the global level and cannot be further adjusted.
They are mainly application level preferences.
Example of such preference is the `ADD_LIGHT_AT_VERTEX` (true or false) to add a green light
at each taxiway vertex.

Some other preferences can be set at the global level, but also at either the airport level,
or the aircraft type level.
Example of such preference is the length of the rabbit light (pulsating light)
in front of the aircraft: `RABBIT_LENGTH`.
The pilot of a smaller aircraft may necessit less lights in front of her/him,
than the pilot of a B747 or A380.


# Preference Hierarchy

If a value is defined at the highest, global level, particular values are not taken into account.

If you want to modify a value at an airport level, you have to leave global value to its default value,
and the particular airport value will be taken into account.
Same applies for aircraft specific values.

THe idea for airport-level values is realism.
There are different realization of Follow the greens.
Some airport may have green light paths, but no rabbit.
Some other airport may only have a short rabbit and no light ahead.
(Both exists.)

The idea for aircraft-level values is practical.
For some aircraft types, the generic value be inappropriate.
Pilots of large aircraft may appreciate a longer rabbit run, and more light ahead
than the number provided by default to anticipate route and turns.
A pilot of a general aviation aircraft will not see the rabbit light 300 meter ahead.
This is why FtG allows for aircraft type specific value set, for the confort of the pilot.


# Global Preferences

Global preferences are set at the highest level and apply to the entire FtG system.

1. RABBIT_LENGTH
1. LIGHTS_AHEAD

However, a particular airport or aircraft may adjust them also.


These global preferences can be adjusted at the global level
but cannot be adjusted at a particular level:

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
RABBIT_SPEED = 0.2  # seconds

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

# Summary

Table summary with preference, where the preference is supplied,
and units used for the preference.

| Preference                      | Global          | Airport        | Aircraft Class    | Aircraft Type      | 
|---------------------------------|-----------------|----------------|-------------------|--------------------|
| TOML «TABLE»                    |                 | [Airport.ICAO] | [Aircraft.C]      | [Aircraft.ICAO]    |
| ------------------------------- | --------------- | ----------     | ----------------- | ------------------ |
| LIGHTS_AHEAD                    | # lights        | # lights       | distance(meters)  | distance(meters)   |
| RABBIT_LENGTH                   | # lights        | # lights       | distance(meters)  | distance(meters)   |
| RABBIT_SPEED                    | seconds         | seconds        | seconds           | seconds            |
| RUNWAY_LIGHT_LEVEL_WHILE_FTG    | lo,med,hi,off   | lo,med,hi,off  | NA                | NA                 |
| DISTANCE_BETWEEN_GREEN_LIGHTS   | meters          | meters         | NA                | NA                 |
| DISTANCE_BETWEEN_LIGHTS         | meters          | meters         | NA                | NA                 |
| DISTANCE_BETWEEN_STOPLIGHTS     | meters          | meters         | NA                | NA                 |
| ADD_LIGHT_AT_VERTEX             | true/false      | NA             | NA                | NA                 |
| ADD_LIGHT_AT_LAST_VERTEX        | true/false      | NA             | NA                | NA                 |


# Lights

FtG lights different _types of lights_ at precise location.
You can adjust some of the light parameters to change the size, color, and intensity of each _type of light_.

The different types of lights are:

- FIRST: First light of follow the greens.
- TAXIWAY: Regular "green" taxiway light used for the path and the "rabbit".
- TAXIWAY_ALT: On runway lead-on and lead-off, same as TAXIWAY light but yellow/amber.
- STOP: Lights used to build the stop bar across the taxiway when clearance is requested (same as TAXIWAY light but red.).
- VERTEX: Additional light added at taxiway network vertex, as published in the airport data file. Used for development mainly.
- WARNING: Additional light, no longer used, a yellow taxiway light.
- LAST: Last light of follow the greens.
- ACTIVE: Light on a departure, arrival or ILS active segment.
- DEFAULT: Light used by Show Taxiway to illuminate all taxiways, default to a bright white light.

To change lights parameters for a type of light, insert the following preference:

```
[Lights.TAXIWAY_ALT]
color = [1.0, 1.0, 0.0]  # (r, g, b), values in [0, 1] range
intensity = 20  # default value
size = 20  # default value
```

This would change the `TAXIWAY_ALT` light type to a bright yellow light.
(The above preference will effectively _create_ a new light with a random name with the supplied paramters and load it.)


## Alternate Light Object File

To use another object light, you must use the following syntax:

```
Lights.TAXIWAY_ALT = "path/to/personal-object-light.obj"
```

It is not the same as

```
[Lights.TAXIWAY_ALT]
name = "path/to/personal-object-light.obj"
```

which would _create_ a file named `path/to/personal-object-light.obj`
with default custom light values (color=white, intensity=20, size=20)
as explained above.

Path objects are relative to the `followthegreens` folder.

## Visible Taxiway Light

To be complete, there is an extra light type

- OFF: Physical taxiway light object with no light (light off).

If yo wish to replace it with an alternate light object:

Lights.OFF = "path/to/favourite-taxiway-light.obj"

