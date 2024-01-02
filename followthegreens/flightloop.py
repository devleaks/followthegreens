# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
import logging

import xp

from .globals import PLANE_MONITOR_DURATION, DISTANCE_BETWEEN_GREEN_LIGHTS, WARNING_DISTANCE

logger = logging.getLogger(__name__)

EARTH = 39940653000  # Earth circumference, in meter :-)


class FlightLoop:
    def __init__(self, ftg):
        self.ftg = ftg
        self.refrabbit = "FollowTheGreen:rabbit"
        self.flrabbit = None
        self.rabbitRunning = False
        self.refplane = "FollowTheGreen:plane"
        self.flplane = None
        self.planeRunning = False
        self.nextIter = PLANE_MONITOR_DURATION  # seconds
        self.lastLit = 0
        self.distance = EARTH
        self.diftingLimit = 5 * DISTANCE_BETWEEN_GREEN_LIGHTS  # After that, we send a warning, and we may cancel FTG.

    def startFlightLoop(self):
        # @todo schedule/unschedule without destroying
        phase = xp.FlightLoop_Phase_AfterFlightModel
        # @todo: make function to reset lastLit counter
        self.lastLit = 0
        if not self.rabbitRunning:
            params = [phase, self.rabbitFLCB, self.refrabbit]
            self.flrabbit = xp.createFlightLoop(params)
            xp.scheduleFlightLoop(self.flrabbit, 1.0, 1)
            self.rabbitRunning = True
            logger.debug("rabbit started.")
        else:
            logger.debug("rabbit running.")
        if not self.planeRunning:
            params = [phase, self.planeFLCB, self.refplane]
            self.flplane = xp.createFlightLoop(params)
            xp.scheduleFlightLoop(self.flplane, 10.0, 1)
            self.planeRunning = True
            logger.debug("plane tracking started.")
        else:
            logger.debug("plane tracked.")

    def stopFlightLoop(self):
        if self.rabbitRunning:
            xp.destroyFlightLoop(self.flrabbit)
            self.rabbitRunning = False
            logger.debug("rabbit stopped.")
        else:
            logger.debug("rabbit not running.")
        if self.planeRunning:
            xp.destroyFlightLoop(self.flplane)
            self.planeRunning = False
            logger.debug("plane tracking stopped.")
        else:
            logger.debug("plane not tracked.")

    def rabbitFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # show rabbit in front of plane.
        # plane is supposed to Follow the greens and it close to green light index self.lastLit.
        # We cannot use XP's counter because it does not increment by 1 just for us.
        return self.ftg.lights.rabbit(self.lastLit)

    def planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # monitor progress of plane on the green. Turns lights off as it does no longer needs them.
        # logger.debug('%2f, %2f, %d', elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter)
        self.ftg.ui.hideMainWindowIfOk(elapsedSinceLastCall)

        pos = self.ftg.aircraft.position()
        if not pos or (pos[0] == 0 and pos[1] == 0):
            logger.debug("no position.")
            return self.nextIter

        nextStop, warn = self.ftg.lights.toNextStop(pos)
        if nextStop and warn < WARNING_DISTANCE:
            logger.debug("closing to stop.")
            if not self.ftg.ui.isMainWindowVisible():
                logger.debug("showing UI.")
                self.ftg.ui.showMainWindow(False)

        closestLight, distance = self.ftg.lights.closest(pos)
        if not closestLight:
            logger.debug("no close light.")
            return self.nextIter

        # logger.debug("closest %d %f", closestLight, distance)
        if closestLight > self.lastLit and distance < self.diftingLimit:  # Progress OK
            # logger.debug("moving %d %d", closestLight, self.lastLit)
            self.lastLit = closestLight
            self.distance = distance
            return self.nextIter

        if self.lastLit == closestLight and (abs(self.distance - distance) < DISTANCE_BETWEEN_GREEN_LIGHTS):  # not moved enought, may even be stopped
            return self.nextIter

        # @todo
        # Need to send warning when pilot moves away from the green.

        self.distance = distance
        return self.nextIter
