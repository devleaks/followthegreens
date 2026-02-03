# X-Plane Follow the Greens 4D Plugin

Follow the greens (FtG) is a (real-life) taxiway guidance system.
It is part of the modern _Advanced Surface Movement Guidance and Control System_ (A-SMGCS).
It currently is implemented in at several large airports like London, Dubai, Munich, Seoul and Frankfurt soon.

The system works by highlighting taxiway lights in front of the aircraft.
The pilot only has to follow the green lights, and stop on red lights.

But there is more now, there is a 4th dimension.

Space. The final frontier? _Time_. The ultimate frontier.


# Follow the greens

Follow the greens is a enhancement to airport infrastructure to ease ground operations.
It is an aid for ground movement, to indicate to pilots where and how to circulate on taxiways without ATC communication.

ATC Ground operators will highlight the taxi path the pilot has to follow with center taxiway green lights.
A red line across the taxiway indicates the aircraft has to hold and wait for the red light to clear.
Very much like car traffic lights.

Please have a look at the [following video](https://vimeo.com/101564135) and search for "airport Follow the greens" to get more information.
There is nowaways a lot more information, manufacturers, and experimental project reports to learn from.

Follow the greens has numerous advantages discussed in the above documents, ranking to ease of use, to smoother taxi rides,
shorter taxi times, to lower interaction with ground control.

Less fuel use, less CO2 produce, follow the greens is realllly green.
Can't be greener. No green bashing.

This plugin brings the Follow the greens concept to X-Plane to guide you on the ground.
X-Plane yellow painted coach arrows on taxiways are fine, but look too artificial.
Follow the greens does the same thing but with a real-life existing system.

Follow the greens is already used at several airports (OMDB, EGLL, EDDM, RKSI... _soon_ at EDDF).
Thanks to this plugin, even your local muni can get Follow the greens _at no cost_.


# 4D !?

Yes 4D. Nowadays, you don’t sell anything if it isn’t 4D or AI-based.
So FtG is 4D.

After reading [this paper](https://www.sciencedirect.com/science/article/pii/S0968090X19311404),
I implemented their idea into FtG.

In a nutshell, FtG will now monitor your taxi speed and invite you to adjust it.
It will do so by adjusting the speed of the «rabbit» light (the pulsating light) in front of the aircraft,
and the length of the rabbit «run».
If the rabbit runs fast and far, you can safely accelerate your taxi pace.
If the rabbit is slow and short, you must reduce your speed because you are probably nearing a sharp turn or a mandatory stop.

It currently only monitor your speed and recommand to adjust it.
It does not enforce meeting time slot requirements (but it easily could).


Please notice the _« over hype »_ of _4D_ trajectories 🤣.
FtG 1 is 2D (lateral guidance on the ground...), FtG 2 adds time information to get you there on time, that’s just a third dimension.
FtG won’t ask you to fly to your holding position. Yet.
(🤔 we may here have a definite path for improvement in a future release.)

Follow the greens 4D is an A-SMGCS Level 4 compliant experimental system only used at X-Plane airports.

Could it be simpler?
Follow the greens.
Try to catch the rabbit.


## What's New in Release 2

Release 2 called _Follow the greens 4D_ (FtG4D) adds the following improvements:

- Follow the greens _rabbit_ light speed and length automagically adjusted to invite pilots to speed up or slow down taxi ride.
- Preferences can be adjusted in a file.
- Runway light intensity can be adjusted, even turned off while FtG4D is running.
- Improved routing algorithm attempt to respect taxiway network constraints (taxiway width, one ways...).
- New commands to interact with FtG4D.
- FtG4D specific log file created to help improve the plugin in case of misbehavior.


# Installation

FtG Release 2 will not work on X-Plane 11 because it uses newer X-Plane SDK features
available through the latest releases of XPPython3 plugin.

FtG plugin is a _Python_ plugin.
Therefore, you first need to install the [XPPython3 plugin](https://xppython3.readthedocs.io/en/latest/).
Release 4.5 or above of the XPPython3 plugin is requested.
Newer version of XPPython3 contains all you need to run Python plugin,
including a version of the python language interpreter.
There is no need to install other software.

Once the XPPython3 plugin is installed and working,
download the [FtG plugin code](https://github.com/devleaks/followthegreens/releases) and unzip it.

Place both file `PI_Followthegreens.py` and folder `followthegreens` in `<X-Plane 12 Folder> / resources / plugins / PythonPlugins`.

That's it.

Reload python scripts and you are all set.

When X-Plane is running and a plane is loaded, check the _Plugin_ menu item at the top.
It should now contain a _Follow the greens..._ menu item.


# Usage

Please refer to the [manual](https://devleaks.github.io/followthegreens/) for detailed usage instructions.
There are also a few documented parameters you can adjust to your liking.

There are a few requirements for FtG to work.
For example, the airport must have a network of taxiways defined in X-Plane.

To start Follow the greens, call the plugin menu item _Follow the greens..._.
Follow instructions in the dialog boxes.

There is a little tip for runway and parking stand selection to go around X-Plane native UI limitations.

To select your destination, *first click inside the input text box to set focus there*,
*then use UP and DOWN arrow keys to cycle through proposed valid destinations*.

If you hit a text key or a number key, selection jumps to the first matching destination.
Only the *first key you type* is used to jump to the first matching destination.

I apologize for the poor user interface.
It is developed with standard X-Plane user interface elements,
which do not include sophisticated widgets like menu boxes.

The (main and unique) user interface window of _Follow the greens_ is designed to disappear after a few seconds of inactivity.
Select Follow the greens in the plugin menu to display it again.

You can assign Follow the greens actions to keys or buttons.


# Help

First [read the manual](https://devleaks.github.io/followthegreens/).

Bug reports, comments, suggestions are always welcome.

Please use the forum here ([comments section](https://forums.x-plane.org/files/file/71124-follow-the-greens/?tab=comments)),
the [discord server](https://discord.gg/AQjP2tWV),
or [github issue](https://github.com/devleaks/followthegreens/issues).

Taxi safely.

Follow the greens.


# Changelog

## Release 2

- [2.2.0](https://github.com/devleaks/followthegreens/releases) - ??-??-2026 - Follow the greens monitors aircraft taxi speed and advise to speed up or slow down.
- (...development releases...)
- 2.0.0 - 29-DEC-2025 - Added hooks for FtG _4D_.


## Release 1

- [1.7.0](https://github.com/devleaks/followthegreens/releases/tag/1.7.0) - 14-JAN-2026 - Last Release 1 version (will only provide critical fixes). Works on X-Plane 11 and order version of XPPython3 plugin.

- 1.6.6 - 21-FEB-2024 - Added Cancel and OK (finish, bye, etc.) commands
- ...
- 1.0.0 - 01-APR-2021 - Initial release.

[Detailed Changelog](https://devleaks.github.io/followthegreens/changelog/)

# License

FtG is MIT license. Feel free to use, copy, distribute, but please do not sell.
Fun is priceless.


# Weekly digest

Follow the greens is now «4D».
[Instructions and download.](https://forums.x-plane.org/files/file/71124-follow-the-greens/)

Follow the greens (FtG) is a (real-life) taxiway guidance system.
It works by highlighting taxiway lights in front of the aircraft.
The pilot only has to follow the green lights, and stop on red lights.

The new *4D* release monitors aircraft taxi speed and invite the pilot to adapt it
by adjusting the speed and the length of the run of the «rabbit» light (pulsating light) in front of the aircraft.
If the rabbit runs fast and far, pilot can safely accelerate the taxi pace.
If the rabbit is slow and short, pilot should slow down because nearing a sharp turn or a mandatory stop.
