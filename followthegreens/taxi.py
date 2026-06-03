# X-Plane Interaction Class
#
from datetime import datetime, timedelta, timezone

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import (
    logger,
    get_global,
    minsec,
    RABBIT_MODE,
    PLANE_MONITOR_DURATION,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    DRIFTING_DISTANCE,
    DRIFTING_LIMIT,
    AIRCRAFT_MIN_DIST,
)
from .geo import EARTH, Point, distance

# Hardcaded here, not preferences
AIRCRAFT_STOPPED_SPEED = 0.01  # m/s, under that speed, things are considered stopped, not moving.
NO_STOP_AHEAD = -1


class Taxi:

    def __init__(self, ftg):
        self.ftg = ftg

        # Aircraft monitoring flight loop
        self.refplane = "FtG:aircraft"
        self.flplane = None
        self.planeRunning = False

        self.nextIter = PLANE_MONITOR_DURATION  # seconds
        self.lastIter = PLANE_MONITOR_DURATION  # seconds, because it is dynamic

        # ASMCMS Level 4 compliance stuff:
        self.target_time = None  # target takeoff hold time, ready to takeoff for ACDM compliance. (Filled/provided externally.)
        self.actual_start = None  # actual taxi start time
        self.planned = None  # planned time of arrival at destination after taxi started
        self.old_starts = []

        # Monitoring globals
        self.remaining_time = 0
        self.remaining_dist = 0
        self.is_late = False
        self.remaining = "waiting for data..."
        self.dist_to_next_turn = 0
        self.dist_from_next_vtx_to_next_turn = 0
        self.last_dist_from_acf_to_next_vtx = -1
        self.total_dist = 0  # total taxi distance
        self.total_time = 0  # total taxi distance

        self.nextStop = NO_STOP_AHEAD

        # Progress tracking
        self.lastLit = 0
        self.distance_to_closest_light = EARTH
        self.diftingLimit = DRIFTING_LIMIT * DISTANCE_BETWEEN_GREEN_LIGHTS  # After that, we send a warning, and we may cancel FTG.

        self.last_acf_light_progress = 0
        self.last_acf_light_progress_cnt = 0
        self.acf_light_progress = 0  # most recent light where the acf is. Can only grow.
        self._taxi_ended = False

        # less verbose debug
        self.show_clearance_popup = get_global("SHOW_CLEARANCE_POPUP", self.ftg.prefs)
        self.closestLight_cnt = 0
        self.old_msg = ""
        self.old_msg2 = ""

    # LOCAL RABBIT HOOKS
    # (with lights availability control)
    #
    @property
    def may_rabbit_autotune(self) -> bool:
        if self.ftg.lights is not None:
            return self.ftg.lights.may_rabbit_autotune()
        return True

    @property
    def reason(self) -> str:
        if self.ftg.lights is not None:
            return self.ftg.lights.reason
        return "no lights"

    def allowRabbitAutotune(self, reason: str = ""):
        if self.ftg.lights is not None:
            return self.ftg.lights.allowRabbitAutotune(reason=reason)

    def disallowRabbitAutotune(self, reason: str = ""):
        if self.ftg.lights is not None:
            return self.ftg.lights.disallowRabbitAutotune(reason=reason)

    def manualRabbitMode(self, mode: RABBIT_MODE):
        if self.ftg.lights is not None:
            return self.ftg.lights.manualRabbitMode(mode=mode)

    def automaticRabbitMode(self):
        if self.ftg.lights is not None:
            return self.ftg.lights.automaticRabbitMode()

    @property
    def rabbitMode(self) -> RABBIT_MODE | None:
        if self.ftg.lights is not None:
            return self.ftg.lights.rabbitMode
        return None

    @rabbitMode.setter
    def rabbitMode(self, mode: RABBIT_MODE):
        if self.ftg.lights is not None:
            self.ftg.lights.rabbitMode = mode

    # 4D
    #
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

    # AIRCRAFT FLIGHT LOOP
    #
    def startFlightLoop(self):
        self.lastLit = 0
        self.acf_light_progress = 0
        self.last_acf_light_progress = 0
        self.last_acf_light_progress_cnt = 0

        if self.hasRabbit():
            self.ftg.lights.setNewLastLit(newLastLit=0)
            self.ftg.lights.startFlightLoop()

        if not self.planeRunning:
            self.flplane = xp.createFlightLoop(callback=self.planeFLCB, phase=xp.FlightLoop_Phase_AfterFlightModel, refCon=self.refplane)
            xp.scheduleFlightLoop(self.flplane, self.nextIter, 1)
            self.planeRunning = True
            logger.debug(f"aircraft tracking started (iter={self.nextIter})")
        else:
            logger.debug("aircraft tracked")

    def stopFlightLoop(self):
        if self.taxiStarted():
            self.taxiEnd()
            self.taxiReset()

        if self.hasRabbit():
            self.ftg.lights.stopFlightLoop()

        if self.planeRunning:
            xp.destroyFlightLoop(self.flplane)
            self.planeRunning = False
            logger.debug("aircraft tracking stopped")
        else:
            logger.debug("aircraft not tracked")

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

    def planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        try:
            if self.ftg is not None:
                return self._planeFLCB(elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon)
        except:
            logger.error("issue in the main flight loop, retrying in 5 seconds", exc_info=True)
        return 5.0  # seconds

    def hasFMCar(self) -> bool:
        return self.ftg is not None and self.ftg.fmcar is not None

    def hasRabbit(self) -> bool:
        if self.ftg.lights is not None:
            return self.ftg.lights.hasRabbit()
        return False

    def _planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # monitor progress of plane on the greens. Turns lights off as it does no longer needs them.
        # logger.debug('%2f, %2f, %d', elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter)
        if self.ftg.paused:
            msg = "paused"
            if msg != self.old_msg:
                logger.debug(msg)
                self.old_msg = msg
            if self.ftg.fmcar is not None:
                self.ftg.fmcar.pause()
            return 2

        if self.old_msg == "paused":
            self.old_msg = ""
            logger.debug("unpaused")
            if self.ftg.fmcar is not None:
                self.ftg.fmcar.unpause()

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
            if not self.ftg.ui.isVisible() and self.show_clearance_popup:
                # logger.debug("showing UI")
                self.ftg.ui.showWindow(canHide=False)
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
            self.ftg.lights.adjustRabbit(flightloop=self, closestLight=closestLight)  # Here is the 4D!

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
            if self.ftg.lights is not None:
                self.ftg.lights.setNewLastLit(newLastLit=closestLight)
            self.distance_to_closest_light = dist_to_closestLight
            return nextIter

        if self.lastLit == closestLight and (abs(self.distance_to_closest_light - dist_to_closestLight) < DISTANCE_BETWEEN_GREEN_LIGHTS):  # not moved enought, may even be stopped
            # logger.debug("aircraft did not move")
            return nextIter

        # @todo
        # Need to send warning when pilot moves away from the greens.
        # if distance > DRIFTING_DISTANCE send warning?
        if dist_to_closestLight > DRIFTING_DISTANCE:
            logger.debug(f"aircraft drifting away from track? (d={round(dist_to_closestLight, 1)} > {DRIFTING_DISTANCE})")

        # if distance > (2*DRIFTING_DISTANCE) and AUTO_REROUTE:
        #     logger.debug(f"aircraft drifting away from track? (d={round(distance, 1)} > {DRIFTING_DISTANCE}), starting new greens")
        #     self.ftg.newGreens(destination=self.ftg.destination)
        self.distance_to_closest_light = dist_to_closestLight

        return nextIter
