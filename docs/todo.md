# Developments
◉   UI prompt for destination: switch arrival.departure
◉   Prompt for « drifting away »
◉   Prompt for heading towards taxiways.
◉   For each light: closing counter and away counter for distance
◉   Global index counter.
◉   Test window close and redisplay.
◉   Algorithm to not stop after runway crossing.
◉   Ramps vs. Vertex of type « both ».
◉   Runways as list of buttons (3 lines of 4 max.)
◯   (Warning: do not take into account airport restrictions.)
◉   Route: 1. Try without runway, then 2. try with taxi-on-runway.
◉   Turf.nearestpointtoline.
◉   Green path to exit runway without U turn.
◉   Test for plane on runway.
◉   Test for ILS zones. Should stop before zones.
◉   Rabbit
◯   Lights (alternating yellow/green) when leaving runway and on ils areas
◯   Report alerts if crosses stop bar
◉   Better rabbit
◉   Better lights
◉   Offer « API » so that someone else could « clear » current FTG when holder.
◯   add greens from taxiway to ramp and vice-versa
◯   Add alt to aircraft position
◯   Smooth turns
◉   Check new route exists before cancelling old one.
◉   Add tryAgain pop up.
◉   Reset lastLit in flight loop.
◉   Add a MaxLightsLit to only light that amount of lights in front of the plane. If 0, lights all lights until stop bar.


# Logged info

1. FTG started.
1. Plane position
1. Airport name
1. Airport has ATC
1. Airport has routing network (# nodes, # edges)
1. Request departure/arrival to DEST.
1. Route found.
1. Lights placed, N segments.
1. Segment # lit.
1. Stop bar # cleared.
1. Terminated successfully. (One more happy pilot.)
1. Cancelled by pilot.

