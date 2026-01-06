# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
from datetime import datetime

import xp

from .globals import (
    AMBIANT_RWY_LIGHT,
    logger,
    RABBIT_MODE,
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    WARNING_DISTANCE,
    RUNWAY_LIGHT_LEVEL_WHILE_FTG,
    AMBIANT_RWY_LIGHT_CMDROOT,
)

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
        self._rabbit_mode = RABBIT_MODE.MED
        self.runway_level_original = 1

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

        # Dim runway lights according to preferences
        if self.planeRunning and self.ftg.airport_light_level is not None:
            self.runway_level_original = xp.getDataf(self.ftg.airport_light_level)
            cmdref = xp.findCommand(AMBIANT_RWY_LIGHT_CMDROOT + RUNWAY_LIGHT_LEVEL_WHILE_FTG)
            if cmdref is not None:
                xp.commandOnce(cmdref)
                currlevel = xp.getDataf(self.ftg.airport_light_level)
                logger.debug(f"runway lights preference set to {RUNWAY_LIGHT_LEVEL_WHILE_FTG} (original={self.runway_level_original}, during FtG={currlevel})")

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

        # Restore runway lights according to what it was
        if not self.planeRunning:
            level = AMBIANT_RWY_LIGHT.HIGH
            currlevel = self.runway_level_original
            if self.ftg.airport_light_level is not None:
                currlevel = xp.getDataf(self.ftg.airport_light_level)
            if currlevel != self.runway_level_original:
                if self.runway_level_original == 0:
                    level = AMBIANT_RWY_LIGHT.OFF
                elif self.runway_level_original <= 0.25:
                    level = AMBIANT_RWY_LIGHT.LOW
                elif self.runway_level_original <= 0.5:
                    level = AMBIANT_RWY_LIGHT.MED
                logger.debug(f"new level {level} ({currlevel} => {self.runway_level_original})")
                cmdref = xp.findCommand(AMBIANT_RWY_LIGHT_CMDROOT + level)
                if cmdref is not None:
                    xp.commandOnce(cmdref)
                    checklevel = xp.getDataf(self.ftg.airport_light_level)
                    logger.debug(f"runway lights restored to {level} (during FtG={currlevel}, after FtG={checklevel})")
                else:
                    logger.debug(f"runway lights command not found {AMBIANT_RWY_LIGHT_CMDROOT + level}")
            else:
                logger.debug(f"runway lights no need to restore ({currlevel} vs. {self.runway_level_original})")

    @property
    def rabbitMode(self) -> RABBIT_MODE:
        return self._rabbit_mode

    @rabbitMode.setter
    def rabbitMode(self, mode: RABBIT_MODE):
        # Need to add a function to NOT change rabbit too often, once every 10 secs. is a minimum
        if self.rabbitMode == mode:
            return
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
        self._rabbit_mode = mode
        self.last_updated = now
        logger.debug(f"rabbit mode set to {mode}")

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
        # Note: 20kt~=10.29m/s, 1m/s~=1.94kt
        SPEED_SLOW = 1.0 # m/s
        SPEED_FAST = 10.0
        if speed < SPEED_SLOW:
            self.rabbitMode = RABBIT_MODE.FASTER
        elif speed > SPEED_FAST:
            self.rabbitMode = RABBIT_MODE.SLOWER

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


        nextStop, warn = self.ftg.lights.toNextStop(pos)
        if nextStop and warn < WARNING_DISTANCE:
            logger.debug("closing to stop.")
            self.rabbitMode = RABBIT_MODE.SLOW
            if not self.ftg.ui.isMainWindowVisible():
                logger.debug("showing UI.")
                self.ftg.ui.showMainWindow(False)
        else:
            # Monitor aircraft speed and adjust rabbit speed
            spd = self.ftg.aircraft.speed()
            self.adjustSpeed(pos, spd)

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
