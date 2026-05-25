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


# Follow me car Jumps

In rare, known circumstances, the Follow Me Car may produce little "jumps" rather than smoothly follow a curve.
This happens when 2 turns are too close to each other, when the first turn "terminates" inside the second turn.
This is a rare event as taxiways are more often large straight lines.
