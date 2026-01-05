# Follow the Greens

Welcome.

Follow the greens is a enhancement to airport infrastructure to ease ground operations.

It is an aid for ground movement, to indicate to pilots where and how to circulate on taxiways.

In a nutshell, whenever a pilot request taxi instructions, she or he solely receives "Please Follow the greens".

Ground operators will highlight the taxi path the pilot has to follow with center taxiway green lights.
A red line across the taxiway indicates the aircraft has to hold and wait for the red light to clear.
Very much like car traffic lights.

No more path or taxiway segment names to remember. Just green lights to follow.

Follow the greens is part of the serious _Advanced Surface Movement Guidance and Control System_ (A-SMGCS).

Please have a look at the following video (https://vimeo.com/101564135) and search for "airport Follow the greens"
to get more information (http://followthegreens.com).
There are nowaways a lot more information, manufacturers, and pilot project reports to learn from.

Follow the greens has numerous advantages discussed in the above videos, ranking to ease of use, to smoother taxi rides,
to lower interaction with ground control.

I found amusing to bring Follow the greens concept to X-Plane as ATC and "AI" struggle to guide you on the ground.

X-Plane yellow painted coach arrows on taxiways are fine, useful but look too artificial.
Follow the greens is an existing system used at a handful airports.
But now, thanks to this plugin, even your local muni can get Follow the greens (at no cost).

Follow the greens is abbreviated FtG.

# Installation

FtG plugin is written in the python language.
Therefore, you first have to install the XPPython3 plugin to allow for use of python plugins.

This process is very similar to the Lua language plugin (XLua or FlyithLua) to use Lua scripts.
Here, another language (Python), another language plugin (XPPython3).

Version 4 or the XPPython3 plugin is required. These versions contain all you need to run Python plugin.
There is no need to install other software.

Once XPPython3 plugin is installed, plugins written in the python language are located in

```
<X-Plane 12 Folder> / resources / plugins / PythonPlugins
```

(The XPPython3 plugin itself resides in `<X-Plane 12 Folder> / resources / plugins / XPPython3` folder.)

Download the FtG plugin code and unzip it.

Place both the file `PI_Followthegreens.py` and the folder `followthegreens` in `<X-Plane 12 Folder> / resources / plugins / PythonPlugins`.

That's it.

Reload X-Plane, or the plugins, or the python scripts and you are all set.

When X-Plane is running and a plane is loaded, check the _Plugin_ menu item at the top.
It should now contain a _Follow the greens..._ menu item. 

# Usage

# New in Release 2

Release 2 no longer works on X-Plane 11 because of the use of new XSDK API calls.

XPPython3 release 4 or above is required.

# Rationale for Release 2

After reading this paper (https://www.sciencedirect.com/science/article/pii/S0968090X19311404),
I found it amusing to incorporate their model and suggestions into FtG.

Please notice their « overhype » with _4D_ trajectories 🤣.

FtG 1 is 2D (latitude and longitude guidance on the ground...), FtG 2 adds time information, that’s just a third dimension.
FtG won’t ask you to fly to your holding position.
(🤔 we may here have a definite path for improvement in a future release.)

Nowadays you know, you don’t sell anything if it does not have AI or 4D in its name.
FtG 2.0 is therefore 4D compliant, with alt=0 all the way.
There is absolutely not AI, just HF (human fun).

If you’re rather safely go through your pre-takeoff checklist while taxiing,
gently blow the daffodils on the sides of the taxiway with warm air,
take your time to get to the runway, you can stick with Release 1.

But if you want to maximise your air time, never loose time in those unnecessary long runs around the airport,
if you’d rather taxi at just below vr speed, give Release 2 a try.
And monitor your brakes temperature.


## Runway Light Control

While FtG rabbit runs, all runway lights are dimmed to a preference value:

RUNWAY_LIGHT_LEVEL_WHILE_FTG

So if you set it to

RUNWAY_LIGHT_LEVEL_WHILE_FTG = AMBIANT_RWY_LIGHT.LOW

all runway lights will be dimmed to low while FtG is running.

Runway light luminosity will be restored to its original value after FtG terminates.

Alternatively, independently of FtG, runway lights can be dimmed thanks to following X-Plane commands:

Preset runway lights to
      - sim/operation/rwy_lights_off (sim/graphics/scenery/airport_light_level=0)
      - sim/operation/rwy_lights_lo (sim/graphics/scenery/airport_light_level=0.25)
      - sim/operation/rwy_lights_med (sim/graphics/scenery/airport_light_level=0.5)
      - sim/operation/rwy_lights_hi (sim/graphics/scenery/airport_light_level=1)


## Rabbit Speed

The speed and length of the rabbit can be controlled by two preference parameters:

RABBIT_LENGTH = 10  # number of lights that blink in front of aircraft
RABBIT_DURATION = 0.2  # sec duration of "off" light in rabbit


You can manually adjust rabbit speed with the following FtG commands:

    - XPPython3/followthegreens/speed_slow (length x 2, speed x 2)
    - XPPython3/followthegreens/speed_slower (normal length, speed x 2, twice slower)
    - XPPython3/followthegreens/speed_med (normal length, normal speed)
    - XPPython3/followthegreens/speed_faster (normal length, speed / 2, twice faster)
    - XPPython3/followthegreens/speed_fast (length x 2, speed / 2)

## Automagic Rabbit Speed Control

The goal of Release 2 is to supply taxi speed information to the pilot in addition to the direction (Follow the greens).

In this first instance, the control of the speed is simplified as such:

- If the aircraft is at or below 15 knots, the rabbit will propose to accelerate (run faster). This is indicated by a faster rabbit sequence.
- If the aircraft is at or above 25 knots, the rabbit will propose to slow down. This is indicated by a slower rabbit sequence.
- IF the aircraft nears a slop bar (at about 200 meters from it), the rabbit will also propose to slow down.

Between 15 and 25 knots on a straight taxiway, the rabbit will run at normal speed.

In a later release, speed indication will be refined to anticipate sharp turns (at slow speed) or long, straight taxiways.


# FtG Control and Monitoring

FtG adds the follwoing commands:

    - XPPython3/followthegreens/main_windown_toggle
    - XPPython3/followthegreens/send_clearance_ok
    - XPPython3/followthegreens/send_cancel
    - XPPython3/followthegreens/send_ok
    - XPPython3/followthegreens/highlight_taxiways_toggle


FtG adds the following dataref:

    - XPPython3/followthegreens/is_running

which is 0 if FtG is not running and 1 when FtG is running.


# Developer Notes

(in another file.)