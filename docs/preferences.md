# Advanced Preference Set up

A number of FtG parameters are exposed as _Preferences_.
It means that chaing the value of a preference will modify the behavior ans aspect of FtG.


Please recall that setting inappropriate values may cause FtG to malfunction,
degrade X-Plane overall performances, even make X-Plane crash in some instances.

# How Preferece Works

Preferences are read on startup of FtG, each time it is called for a new FtG guidance session.

If the preference file

`<X-Plane 12 Folder> / Resources / plugins / PythonPlugins / followthegreens / followthegreens.prf`

is found, it is used. If not found there, FtG tries to open the following preference file:

`<X-Plane 12 Folder> / Output / preferences / followthegreens.prf`

If not found, there simply won't be any preference set up.

If a preference file is found, loaded preferences are logged in the ftglog.txt file.


# Preference Hierarchy

Some preferences can be set a different level.
For example, the length of the rabbit can be set

1. At the global, FtG level,
1. At the level of a given airport,
1. At the level of an aircraft model.

In the above example, the value of the preference is the value found at the highest level.


# Global Preferences

Global preferences are set at the highest level and apply to the entire FtG system.

1. ADD_LIGHT_AT_VERTEX (true/false)
1. ADD_LIGHT_AT_LAST_VERTEX (true/false)
1. DISTANCE_BETWEEN_STOPLIGHTS (in meters, a small distance like 1 (dense) to 3 (loose) meters.)


# Airport Preferences

Airports may have particular setup for FtG.
The following preferences can be set at an individual airport level:

1. Distance between taxiway center lights (Expressed in meters.)
1. Rabbit speed, including completely disabled by setting the speed to `0`. (Expressed in fraction of a second.)
1. Distance between lights when illuminating the whole taxiway network (Show taxiway, expressed in meters.).


# Aircraft Preferences

The following preferences are set depending on the detected aircraft type:

1. Rabbit speed
1. Rabbit length
1. (Static) lights ahead of the rabbit

These preferences are always applied, unless a global preference has been imposed.

For aircraft preferences, length must be expressed "physically", with metric units:

For example, for a 40 meter aircraft (A320, B737), rabbit length should be 80m in front of the aircraft,
and lights ahead another 50 meters ahead of the rabbit.

The reason to express aircraft requirements in physical units is that the number of lights
to be used for the rabbit is dependent on other paramters like the distance between lights,
a parameter that may vary from airport to airport, and not related to an aircraft.
