# X-Plane Follow the Greens 4D Plugin

Follow the greens (FtG) is a (real-life) taxiway guidance system.

It works by highlighting taxiway lights in front of the aircraft.
The pilot only has to follow the green lights, and stop on red lights.

But there is more now. There is a 4th dimension now. Read on.

Wow, wow, wow. 4D…!?

Space. The final frontier.


# Follow the greens

Follow the greens is a enhancement to airport infrastructure to ease ground operations.
It is an aid for ground movement, to indicate to pilots where and how to circulate on taxiways without ATC communication.

ATC Ground operators will highlight the taxi path the pilot has to follow with center taxiway green lights.
A red line across the taxiway indicates the aircraft has to hold and wait for the red light to clear.
Very much like car traffic lights.

Follow the greens is part of the serious _Advanced Surface Movement Guidance and Control System_ (A-SMGCS).

Please have a look at the [following video](https://vimeo.com/101564135) and search for "airport Follow the greens" to get more information.
See [http://followthegreens.com](http://followthegreens.com) if you are interested.
There is nowaways a lot more information, manufacturers, and experimental project reports to learn from.

Follow the greens has numerous advantages discussed in the above documents, ranking to ease of use, to smoother taxi rides,
to lower interaction with ground control.

Yeah, yeah, less fuel use also.

Yeah, yeah, less CO2 produced too.

Yeah, yeah, follow the greens is realllly green. Can't be greener.

Seriously. No green bashing.

I found amusing to bring Follow the greens concept to X-Plane as ATC and "AI" struggle to guide you on the ground.
X-Plane yellow painted coach arrows on taxiways are fine, useful, but look too artificial.

Follow the greens is an existing system used at a handful airports.
But now, thanks to this plugin, even your local muni can get Follow the greens _(at no cost)_.


# 4D !?

Yes 4D. Nowadays, you don’t sell anything if it isn’t 4D or AI-based.
So FtG is 4D.

After reading [this paper](https://www.sciencedirect.com/science/article/pii/S0968090X19311404),
I found it amusing to incorporate their model and suggestions into FtG.

Please notice the _« over hype »_ of _4D_ trajectories 🤣.
FtG 1 is 2D (lateral guidance on the ground...), FtG 2 adds time information to get you there on time, that’s just a third dimension.
FtG won’t ask you to fly to your holding position. Yet.
(🤔 we may here have a definite path for improvement in a future release.)

In a nutshell, FtG will now monitor your taxi speed and invite you to adjust it.
It will do so by adjusting the speed of the «rabbit» light in front of the aircraft,
and the length of the rabbit run.
If the rabbit runs fast and far, you can safely accelerate your taxi pace.
If the rabbit is slow and short, you must reduce your speed because you are probably nearing a sharp turn or a mandatory stop.

Could it be simpler?
Follow the greens.
Try to catch the rabbit.


## Should I upgrade to 4D?

If you're X-Plane 11, you cannot. Sorry.

If you’re rather safely go through your pre-takeoff checklist while taxiing,
gently blow the daffodils on the sides of the taxiway with warm air,
take your time to get to the runway, you can stick with FtG Release 1.

But if you want to maximise your air time, never loose time in those unnecessary long runs around the airport,
if you’d rather taxi at just below _vr_ speed, give Release 2 a try.
And monitor your brakes temperature.


## What's New in Release 2

Release 2 is called _Follow the greens 4D_ (and may be abbreviated FtG4D).

- Follow the greens «rabbit» light speed and length automagically adjusted to invite pilots to speed up or slow down taxi ride.
- A few parameters can be adjusted in a configuration file.
- Routing algorithms attempt to respect taxiway network constraints.
- Better taxiway network specification, which leads to better route finding.
- FtG specific log file created to help us improve the plugin in case of trouble.


# Installation

FtG plugin is a «python plugin».
Therefore, you first need to install the [XPPython3 plugin](https://xppython3.readthedocs.io/en/latest/).

FtG Release 2 will not work on X-Plane 11 because it uses newer X-Plane SDK features
available through the latest releases of XPPython3 plugin.

For the Release 2 of FtG, Version 4.5 or above of the XPPython3 plugin is required.
Newer version of XPPython3 contains all you need to run Python plugin,
including a version of the python language interpreter.
There is no need to install other software.

Once the XPPython3 plugin is installed and working,
download the [FtG plugin code](https://github.com/devleaks/followthegreens/releases) and unzip it.

Place both the file `PI_Followthegreens.py` and the folder `followthegreens` in `<X-Plane 12 Folder> / resources / plugins / PythonPlugins`.

That's it.

Reload python scripts and you are all set.

When X-Plane is running and a plane is loaded, check the _Plugin_ menu item at the top.
It should now contain a _Follow the greens..._ menu item.


# Usage

Please refer to the manual [here](https://devleaks.github.io/followthegreens/) for detailed usage instructions.
There are also a few documented parameters you can adjust to your liking.

There are a few requirements for FtG to work.
For example, the airport must have a network of taxiways defined in X-Plane.

To start Follow the greens, call the plugin menu item _Follow the greens..._.
Follow instructions in the dialog boxes.

There is a little tip for runway and parking stand selection.

To select your destination, *first click inside the input text box to set focus there*,
*then use UP and DOWN arrow keys to cycle through proposed valid destinations*.

If you hit a text key or a number key, selection jumps to the first matching destination.
Only the *first key you type* is used to jump to the first matching destination.

I apoligize for the poor user interface.
It is developed with standard X-Plane user interface elements,
which do not include sophisticated widgets like menu boxes.

The (main and unique) user interface window of _Follow the greens_ is designed to disappear after a few seconds of inactivity.
Select Follow the greens in the plugin menu to display it again.

You can assign Follow the greens action to a key or button.
It is equivalent to selecting X-Plane Plugin menu entry.

# Changelog

## Release 2

- [2.2.1](https://github.com/devleaks/followthegreens/releases) - ??-??-2026 - First publicly available Release 2. Monitoring aircraft speed, recommending target speed range for taxiing.
- ... (numerous development releases with little interest for production system...)
- 2.0.0 - 29-DEC-2025 - Added hooks for 4D FtG, updated README.


## Release 1

- [1.7.0](https://github.com/devleaks/followthegreens/releases/tag/1.7.0) - 14-JAN-2026 - Last Release 1 version (will only provide critical fixes).
- 1.6.6 - 21-FEB-2024 - Added Cancel and OK (finish, bye, etc.) commands
- 1.6.5 - 20-FEB-2024 - Now opening all files as UTF-8 files. Code blackened.
- ...
- 1.0.0 - 01-APR-2021 - Initial release.


# License

FtG is MIT license. Feel free to use, copy, distribute, but please do not sell.
Fun is priceless.


# Help

Bug reports, comments, suggestions are always welcome.
Please use the forum here or [github issue](https://github.com/devleaks/followthegreens/issues).

Taxi safely.

Follow the greens.

# Weekly digest

Follow the greens is now «4D».
[Instructions and download.](https://forums.x-plane.org/files/file/71124-follow-the-greens/)

Follow the greens (FtG) is a (real-life) taxiway guidance system.
It works by highlighting taxiway lights in front of the aircraft.
The pilot only has to follow the green lights, and stop on red lights.

The new _«4D»_ release monitors aircraft taxi speed and invite the pilot to adapt it
by adjusting the speed and the length of the run of the «rabbit» light in front of the aircraft.
If the rabbit runs fast and far, pilot can safely accelerate the taxi pace.
If the rabbit is slow and short, pilot brake because nearing a sharp turn or a mandatory stop.
