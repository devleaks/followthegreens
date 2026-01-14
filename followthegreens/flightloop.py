# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
from datetime import datetime, timedelta

import xp

from .globals import (
    logger,
    RABBIT_MODE,
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    DRIFTING_DISTANCE,
    DRIFTING_LIMIT,
    AMBIANT_RWY_LIGHT_CMDROOT,
    AMBIANT_RWY_LIGHT,
)
from .geo import EARTH, Point, distance

MAX_UPDATE_FREQUENCY = 10  # seconds


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
        self.diftingLimit = DRIFTING_LIMIT * DISTANCE_BETWEEN_GREEN_LIGHTS  # After that, we send a warning, and we may cancel FTG.
        self.last_updated = datetime.now() - timedelta(seconds=MAX_UPDATE_FREQUENCY)
        self._rabbit_mode = RABBIT_MODE.MED
        self._may_adjust_rabbit = True
        self.manual_mode = False
        self.runway_level_original = 1

        self.closestLight_cnt = 0

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
            if ll is not None:
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

    @property
    def may_rabbit_autotune(self) -> bool:
        return self._may_adjust_rabbit and not self.manual_mode

    def allow_rabbit_autotune(self):
        self._may_adjust_rabbit = True
        logger.debug("rabbit adjustment authorized")

    def disallow_rabbit_autotune(self):
        self._may_adjust_rabbit = False
        logger.debug("rabbit adjustment forbidden")

    def manualRabbitMode(self, mode: RABBIT_MODE):
        self.manual_mode = True
        self.rabbitMode = mode

    def automaticRabbitMode(self):
        self.manual_mode = False

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
        if not self.may_rabbit_autotune:
            logger.info("rabbit adjustment forbidden")
            return
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

    def adjustRabbit(self, position, closestLight):
        # Important note:
        # In planeFLCB(), if we are closing to a STOP, the following is set:
        #   self.rabbitMode = RABBIT_MODE.SLOWEST
        # If we are not close to a stop, here we are to check for turns.
        #
        # logger.debug("adjusting rabbit..")
        if not self.has_rabbit():
            logger.debug("..no rabbit")
            return
        if not self.may_rabbit_autotune:
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

        # 2. distance to that next vertex and turn at that vertex
        dist = distance(Point(lat=position[0], lon=position[1]), nextvtx)
        turn = route.turns[light.index]

        # 3. current speed
        speed = self.ftg.aircraft.speed()
        # logger.debug(f"closest light: vertex index {light.index}, next vertex={nextvtx}, distance={round(dist, 1)}, turn={round(turn, 0)}, speed={round(speed, 1)}")
        # logger.debug(f"adjustRabbit: start turn={round(turn, 0)} at {round(dist, 1)}m, current speed={round(speed, 1)}")

        # From observation/experience:
        #
        # Taxi very fast=20 m/s
        # Taxi fast=15 m/s
        # Taxi cautious = 6m/s
        # Turn (90°): 3-4 m/s
        # Brake: 12m/s to 3: 100 m with A321, 200m with A330
        # WE decide:
        # Turn < 15°, speed "cautious"
        # Turn > 15°, speed "turn"
        #
        STOPPED_SPEED = 0.01  # m/s
        TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line
        SMALL_TURN_LIMIT = 15.0  # °, below this, it is a small turn, recommended to slow down a bit but not too much
        MOVEIT_DIST = 400.0  # m no reason to not go fast
        SPEED_DELTA = 5.0  # in m/s

        # 4. Find next "significant" turn of more than TURN_LIMIT
        idx = light.index + 1
        while abs(turn) < TURN_LIMIT and idx < len(route.route):
            turn = route.turns[idx]
            dist = dist + route.edges[idx].cost
            idx = idx + 1

        # @todo: What if no more turn but end of greens reached?
        if idx == len(route.route):  # end of route
            logger.warning("adjustRabbit: reached end of route")

        logger.debug(
            f"adjustRabbit: currently at index {light.index}, next turn (>{TURN_LIMIT}) at index {idx-1}: "
            + f"{round(turn, 0)} at {round(dist, 1)}m, current speed={round(speed, 1)}"
        )

        # II. From distance to turn, and angle of turn, assess situation

        # II.1  determine target speed (range)
        taxi_speed_ranges = self.ftg.aircraft.taxi_speed_ranges()
        braking_distance = self.ftg.aircraft.braking_distance()  # m should be a function of acf mass/type and current speed

        target = taxi_speed_ranges.MED  # target speed range
        comment = "continue"

        if dist < braking_distance:
            if abs(turn) < SMALL_TURN_LIMIT:
                comment = "small turn at braking distance, caution"
                target = taxi_speed_ranges.CAUTION
            else:
                comment = "turn at braking distance"
                target = taxi_speed_ranges.TURN
        elif dist > MOVEIT_DIST:
            comment = "no turn before large distance, move it"
            target = taxi_speed_ranges.FAST

        # II.2 adjust rabbit mode from current speed to target speed range
        advise = "on target"  # ..within range, mode = normal/medium
        mode = RABBIT_MODE.MED

        srange = target.value
        if speed < STOPPED_SPEED:  # m/s
            advise = f"probably stopped ({round(speed, 1)}m/s < {STOPPED_SPEED})"
        elif speed < srange[0]:
            delta = srange[0] - speed
            if delta > SPEED_DELTA:
                mode = RABBIT_MODE.FASTEST
                advise = "really too slow, accelerate"
            else:
                mode = RABBIT_MODE.FASTER
                advise = "too slow, accelerate"
        elif speed > srange[1]:
            delta = speed - srange[1]
            if delta > SPEED_DELTA:
                mode = RABBIT_MODE.SLOWEST
                advise = "really too fast, brake"
            else:
                mode = RABBIT_MODE.SLOWER
                advise = "too fast, brake"

        logger.debug(
            f"adjustRabbit: current speed={round(speed, 1)}, target={target}; rabbit current mode={self.rabbitMode}, recommanded={mode} ({comment}, {advise})"
        )

        if self.rabbitMode != mode:
            self.rabbitMode = mode
        # logger.debug(f"..done ({advise})")

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

        # @todo: WARNING_DISTANCE should be computed from acf type (weigth, size) and speed
        nextStop, warn = self.ftg.lights.toNextStop(pos)
        if nextStop and warn < self.ftg.aircraft.warning_distance():
            logger.debug("closing to stop.")
            if self.has_rabbit():
                self.rabbitMode = RABBIT_MODE.SLOWEST
                # prevent rabbit auto-tuning, must remain slow until stop bar cleared
                self.disallow_rabbit_autotune()
            if not self.ftg.ui.isMainWindowVisible():
                logger.debug("showing UI.")
                self.ftg.ui.showMainWindow(False)

        closestLight, distance = self.ftg.lights.closest(pos)
        if closestLight is None:
            if self.closestLight_cnt % 20:
                logger.debug("no close light.")
            self.closestLight_cnt = self.closestLight_cnt + 1
            return self.nextIter

        self.closestLight_cnt = 0

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
        # if distance > DRIFTING_DISTANCE send warning?
        if distance > DRIFTING_DISTANCE:
            logger.debug(f"aircraft drifting away from track? (d={round(distance, 1)} > {DRIFTING_DISTANCE})")

        self.distance = distance
        return self.nextIter
