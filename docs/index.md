# Follow the Greens

Follow the greens is a enhancement to airport infrastructure to ease ground operations.

It is an aid for ground movement, to indicate to pilots where and how to circulate on taxiways without ATC communication.

ATC Ground operators will highlight the taxi path the pilot has to follow with center taxiway green lights.
A red line across the taxiway indicates the aircraft has to hold and wait for the red light to clear.
Very much like car traffic lights.

No more path or taxiway segment names to remember. Just green lights to follow.

Follow the greens is part of the serious _Advanced Surface Movement Guidance and Control System_ (A-SMGCS).

Please have a look at the [following video](https://vimeo.com/101564135) and search for "airport Follow the greens" to get more information.
See [http://followthegreens.com](http://followthegreens.com) if you are interested.
There is nowadays a lot more information, manufacturers, and experimental project reports to learn from.

Follow the greens has numerous advantages discussed in the above videos, ranking to ease of use, to smoother taxi rides,
to lower interaction with ground control.

Yeah, yeah, less fuel use also.

Yeah, yeah, less CO~2~ produced.

Yeah, yeah, follow the greens is realllly green. Can't be greener than that.

Seriously. No green bashing.

I brought Follow the greens concept to X-Plane as ATC and "AI" struggle to guide you on the ground.
X-Plane yellow painted coach arrows on taxiways are fine, useful, but look too artificial.

Follow the greens is an existing system used at a handful airports.
But now, thanks to this plugin, even your local muni can get Follow the greens _(at no cost)_.

Follow the greens is abbreviated FtG.


# Installation

Release 2 will not work on X-Plane 11.
If you want to use Follow the greens on X-Plane 11, you have to use Release 1(.6.7).

FtG plugin is written in the python language.
Therefore, you first need to install the [XPPython3 plugin](https://xppython3.readthedocs.io/en/latest/).

This process is very similar to the Lua language plugin (XLua or FlyithLua) to use Lua scripts.
Here, another language (Python), another plugin (XPPython3).

For the Release 2 of FtG, Version 4.5 of the XPPython3 plugin is required.
Newer version of XPPython3 contain all you need to run Python plugin, including a version of the python language interpreter.
There is no need to install other software.

Once XPPython3 plugin is installed, python plugin scripts are located in

```
<X-Plane 12 Folder> / resources / plugins / PythonPlugins
```

(The XPPython3 plugin itself resides in `<X-Plane 12 Folder> / resources / plugins / XPPython3` folder,
but you should not touch that folder content in any way.)

Download the FtG plugin code and unzip it.

Place both the file `PI_Followthegreens.py` and the folder `followthegreens` in `<X-Plane 12 Folder> / resources / plugins / PythonPlugins`.

That's it.

Reload X-Plane, or the plugins, or the python scripts and you are all set.

When X-Plane is running and a plane is loaded, check the _Plugin_ menu item at the top.
It should now contain a _Follow the greens..._ menu item.

![Plugin Menu](images/menu.png)

For Release 1 users on X-Plane 12 with a recent version of XPPython3,
FtG is a drop-in replacement.


# Usage

To use Follow the greens at an airport facility, there is a little constrain on the airport:
It must have a network of taxiways defined in its airport X-Plane file.
Most airports do.

If an airport does not have a network of taxiways defined in X-Plane,
Follow the greens will tell you so and terminate.

To start follow the greens, you will need to supply some information to it to start.

If you are at a stand location, ready for departure, you will need to supply the runway you are taking-off from.
Follow the greens will light the path the the entrane of the runway.

![Departure dialog](images/departure.png)

If you just landed and roll out, heading for your stand, you will need to supply the stand number.
It must be a stand location known from X-Plane for that airport.
Follow the greens will light the way to the stand.

![Arrival dialog](images/arrival.png)

If you added plugins like [AutoDGS](https://forums.x-plane.org/forums/topic/290222-autodgs-dgs-marshaller-or-vdgs-for-every-gateway-airport/#comment-2569544), you will be guided at the stand by a marshall or a VDG system.

If your path come across an holding position, FtG will indicate the holding position with a red bar of lights
across the taxiway.

When approaching this red line across the taxiway, a dialog box will pop up and ask you to confirm
when you received the clearance to progress.

Follow the greens is not aware of the ATC ground in use, and the ATC ground is not aware of the existance of FtG.
Therefore, when ATC has given clearance and you aknowledged it, you can press the the «Clearance received» button
in the dialog box.

![Clearance dialog](images/clearance.png)

Follow the greens will resume, turn off the red lights and light the next segment of greens.

It will do so until you reach your destination.

That is it. Nothing more. Nothing less.


# What's New in Release 2

After reading [this paper](https://www.sciencedirect.com/science/article/pii/S0968090X19311404),
I found it amusing to incorporate their model and suggestions into FtG.

*Release 2 adds a monitoring of your current taxi speed,
and a variation of the rabbit light speed and length to invite you to either expedite your taxi ride,
or, on the opposite, to slow down before a sharp turn or stop.*

If you’re rather safely go through your pre-takeoff checklist while taxiing,
gently blow the daffodils on the sides of the taxiway with warm air,
take your time to get to the runway, you can stick with Release 1.

But if you want to maximise your air time, never loose time in those unnecessary long runs around the airport,
if you’d rather taxi at just below _v~r~_ speed, give Release 2 a try.
And monitor your brakes temperature.

Please notice the « overhype » with taxi _4D_ trajectories 🤣.
FtG 1 is 2D (lateral guidance on the ground...), FtG 2 adds time information to get you there on time, that’s just a third dimension.
FtG won’t ask you to fly to your holding position.
(🤔 we may here have a definite path for improvement in a future release.)

Nowadays you know, you don’t sell anything if it does not have AI or 4D in its name.
FtG 2.0 is therefore 4D compliant, with `altitude=0` all the way.
There is absolutely not AI, just HFAB (human fun and bugs).

Release 2 no longer works on X-Plane 11 because of the use of new X-Plane SDK API calls and XPPython3 simplifications.
XPPython3 release 4 or above is required.


# Configuration Parameters

Follow the greens exposes a few limited set of preference parameters.
Parameters are specified in a configuration file that can be found at
on of the two following locations:

Either

`<X-Plane 12 Folder> / Resources / plugins / PythonPlugins / followthegreens / ftgconfig.toml`

or

`<X-Plane 12 Folder> / Output / preferences / ftgconfig.toml`

(The first one takes precedence on the second one.)

Here is a template of the configutation file.
It is a [TOML](https://toml.io/en/) formatted file.

```
DISTANCE_BETWEEN_GREEN_LIGHTS = 20  # meters
DISTANCE_BETWEEN_LIGHTS = 40  # meters

LIGHTS_AHEAD = 0   # number of green lights
RABBIT_LENGTH = 10   # number of green lights
RABBIT_DURATION = 0.2   # seconds, no less than 0.1

RUNWAY_LIGHT_LEVEL_WHILE_FTG = "lo"  # off, lo, med, hi
```

Parameters in the above file refer to the following items:

![Parameters](images/parameters.png)


Please note that the values you enter here may affect X-Plane performances (faster rabbit, numerous taxiway lights...)

Here is description of the parameters available for customization.


## Runway Light Intensity Control

While FtG rabbit runs, all runway lights are dimmed to a preference value:

`RUNWAY_LIGHT_LEVEL_WHILE_FTG`

So if you set it to

```
RUNWAY_LIGHT_LEVEL_WHILE_FTG = "lo"
```

all runway lights will be dimmed to low while FtG is running.
Even completely OFF if you choose to do so.
Possible values are `lo`, `med`, `hi` and `off`.

Runway light luminosity will be restored to its original value after FtG terminates.

Alternatively, independently of FtG, runway lights can be dimmed thanks to the following
standard X-Plane commands:

- `sim/operation/rwy_lights_off` (sim/graphics/scenery/airport_light_level=0)
- `sim/operation/rwy_lights_lo` (sim/graphics/scenery/airport_light_level=0.25)
- `sim/operation/rwy_lights_med` (sim/graphics/scenery/airport_light_level=0.5)
- `sim/operation/rwy_lights_hi` (sim/graphics/scenery/airport_light_level=1)


## Automagic Rabbit Speed Control

The goal of Release 2 is to supply taxi speed information to the pilot in addition to the direction (follow the greens).
The speed information is supplied with two _indicators_:

- The *speed of the «rabbit»* (the faster the rabbit, the faster you should run to catch it up, the slower the rabbit, the slower you should go.)
- The *length of the rabbit run* (the longer the rabbit, the more you can keep up with that speed, do not expect speed change.)


The control of the speed works as follow:

From the position of the aircraft, the distance to the next significan turn,
and the type of the aircraft (if available), a speed range is estimated (min value, max value).

- If the aircraft is at or below the minimum range speed, the rabbit will propose to accelerate (run faster). This is indicated by a faster rabbit sequence.
- If the aircraft is at or above the maximum range speed, the rabbit will propose to slow down. This is indicated by a slower rabbit sequence.
- If the aircraft nears a stop light or the end of the greens (at about 200 meters from it), the rabbit will propose to slow down.
- If the aircraft moves at a speed within its estimated range, the rabbit runs at normal speed.

Warning and braking distances are estimeted from the current speed and aircraft type if available.


## Manual Rabbit Speed Control

The speed and length of the rabbit can be controlled by two preference parameters:

```
RABBIT_LENGTH = 10  # number of lights that blink in front of aircraft
RABBIT_DURATION = 0.2  # sec duration of "off" light in rabbit
```

You can manually adjust rabbit speed and length with the following FtG commands:

- `XPPython3/followthegreens/speed_slowest` (length × 2, speed × 2)
- `XPPython3/followthegreens/speed_slower` (normal length, speed × 2, twice slower)
- `XPPython3/followthegreens/speed_med` (normal length, normal speed)
- `XPPython3/followthegreens/speed_faster` (normal length, speed / 2, twice faster)
- `XPPython3/followthegreens/speed_fastest` (length × 2, speed / 2)

If you force the rabbit speed and length using one of the above command,
rabbit auto-tuning will be disabled for this run of Follow the greeens.

- `XPPython3/followthegreens/speed_auto`

will set rabbit mode back to automagic tuning depending on aircraft speed and recommended speed range.


# Notes on Performances

Follow the greens uses little resources.

1. Every 10 seconds or so, FtG checks the aircraft position and speed and adjust greens accordingly. («aircraft flight loop»)
2. The rabbit flight loop» is called more often, depending on the rabbit speed. The faster the rabbit, the more pressure on X-Plane. With 0.2 seconds rabbit, FtG is unnoticable.

One might expect a slight hiccup when looking for a route at a large airport with numerous taxiways.
Hiccup should not last more than one or two seconds in this case.
During the computation, X-Plane seems to freeze for a couple of seconds.


### About Strict Route Search Mode

The goal of FtG is to provide a route from where the aircraft is located to a destination,
either a runway entry, or a parking stand.
It does this by finding a route on a network of taxiways.

But!

Taxiways may have contraints.

1. First, there might be aircraft size/width/weight constraints. A narrow taxiway is not suitable for an airliner.
2. Second, there might be local constrainst like one-way taxiways, taxiways used for inner/outer traffic.
3. Third, runways may sometime be used as taxiways, usually with a U-turn surface at its ends.

X-Plane airport designer sometimes provides detailed taxiway information, sometimes not.

Follow the greens has to cope with what is available in airport definition files.

To do this, a sophisticate algorithm first tries to find a route respecting all constraints.
If no route is found, the algorith will relax some constraints, one by one until a route is found.


# FtG Control and Monitoring

## FtG Commands

FtG adds the follwoing commands:

- `XPPython3/followthegreens/main_windown_toggle`
- `XPPython3/followthegreens/send_clearance_ok`
- `XPPython3/followthegreens/send_cancel`
- `XPPython3/followthegreens/send_ok`
- `XPPython3/followthegreens/highlight_taxiways_toggle`
- `XPPython3/followthegreens/bookmark`


## FtG Monitoring Datarefs

FtG adds the following dataref:

- `XPPython3/followthegreens/is_running`, which is 0 if FtG is not running and 1 when FtG is running,
- `XPPython3/followthegreens/is_holding`, is 1 when FtG expects a clearance to progress.


## Use by External Plugins

Monitoring datarefs and commands are designed to be used by other software to instruct
Follow the greens to proceed. Namely:

- `XPPython3/followthegreens/is_holding` is meant to be used by other plugins to let them know FtG is waiting for clearance.
- `XPPython3/followthegreens/send_clearance_ok` is the command to be used by other plugins to signal FtG that the clearance was received.


# See Also

[Developer notes](devnotes.md).

[Changelog](changelog.md)

![FtG Logo](images/ftg.png)

Taxi safely