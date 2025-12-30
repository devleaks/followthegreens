# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
import logging
from datetime import datetime

import xp

from .globals import (
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    WARNING_DISTANCE,
)

logger = logging.getLogger("follow_the_greens")

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
        self.diftingLimit = (
            5 * DISTANCE_BETWEEN_GREEN_LIGHTS
        )  # After that, we send a warning, and we may cancel FTG.
        self.last_updated = datetime.now()
        self.rabbit_mode = 0  # faster, normal, slower [-2, 2]?

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
            # if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
            #     logger.debug(f"Checking menu {self.ftg.pi.menuIdx}..")
            #     xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Checked)
            #     logger.debug(f"..checked")
            # else:
            #     logger.debug(f"menu not checked (index {self.ftg.pi.menuIdx})")
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
            # if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
            #     logger.debug(f"Unchecking menu {self.ftg.pi.menuIdx}..")
            #     xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Unchecked)
            #     logger.debug(f"..unchecked")
            # else:
            #     logger.debug(f"menu not checked (index {self.ftg.pi.menuIdx})")
        else:
            logger.debug("plane not tracked.")

    def rabbitMode(self, mode: str):
        # Need to add a function to NOT change rabbit too often, once every 10 secs. is a minimum
        MAX_UPDATE_FREQUENCY = 10  # seconds
        now = datetime.now()
        delay = (now - self.last_updated).total_seconds()
        if delay < MAX_UPDATE_FREQUENCY:
            logger.debug(
                f"must wait {round(MAX_UPDATE_FREQUENCY - delay, 2)} seconds before changing rabbit"
            )
            return

        if self.rabbitRunning:
            xp.destroyFlightLoop(self.flrabbit)
            self.rabbitRunning = False
            logger.debug("rabbit stopped before adjustments")
        else:
            logger.debug("rabbit not running.")

        self.ftg.lights.rabbitMode(mode)
        self.last_updated = now

        phase = xp.FlightLoop_Phase_AfterFlightModel
        # @todo: make function to reset lastLit counter
        self.lastLit = 0
        params = [phase, self.rabbitFLCB, self.refrabbit]
        self.flrabbit = xp.createFlightLoop(params)
        xp.scheduleFlightLoop(self.flrabbit, 1.0, 1)
        self.rabbitRunning = True
        logger.debug("rabbit restarted after adjustments")

    def adjustSpeed(self, speed, position):
        # Check if speed of aircraft is optimum
        # Next vertex: distance, expected turn angle at vertex
        # Min taxi speed 5kt, absolute max taxi speed 30kt
        # Accelerate of more than 200m from turn, break if closer
        # Max turn speed = function(turn angle)
        return False

    def rabbitFLCB(
        self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon
    ):
        # pylint: disable=unused-argument
        # show rabbit in front of plane.
        # plane is supposed to Follow the greens and it close to green light index self.lastLit.
        # We cannot use XP's counter because it does not increment by 1 just for us.
        return self.ftg.lights.rabbit(self.lastLit)

    def planeFLCB(
        self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon
    ):
        # pylint: disable=unused-argument
        # monitor progress of plane on the green. Turns lights off as it does no longer needs them.
        # logger.debug('%2f, %2f, %d', elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter)
        self.ftg.ui.hideMainWindowIfOk(elapsedSinceLastCall)

        pos = self.ftg.aircraft.position()
        if not pos or (pos[0] == 0 and pos[1] == 0):
            logger.debug("no position.")
            return self.nextIter

        # Monitor aircraft speed and adjust rabbit speed
        spd = self.ftg.aircraft.speed()
        if self.adjustSpeed(pos, spd):
            self.changeRabbit(0, 0, 0)

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

        if self.lastLit == closestLight and (
            abs(self.distance - distance) < DISTANCE_BETWEEN_GREEN_LIGHTS
        ):  # not moved enought, may even be stopped
            return self.nextIter

        # @todo
        # Need to send warning when pilot moves away from the green.

        self.distance = distance
        return self.nextIter
