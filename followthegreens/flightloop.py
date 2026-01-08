# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
from datetime import datetime

import xp

from .globals import (
    logger,
    RABBIT_MODE,
    SPEED_SLOW,
    SPEED_FAST,
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    WARNING_DISTANCE,
    RUNWAY_LIGHT_LEVEL_WHILE_FTG,
    AMBIANT_RWY_LIGHT_CMDROOT,
    AMBIANT_RWY_LIGHT,
)
from .geo import EARTH, Point, distance


class FlightLoop:
    def __init__(self, ftg):
        self.ftg = ftg
        self.refrabbit = "FtG:rabbit"
        self.flrabbit = None
        self.rabbitRunning = False
        self.refplane = "FtG:aircraft"
        self.flplane = None
        self.planeRunning = False
        self.nextIter = PLANE_MONITOR_DURATION  # seconds
        self.lastLit = 0
        self.distance = EARTH
        self.diftingLimit = 5 * DISTANCE_BETWEEN_GREEN_LIGHTS  # After that, we send a warning, and we may cancel FTG.
        self.last_updated = datetime.now()
        self._rabbit_mode = RABBIT_MODE.MED
        self._may_adjust_rabbit = True
        self.runway_level_original = 1

    def startFlightLoop(self):
        # @todo schedule/unschedule without destroying
        phase = xp.FlightLoop_Phase_AfterFlightModel
        # @todo: make function to reset lastLit counter
        self.lastLit = 0

        if self.has_rabbit():
            if not self.rabbitRunning:
                params = [phase, self.rabbitFLCB, self.refrabbit]
                self.flrabbit = xp.createFlightLoop(params)
                xp.scheduleFlightLoop(self.flrabbit, 1.0, 1)
                self.rabbitRunning = True
                logger.debug(f"rabbit started ({self._rabbit_mode}).")
            else:
                logger.debug(f"rabbit running ({self._rabbit_mode}).")
        else:
            logger.debug("no rabbit requested.")

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
        ll = self.ftg.get_config("RUNWAY_LIGHT_LEVEL_WHILE_FTG")
        if self.planeRunning and self.ftg.airport_light_level is not None:
            self.runway_level_original = xp.getDataf(self.ftg.airport_light_level)
            cmdref = xp.findCommand(AMBIANT_RWY_LIGHT_CMDROOT + ll)
            if cmdref is not None:
                xp.commandOnce(cmdref)
                currlevel = xp.getDataf(self.ftg.airport_light_level)
                logger.debug(f"runway lights preference set to {ll} (original={self.runway_level_original}, during FtG={currlevel})")

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
                    level = AMBIANT_RWY_LIGHT.MEDIUM
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

    def has_rabbit(self) -> bool:
        return self.ftg.lights.has_rabbit() if self.ftg.lights is not None else False

    def allow_rabbit_autotune(self):
        self._may_adjust_rabbit = True
        logger.debug("rabbit adjustment authorized")

    def disallow_rabbit_autotune(self):
        self._may_adjust_rabbit = False
        logger.debug("rabbit adjustment forbidden")

    @property
    def rabbitMode(self) -> RABBIT_MODE:
        return self._rabbit_mode

    @rabbitMode.setter
    def rabbitMode(self, mode: RABBIT_MODE):
        # Need to add a function to NOT change rabbit too often, once every 10 secs. is a minimum
        if not self.has_rabbit():
            return
        if self.rabbitMode == mode:
            return
        if not self._may_adjust_rabbit:
            logger.info("rabbit adjustment forbidden")
            return
        MAX_UPDATE_FREQUENCY = 10  # seconds
        now = datetime.now()
        delay = (now - self.last_updated).total_seconds()
        if delay < MAX_UPDATE_FREQUENCY:
            logger.info(f"must wait {round(MAX_UPDATE_FREQUENCY - delay, 2)} seconds before changing rabbit")
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

    def adjustRabbitSimple(self):
        logger.debug("adjusting rabbit.. (simple)")
        if not self.has_rabbit():
            logger.debug("..no rabbit")
            return
        if not self._may_adjust_rabbit:
            logger.debug("..autotune not permitted")
            return
        speed = self.ftg.aircraft.speed()

        logger.debug(f"adjustRabbit: {speed}")
        mode = RABBIT_MODE.MED
        if speed < 0.01:  # m/s
            logger.debug("probably stopped")
        elif speed < SPEED_SLOW:
            logger.debug("too slow")
            mode = RABBIT_MODE.FASTER
        elif speed > SPEED_FAST:
            logger.debug("too fast")
            mode = RABBIT_MODE.SLOWER
        if self.rabbitMode != mode:
            self.rabbitMode = mode
            logger.debug(f"..done. new mode is {self.rabbitMode} (requested {mode})")

    def adjustRabbit(self, position, closestLight):
        logger.debug("adjusting rabbit..")
        SPEEDS = {  # m/s
            "fast": [7.5, 13],
            "med": [5, 10],
            "slow": [2, 7],
            "caution": [1, 4],
            "turn": [0, 2],
        }

        if not self.has_rabbit():
            logger.debug("..no rabbit")
            return
        if not self._may_adjust_rabbit:
            logger.debug("..autotune not permitted")
            return

        # I. Collect information
        # 1. Distance to next vertex (= distance to next potential turn)
        route = self.ftg.lights.route
        light = self.ftg.lights.lights[closestLight]
        nextvertex = light.index + 1
        if nextvertex >= len(route.route):  # end of route
            nextvertex = len(route.route) - 1
        nextvtxid = route.route[nextvertex]
        nextvtx = route.graph.get_vertex(nextvtxid)

        dist = distance(Point(lat=position[0], lon=position[1]), nextvtx)
        # 2. Angle of next turn
        turn = route.turns[light.index]
        speed = self.ftg.aircraft.speed()
        # logger.debug(f"closest light: vertex index {light.index}, next vertex={nextvtx}, distance={round(dist, 1)}, turn={round(turn, 0)}, speed={round(speed, 1)}")
        logger.debug(f"adjustRabbit: turn={round(turn, 0)} at {round(dist, 1)}m, current speed={round(speed, 1)}")

        # II. From distance to turn, and angle of turn, assess situation
        # II.1  determine speed category
        msg = "on target"
        category = "med"

        # II.2 Adjust rabbit mode to requirements
        mode = RABBIT_MODE.MED
        srange = SPEEDS[category]
        if speed < 0.01:  # m/s
            msg = "probably stopped"
        elif speed < srange[0]:
            mode = RABBIT_MODE.FASTER
            msg = "accelerate"
        elif speed > srange[1]:
            mode = RABBIT_MODE.SLOWER
            msg = "too fast"

        if self.rabbitMode != mode:
            self.rabbitMode = mode
            logger.debug(f"adjustRabbit: speed={speed} distance={dist} turn={turn} => category {category}")
            logger.debug(f"adjustRabbit: speed={speed} range={dist} {msg} => rabbit {mode}")
        logger.debug(f"..done ({msg})")

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
            if self.has_rabbit():
                self.rabbitMode = RABBIT_MODE.SLOW
                # prevent rabbit auto-tuning, must remain slow until stop bar cleared
                self.disallow_rabbit_autotune()
            if not self.ftg.ui.isMainWindowVisible():
                logger.debug("showing UI.")
                self.ftg.ui.showMainWindow(False)

        closestLight, distance = self.ftg.lights.closest(pos)
        if not closestLight:
            logger.debug("no close light.")
            return self.nextIter

        if self.has_rabbit():
            self.adjustRabbit(position=pos, closestLight=closestLight)  # Here is the 4D!

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
        # if distance > 200m? send warning?
        if distance > 200:
            logger.debug(f"aircraft away from track? (d={distance})")

        self.distance = distance
        return self.nextIter
