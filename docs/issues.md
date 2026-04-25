# Issues

Here is a list of know issues, problem, limitations.

# Too Far from Taxiway

Problem:

Aircraft need to be less than TOO_FAR = 500m from a taxiway vertex.

Use case:

Aircraft is at end of long runway.
First exit is more than 500m away.

Workaround:

Let aricraft moving forward until it is less that 500m away from taxiway vertex.


# Pause

Follow the Greens plugin does not handle pause.
It keeps running while the simulator is paused.
There should not be any issue with that.
If the aircraft does not move, greens don't change.


# Aircraft Relocation

Follow the Greens takes a «picture» of the situation when a new session is started.
If the aircraft is changed or relocated after the session is started,
pilot should cancel the previous session and restart a new one to take
into account all changes.


# Follow me car Jumps

In rare, known circumstances, the Follow Me Car may produce little "jumps" rather than smoothly follow a curve.
This happens when 2 turns are too close to each other, when the first turn "terminates" inside the second turn.
This is a rare event as taxiways are more often large straight lines.
Solving this event implies loading a substantial helping package (for Bézier curves) not required for other operations.
For simplicity, we chose not to impose that large package, unnecessary in 99% of the time.
