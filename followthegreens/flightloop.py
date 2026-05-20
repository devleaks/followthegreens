# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor aircraft position.
#
from datetime import datetime, timedelta, timezone

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import (
    MOVEMENT,
    logger,
    get_global,
    minsec,
    RABBIT_MODE,
    TAXI_SPEED,
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    DRIFTING_DISTANCE,
    DRIFTING_LIMIT,
    AMBIANT_RWY_LIGHT_CMDROOT,
    AMBIANT_RWY_LIGHT,
    AIRCRAFT_MIN_DIST,
)
from .geo import EARTH, Point, distance

# Hardcaded here, not preferences
MAX_UPDATE_FREQUENCY = 10  # seconds, rabbit cannot change again more that 10 seconds it changed
AIRCRAFT_STOPPED_SPEED = 0.01  # m/s, under that speed, things are considered stopped, not moving.
NO_STOP_AHEAD = -1


class FlightLoop:

    def __init__(self, ftg):
        self.ftg = ftg
        self.refrabbit = "FtG:rabbit"
        self.flrabbit = None
        self.rabbitRunning = False
        self.refplane = "FtG:aircraft"
        self.flplane = None
        self.planeRunning = False
        self.refexec = "FtG:rabbit"
        self.flexec = None
        self.execRunning = False
        self.nextIter = PLANE_MONITOR_DURATION  # seconds
        self.lastIter = PLANE_MONITOR_DURATION  # seconds, because it is dynamic
        self.nextStop = NO_STOP_AHEAD
        self.lastLit = 0
        self.distance_to_closest_light = EARTH
        self.diftingLimit = DRIFTING_LIMIT * DISTANCE_BETWEEN_GREEN_LIGHTS  # After that, we send a warning, and we may cancel FTG.
        self.last_updated = datetime.now() - timedelta(seconds=MAX_UPDATE_FREQUENCY)
        self._rabbit_mode = RABBIT_MODE.MED
        self._may_adjust_rabbit = True
        self.reason = ""
        self.manual_mode = False
        self.runway_level_original = 1
        self.show_clearance_popup = get_global("SHOW_CLEARANCE_POPUP", self.ftg.prefs)

        # ASMCMS Level 4 compliance stuff:
        self.target_time = None  # target takeoff hold time, ready to takeoff for ACDM compliance. (Filled/provided externally.)
        self.actual_start = None  # actual taxi start time
        self.planned = None  # planned time of arrival at destination after taxi started
        self.old_starts = []

        # Monitoring globals
        self.remaining_time = 0
        self.remaining_dist = 0
        self._hud_position = get_global("HUD_POSITION", self.ftg.prefs)
        self._hud_colors = get_global("HUD_COLORS", self.ftg.prefs)
        self.is_late = False
        self.remaining = "waiting for data..."
        self.dist_to_next_turn = 0
        self.dist_from_next_vtx_to_next_turn = 0
        self.last_dist_from_acf_to_next_vtx = -1
        self.total_dist = 0  # total taxi distance
        self.total_time = 0  # total taxi distance

        self.last_acf_light_progress = 0
        self.last_acf_light_progress_cnt = 0
        self.acf_light_progress = 0  # most recent light where the acf is. Can only grow.
        self._taxi_ended = False

        # less verbose debug
        self.closestLight_cnt = 0
        self.old_msg = ""
        self.old_msg2 = ""

        self.pause_dref = xp.findDataRef("sim/time/paused")
        self.startExecLoop()

    def startExecLoop(self):
        self.flexec = xp.createFlightLoop(callback=self.executeFLCB, phase=xp.FlightLoop_Phase_BeforeFlightModel, refCon=self.refexec)
        xp.scheduleFlightLoop(self.flexec, 1.0, 1)  # starts in a second, arbitrary
        self.execRunning = True
        logger.debug("execute loop started")

    def stopExecLoop(self):
        xp.destroyFlightLoop(self.flexec)
        self.execRunning = False
        logger.debug("execute loop stopped")

    def startFlightLoop(self):
        self.lastLit = 0
        self.acf_light_progress = 0
        self.last_acf_light_progress = 0
        self.last_acf_light_progress_cnt = 0

        if self.hasRabbit():
            if not self.rabbitRunning:
                self.flrabbit = xp.createFlightLoop(callback=self.rabbitFLCB, phase=xp.FlightLoop_Phase_BeforeFlightModel, refCon=self.refrabbit)
                xp.scheduleFlightLoop(self.flrabbit, 1.0, 1)  # starts in a second, arbitrary
                self.rabbitRunning = True
                logger.debug(f"rabbit started ({self._rabbit_mode})")
            else:
                logger.debug(f"rabbit running ({self._rabbit_mode})")
        else:
            logger.debug("no rabbit requested")

        if not self.planeRunning:
            self.flplane = xp.createFlightLoop(callback=self.planeFLCB, phase=xp.FlightLoop_Phase_AfterFlightModel, refCon=self.refplane)
            xp.scheduleFlightLoop(self.flplane, self.nextIter, 1)
            self.planeRunning = True
            logger.debug(f"aircraft tracking started (iter={self.nextIter})")
            # if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
            #     logger.debug(f"Checking menu {self.ftg.pi.menuIdx}")
            #     xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Checked)
            #     logger.debug(f"..checked")
            # else:
            #     logger.debug(f"menu not checked (index {self.ftg.pi.menuIdx})")
        else:
            logger.debug("aircraft tracked")

        # Dim runway lights according to preferences
        ll = get_global("RUNWAY_LIGHT_LEVEL_WHILE_FTG", preferences=self.ftg.prefs)
        ll = ll.lower()
        if ll.startswith("l"):
            ll = "lo"
        elif ll.startswith("m"):
            ll = "med"
        elif ll.startswith("h"):
            ll = "hi"
        elif ll.startswith("o"):
            ll = "off"
        if self.planeRunning and self.ftg.airport_light_level is not None:
            self.runway_level_original = xp.getDataf(self.ftg.airport_light_level)
            if ll is not None:
                cmdref = xp.findCommand(AMBIANT_RWY_LIGHT_CMDROOT + ll)
                if cmdref is not None:
                    xp.commandOnce(cmdref)
                    currlevel = xp.getDataf(self.ftg.airport_light_level)
                    logger.debug(f"runway lights preference set to {ll} (original={self.runway_level_original}, during FtG={currlevel})")

    def stopFlightLoop(self):
        self.stopExecLoop()

        self.taxiEnd()
        self.taxiReset()
        if self.rabbitRunning:
            xp.destroyFlightLoop(self.flrabbit)
            self.rabbitRunning = False
            logger.debug("rabbit stopped")
        else:
            logger.debug("rabbit not running")

        if self.planeRunning:
            xp.destroyFlightLoop(self.flplane)
            self.planeRunning = False
            logger.debug("aircraft tracking stopped")
            # if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
            #     logger.debug(f"Unchecking menu {self.ftg.pi.menuIdx}")
            #     xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Unchecked)
            #     logger.debug(f"..unchecked")
            # else:
            #     logger.debug(f"menu not checked (index {self.ftg.pi.menuIdx})")
        else:
            logger.debug("aircraft not tracked")

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
        if self.taxiStarted():
            self.taxiReset()

    def hasRabbit(self) -> bool:
        return self.ftg.lights.hasRabbit() if self.ftg.lights is not None else False

    def hasFMCar(self) -> bool:
        return self.ftg is not None and self.ftg.fmcar is not None

    @property
    def may_rabbit_autotune(self) -> bool:
        return self._may_adjust_rabbit and not self.manual_mode

    def allowRabbitAutotune(self, reason: str = ""):
        self._may_adjust_rabbit = True
        self.reason = reason
        logger.debug(f"rabbit adjustment authorized (reason {reason})")

    def disallowRabbitAutotune(self, reason: str = ""):
        self._may_adjust_rabbit = False
        self.reason = reason
        logger.debug(f"rabbit adjustment not permitted (reason {reason})")

    def manualRabbitMode(self, mode: RABBIT_MODE):
        self.manual_mode = True
        logger.debug("manual rabbit mode")
        self.rabbitMode = mode

    def automaticRabbitMode(self):
        self.manual_mode = False
        logger.debug("rabbit mode automagic")

    @property
    def rabbitMode(self) -> RABBIT_MODE:
        return self._rabbit_mode

    @rabbitMode.setter
    def rabbitMode(self, mode: RABBIT_MODE):
        # Need to add a function to NOT change rabbit too often, once every 10 secs. is a minimum
        if not self.hasRabbit():
            return
        if self.rabbitMode == mode:
            return
        if not self.may_rabbit_autotune:
            logger.debug(f"rabbit adjustment not permitted ({self.reason})")
            return
        now = datetime.now()
        delay = (now - self.last_updated).total_seconds()
        if delay < MAX_UPDATE_FREQUENCY:
            logger.debug(f"must wait {round(MAX_UPDATE_FREQUENCY - delay, 2)} seconds before changing rabbit")
            return
        self.ftg.lights.rabbitMode(mode)
        self._rabbit_mode = mode
        self.last_updated = now
        logger.debug(f"rabbit mode set to {mode}")

    @property
    def rabbitText(self):
        if self.rabbitMode in RABBIT_MODE.FASTER:
            return "ACCELERATE"
        elif self.rabbitMode in RABBIT_MODE.FASTEST:
            return "ACCELERATE"
        elif self.rabbitMode in RABBIT_MODE.SLOWER:
            return "BRAKE"
        elif self.rabbitMode in RABBIT_MODE.SLOWEST:
            return "SLOW"
        else:
            return "ACTIVE"

    def late(self, t0: float = 0.0) -> bool:
        # when taxi is started, we determine an ETA at destination
        # compare now + time remaining vs ETA
        if self.actual_start is None or self.planned is None:
            logger.debug("no start time")
            return False
        eta = datetime.now(tz=timezone.utc) + timedelta(seconds=t0)
        tdiff = self.planned - eta
        # logger.debug(f"remaining: {round(t0, 1)}, delta time: {round(tdiff.seconds, 1)} secs {'in advance' if tdiff.seconds > 0 else 'late'}")
        return tdiff.seconds < 0  # is late

    def hudPosition(self):
        return self._hud_position

    def hudColors(self):
        return self._hud_colors

    def taxiReset(self):
        self.actual_start = None
        self.planned = None
        self.total_dist = 0
        self.total_time = 0
        self._taxi_ended = False

    def taxiStarted(self) -> bool:
        return self.actual_start is not None

    def taxiEnded(self) -> bool:
        return self._taxi_ended

    def taxiStart(self):
        # isolated a few markers taken when we detect taxi actually starts...
        self.actual_start = datetime.now(tz=timezone.utc).replace(microsecond=0)
        d, s = self.ftg.route.baseline()
        self.planned = self.actual_start + timedelta(seconds=round(s))
        # reset taxi distance and duration when start detected
        # (might expect small difference)
        self.total_dist = self.ftg.aircraft.moved()
        self.total_time = self.lastIter
        self._taxi_ended = False
        logger.info(f"taxi started at {self.actual_start.strftime('%H:%M')}Z, ride is {round(d, 1)}m in {minsec(s)}, planned takeoff hold at {self.planned.strftime('%H:%M')}Z")

    def taxiEnd(self):
        # provides some stats
        if not self.taxiStarted():
            logger.debug("taxi not started")
            return
        if self.taxiEnded():
            # logger.debug("taxi already ended")
            return
        self._taxi_ended = True
        now = datetime.now(tz=timezone.utc).replace(microsecond=0)
        logger.debug(f"taxi ended at {now.strftime("%H:%M")}Z ride was {round(self.total_dist, 1)}m in t={round(self.total_time, 1)}s ({minsec(self.total_time)})")
        if self.planned is not None:
            diff = (self.planned - now).seconds
            logger.info(f"taxi ended at {now.strftime("%H:%M")}Z ({minsec(diff)})")
            logger.debug(f"planned={self.planned.strftime("%H:%M")}Z, actual={now.strftime("%H:%M")}Z, {minsec(diff)} {'in advance' if diff > 0 else 'late'}")
            # logger.debug(f"control total={round(self.total_time, 1)} vs diff={round(diff, 1)}")

    def newRoute(self):
        self.old_starts.append((self.actual_start, self.target_time, self.planned))
        self.actual_start = None

    def adjustedIter(self, acf_speed: float) -> float:
        # If aircraft move fast, we check/update FtG more often
        # nextIter never changes, lastIter does
        FASTEST_PLANE_MONITOR_DURATION = 0.8  # fastest "frequency" in secs.
        try:
            if acf_speed is None or acf_speed < AIRCRAFT_STOPPED_SPEED:
                # logger.debug(f"stopped, iter {self.nextIter}s")
                return self.nextIter

            if self.rabbitMode == RABBIT_MODE.SLOWEST:  # probably closing stop or turn, must monitor/adjust speed frequently
                if self.lastIter != FASTEST_PLANE_MONITOR_DURATION:
                    logger.debug(f"close to stop, iter fast {self.nextIter}s")
                self.lastIter = FASTEST_PLANE_MONITOR_DURATION
                return self.lastIter

            SPEEDS = [  # [speed=m/s, iter=s], to keep about 10 meter acf movement, or less if slow at beginning
                [12.0, FASTEST_PLANE_MONITOR_DURATION],
                [10.0, 1.0],
                [7.0, 1.2],
                [3.0, 2.0],
                [2.2, 3.0],
                [0.0, PLANE_MONITOR_DURATION],
            ]
            i = 0
            while i < len(SPEEDS):
                if acf_speed > SPEEDS[i][0]:
                    j = SPEEDS[i][1]
                    logger.debug(f"acf speed {round(acf_speed, 1)}m/s, iter set to {j}s")
                    if j != self.lastIter:
                        logger.debug(f"acf speed {round(acf_speed, 1)}m/s, iter set to {j}s")
                        self.lastIter = j
                    return self.lastIter
                i = i + 1
        except:
            logger.error("adjustedIter", exc_info=True)
        logger.debug(f"acf speed {round(acf_speed, 1)}m/s, regular iter {self.nextIter}s")
        return self.nextIter

    def adjustRabbit(self, position, closestLight, acf_speed):
        # Important note:
        # In planeFLCB(), if we are closing to a STOP, the following is set:
        #   self.rabbitMode = RABBIT_MODE.SLOWEST
        # If we are not close to a stop, here we are to check for turns.
        #
        # logger.debug("adjusting rabbit")
        # if not self.hasRabbit():
        #     logger.debug("..no rabbit")
        #     return

        # I. Collect information
        # 1. Distance to next vertex (= distance to next potential turn)
        route = self.ftg.lights.route
        light = self.ftg.lights.lights[closestLight]
        next_vertex = light.edgeIndex + 1
        if next_vertex >= len(route.route):  # end of route
            next_vertex = len(route.route) - 1
            logger.info("reached end of route")
        nextvtxid = route.route[next_vertex]
        nextvtx = route.graph.get_vertex(nextvtxid)

        # 2. distance to that next vertex and turn at that vertex
        dist_from_acf_to_next_vtx = distance(Point(lat=position[0], lon=position[1]), nextvtx)

        if round(self.last_dist_from_acf_to_next_vtx, 1) == round(dist_from_acf_to_next_vtx, 1):  # not moved
            msg = "stopped"
            if self.old_msg != msg:
                logger.debug(msg)
                self.old_msg = msg
            return

        self.last_dist_from_acf_to_next_vtx = dist_from_acf_to_next_vtx
        turn = route.turns[light.edgeIndex]

        # 3. current speed
        acf_move = acf_speed * self.lastIter

        # logger.debug(f"closest light: vertex index {light.edgeIndex}, next vertex={nextvtx}, distance={round(dist, 1)}, turn={round(turn, 0)}, speed={round(speed, 1)}")
        # logger.debug(f"start turn={round(turn, 0)} at {round(dist, 1)}m, current speed={round(speed, 1)}")

        # From observation/experience:
        # Taxi very fast> 15 m/s
        # Taxi fast=12 m/s
        # Taxi cautious = 6m/s
        # Turn (90°): 3-4 m/s
        # Brake: 12m/s to 3: 100 m with A321, 200m with A330
        # We decide:
        # Turn < 15°, speed "cautious"
        # Turn > 15°, speed "turn"
        #
        # 4. Find next "significant" turn of more than TURN_LIMIT
        # following is precomputed once and for all in mkDistToBrake() (.dtb[<route-vertex-index>])
        # dist2 = dist_from_acf_to_next_vtx
        # dist_before2 = dist2
        TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line

        idx = next_vertex
        while abs(turn) < TURN_LIMIT and idx < len(route.turns):
            turn = route.turns[idx]
            # dist_before2 = dist2
            # dist2 = dist2 + route.edges[idx].cost
            idx = idx + 1
        if idx >= len(route.route):  # end of route
            idx = len(route.route) - 1
            logger.info("reached end of route")

        # logger.debug(f"current vertex={light.edgeIndex}, distance to next vertex {idx}: {round(dist_from_acf_to_next_vtx, 1)}m")
        # logger.debug(f"at vertext {idx}: turn={round(route.turns[idx], 1)} DEG")
        dist_from_next_vtx_to_next_turn = 0 if abs(route.turns[next_vertex]) > TURN_LIMIT else route.dtb[next_vertex]
        # next_turn_vertex_index = next_vertex if abs(route.turns[next_vertex]) > TURN_LIMIT else route.dtb_at[next_vertex]
        # could also be route.dtb_at[light.edgeIndex]
        # logger.debug(f"at vertext {idx}: distance to add to next turn={round(dist_from_next_vtx_to_next_turn, 1)}m")

        dist_before = dist_from_acf_to_next_vtx + dist_from_next_vtx_to_next_turn
        self.dist_to_next_turn = dist_before  # for hud, temporarily
        self.dist_from_next_vtx_to_next_turn = dist_before  # for hud, temporarily
        taxi_speed = max(acf_speed, self.ftg.aircraft.avgTaxiSpeed())  # m/s
        time_to_next_vertex = dist_from_acf_to_next_vtx / taxi_speed

        # logger.debug(f"acf speed={round(acf_speed, 1)}, moved {round(acf_move, 1)}m during last iteration ({self.lastIter} secs)")
        # logger.debug(f"at index {light.edgeIndex}, next turn at index {idx-1}, {round(turn)}D at {round(dist_before, 1)}m")
        # logger.debug(f"dist to next vertex {next_vertex}: {round(dist_from_acf_to_next_vtx, 1)}m, dist from next_vertex to next turn: {round(dist_from_next_vtx_to_next_turn, 1)}m")

        # dist to next vertex + remaining at next vertex = total left
        self.remaining_dist = dist_from_acf_to_next_vtx + route.dleft[next_vertex]
        # logger.debug(f"remaining dist to {next_vertex}: nxt {round(dist_from_acf_to_next_vtx, 1)}m + end {round(route.dleft[next_vertex], 1)}m = {round(self.remaining_dist, 1)}m")

        self.remaining_time = time_to_next_vertex + route.tleft[next_vertex] + 30
        # logger.debug(
        #     f"remaining time to {next_vertex}: nxt {round(time_to_next_vertex, 1)}sec + end {round(route.tleft[next_vertex], 1)}sec + mgn 30sec = {round(self.remaining_time, 1)}sec"
        # )

        # logger.debug(f"next turn index control next_turn_vertex_index={next_turn_vertex_index}, dtb_at[light.edgeIndex]={route.dtb_at[light.edgeIndex]}, idx={idx-1} (computed)")

        # logical controls
        # 1. dist to next turn + remaining at turn = total left
        # logger.debug(f"remaining dist: nxt turn at index {idx-1} {round(dist_before, 1)}m + end {round(route.dleft[idx-1], 1)}m = {round(dist_before + route.dleft[idx-1], 1)}m")

        # logger.debug(f"total d={round(self.total_dist, 1)}m, t={round(self.total_time, 1)}s ({minsec(self.total_time)})")

        # precompute for hud
        self.is_late = self.late(t0=self.remaining_time)  # will display original estimated vs new estimate
        self.remaining = f"{round(self.remaining_dist):4d}m, {minsec(self.remaining_time)}"
        # logger.debug(f"remaining: {round(self.remaining_dist, 1)}m, {round(self.remaining_time/60)}min, {'(late)' if self.is_late else '(on time)'}")
        # logger.debug(f"{self.remaining}")

        if not self.may_rabbit_autotune:
            logger.debug(f"..autotune not permitted ({self.reason})")
            return

        # II. From distance to turn, and angle of turn, assess situation
        # II.1  determine target speed (range)
        SMALL_TURN_LIMIT = 15.0  # °, below this, it is a small turn, recommended to slow down a bit but not too much
        MOVEIT_DIST = 400.0  # m no reason to not go fast
        SPEED_DELTA = 4.0  # in m/s, should may be a % of average range speed

        taxi_speed_ranges = self.ftg.aircraft.taxiSpeedRanges()
        braking_distance = self.ftg.aircraft.brakingDistance()  # m should be a function of acf mass/type and current speed

        target = taxi_speed_ranges[TAXI_SPEED.MED]  # target speed range
        comment = "continue"

        if dist_before < braking_distance:
            if abs(turn) < SMALL_TURN_LIMIT:
                comment = "small turn at braking distance, caution"
                target = taxi_speed_ranges[TAXI_SPEED.CAUTION]
            else:
                comment = "turn at braking distance"
                target = taxi_speed_ranges[TAXI_SPEED.TURN]
        elif dist_before > MOVEIT_DIST:
            comment = "no turn before large distance, move it"
            target = taxi_speed_ranges[TAXI_SPEED.FAST]

        # II.2 adjust rabbit mode from current speed to target speed range
        advise = "on target"  # ..within range, mode = normal/medium
        mode = RABBIT_MODE.MED

        speed_range = target
        if acf_speed < AIRCRAFT_STOPPED_SPEED:  # m/s
            advise = f"probably stopped ({round(acf_speed, 1)}m/s < {AIRCRAFT_STOPPED_SPEED})"
        elif acf_speed < speed_range[0]:
            delta = speed_range[0] - acf_speed
            if delta > SPEED_DELTA:
                mode = RABBIT_MODE.FASTEST
                advise = "really too slow, accelerate"
            else:
                mode = RABBIT_MODE.FASTER
                advise = "too slow, accelerate"
        elif acf_speed > speed_range[1]:
            delta = acf_speed - speed_range[1]
            if delta > SPEED_DELTA:
                mode = RABBIT_MODE.SLOWEST
                advise = "really too fast, brake"
            else:
                mode = RABBIT_MODE.SLOWER
                advise = "too fast, brake"

        msg = f"acf speed={round(acf_speed, 1)}, target={target}; rabbit mode={self.rabbitMode}, recommanded={mode} ({comment}, {advise})"
        if msg != self.old_msg2:
            logger.debug(msg)
            self.old_msg2 = msg

        try:
            if self.rabbitMode != mode:
                logger.info(msg)
                self.rabbitMode = mode
        except:
            logger.error("set rabbitMode", exc_info=True)

    def hasToStop(self):
        return self.nextStop != NO_STOP_AHEAD

    def closingToStop(self, aircraft) -> bool:
        pos = aircraft.position_point()
        nextStop, warn = self.ftg.lights.toNextStop(pos)
        return warn < aircraft.warningDistance()

    def lightsProgressed(self) -> bool:
        # note: first update might be due to aircraft being "on" the light string.
        #       second update confirms aircraft has moved on light string.
        r = self.last_acf_light_progress_cnt > 1
        if r:
            logger.debug(f"lights progressed: {self.last_acf_light_progress} -> {self.acf_light_progress} ({self.last_acf_light_progress_cnt})")
        return r

    def rabbitFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # show rabbit in front of plane.
        # plane is supposed to Follow the greens and it close to green light index self.lastLit.
        # We cannot use XP's counter because it does not increment by 1 just for us.
        if self.ftg is not None and self.ftg.lights is not None:
            try:
                return self.ftg.lights.rabbit(self.lastLit)
            except:
                logger.error("issue in rabbit flight loop, retrying in 5 seconds", exc_info=True)
        return 5.0

    def executeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        timed = 1.0
        try:
            if self.ftg is not None:
                self.ftg._execute()
        except:
            logger.error(f"issue in execute flight loop, retrying in {timed} seconds", exc_info=True)
        return timed  # seconds

    def planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        try:
            if self.ftg is not None:
                return self._planeFLCB(elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon)
        except:
            logger.error("issue in the main flight loop, retrying in 5 seconds", exc_info=True)
        return 5.0  # seconds

    def _planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # monitor progress of plane on the green. Turns lights off as it does no longer needs them.
        # logger.debug('%2f, %2f, %d', elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter)
        if xp.getDatai(self.pause_dref) == 1:
            msg = "paused"
            if msg != self.old_msg:
                logger.debug(msg)
                self.old_msg = msg
            return 2

        self.ftg.hideWindow(elapsedSinceLastCall)

        aircraft = self.ftg.aircraft

        pos_pt = aircraft.position_point()
        if pos_pt is None or (pos_pt.lat == 0 and pos_pt.lon == 0):
            logger.debug("no position")
            return self.nextIter
        pos = (pos_pt.lat, pos_pt.lon)

        acf_speed = aircraft.speed()
        if acf_speed is None:
            logger.debug("no speed")
            return self.nextIter

        fmcar = self.ftg.fmcar
        closestLight, dist_to_closestLight = aircraft.closestLight(lights=self.ftg.lights)
        nextStop = NO_STOP_AHEAD
        warn = EARTH
        if closestLight is not None:
            logger.debug(f"acf closest light {closestLight}")
            nextStop, warn, cleared = aircraft.nextStop(ftg=self.ftg, closestLight=closestLight)

        if not self.taxiStarted():
            # FM Car hook #1
            if self.hasFMCar() and not fmcar.inited:
                fmcar.spawn(nextStop=nextStop)
            #
            if aircraft.moved() > AIRCRAFT_MIN_DIST or aircraft.moving() or self.lightsProgressed():
                self.taxiStart()
            else:
                msg = f"not started taxiing yet, {round(aircraft.moved(), 1)} < {AIRCRAFT_MIN_DIST}, moving={aircraft.moving()}"
                if msg != self.old_msg:
                    logger.debug(msg)
                    self.old_msg = msg
                return self.adjustedIter(acf_speed=acf_speed)

        # track progress for hud and 4D
        acf_move = acf_speed * self.lastIter  # * elapsedSinceLastCall
        self.total_time = self.total_time + self.lastIter
        self.total_dist = self.total_dist + acf_move

        # @todo: WARNING_DISTANCE should be computed from acf type (weigth, size) and speed
        if nextStop and warn < aircraft.warningDistance():
            logger.debug(f"closing to stop (at light index={nextStop}, d={round(warn, 1)}m)")
            self.nextStop = nextStop
            if self.hasFMCar():
                fmcar.mustStopSoon()
            if self.hasRabbit():
                if self.rabbitMode != RABBIT_MODE.SLOWEST:
                    self.allowRabbitAutotune("close to stop, allow autotune to force update to SLOWEST..")
                    self.rabbitMode = RABBIT_MODE.SLOWEST
                    # prevent rabbit auto-tuning, must remain slow until stop bar cleared
                    self.disallowRabbitAutotune("..close to stop, autotune forced to SLOWEST")
            if not self.ftg.ui.isMainWindowVisible() and self.show_clearance_popup:
                # logger.debug("showing UI")
                self.ftg.ui.showMainWindow(False)
            else:
                logger.debug(f"show_clearance_popup = {self.show_clearance_popup}")
        else:
            self.nextStop = NO_STOP_AHEAD
            if self.hasFMCar() and fmcar.mustStop():
                fmcar.canContinue()
            if not self.may_rabbit_autotune:
                self.allowRabbitAutotune("no longer close to stop")

        if closestLight is None:
            if self.closestLight_cnt % 20:
                logger.debug("no close light")
            self.closestLight_cnt = self.closestLight_cnt + 1
            return self.adjustedIter(acf_speed=acf_speed)

        self.closestLight_cnt = 0
        nextIter = self.adjustedIter(acf_speed=acf_speed)

        if closestLight < self.acf_light_progress:
            logger.debug(f"backup detected, ignoring closestLight={closestLight}, using {self.acf_light_progress}, no progress")
            closestLight = max(closestLight, self.acf_light_progress)

        if self.ftg.lights.isLastLight(index=closestLight):  # at end
            self.taxiEnd()

        if self.hasRabbit():
            self.adjustRabbit(position=pos, closestLight=closestLight, acf_speed=acf_speed)  # Here is the 4D!

        if self.hasFMCar() and self.taxiEnded() and fmcar.isDeleted():
            self.ftg.fmcar = None  # ready to create a new one

        if self.last_acf_light_progress != self.acf_light_progress:
            self.last_acf_light_progress_cnt += 1

        self.last_acf_light_progress = self.acf_light_progress
        self.acf_light_progress = closestLight

        # logger.debug("closest %d %f", closestLight, distance)
        if closestLight > self.lastLit and dist_to_closestLight < self.diftingLimit:  # Progress OK
            # logger.debug("moving %d %d", closestLight, self.lastLit)
            self.lastLit = closestLight
            self.distance_to_closest_light = dist_to_closestLight
            return nextIter

        if self.lastLit == closestLight and (abs(self.distance_to_closest_light - dist_to_closestLight) < DISTANCE_BETWEEN_GREEN_LIGHTS):  # not moved enought, may even be stopped
            # logger.debug("aircraft did not move")
            return nextIter

        # @todo
        # Need to send warning when pilot moves away from the green.
        # if distance > DRIFTING_DISTANCE send warning?
        if dist_to_closestLight > DRIFTING_DISTANCE:
            logger.debug(f"aircraft drifting away from track? (d={round(dist_to_closestLight, 1)} > {DRIFTING_DISTANCE})")

        # if distance > (2*DRIFTING_DISTANCE) and AUTO_REROUTE:
        #     logger.debug(f"aircraft drifting away from track? (d={round(distance, 1)} > {DRIFTING_DISTANCE}), starting new greens")
        #     self.ftg.newGreen(destination=self.ftg.destination)
        self.distance_to_closest_light = dist_to_closestLight

        return nextIter
