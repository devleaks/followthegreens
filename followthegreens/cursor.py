import os
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import RABBIT_MODE, logger, MOVEMENT, INDICATOR, AIRCRAFT_MIN_SPEED
from .geo import Point, Line, bearing, destination, distance
from .lightstring import XPObject
from .route import SMOOTH_ROUTE


class CURSOR_STATUS(StrEnum):
    NEW = "NEW"  # cursor just created
    READY = "READY"  # cursor initialized, got starting position, cursor spawned, flight loop not running
    ACTIVE = "ACTIVE"  # flight loop running
    FINISHING = "FINISHING"  # initiated finish
    FINISHED = "FINISHED"  # finish finished, can be deleted
    DESTROYED = "DESTROYED"  # cursor destroyed
    DELETED = "DELETED"  # cursor deleted
    HOLD = "HOLD"  # cursor temporarily held


def ts() -> float:
    return datetime.now().timestamp()


def st(t: float) -> float:
    # format timestamp
    if t <= 0:
        return 0.0
    d = datetime.fromtimestamp(t)
    d = d.replace(hour=d.hour - 2, minute=0, second=0, microsecond=0)
    t0 = d.timestamp()
    return datetime.fromtimestamp(t).strftime("%M:%S.%f")  # round(t - t0, 3)


def sf(t: float, unit: str = "") -> str:
    # format distance or speed
    return f"{round(t, 1)}{unit}"


def slow_debug(c, s):
    if c % 200 == 0:
        logger.debug(s)


NOT_ON_ROUTE = -1


@dataclass
class CursorType:
    """Cursor detailed information with default values"""

    filename: str = "xcsl/FMC.obj"
    above_ground: float = 0.0  # vertical offset for above object

    indicator: bool = False  # use additionl indicator
    indicator_shift: tuple = (0.0, 0.0)  # offset for indicator (height, forward), in meters

    slow_speed: float = 3.0  # turns, careful move, all speed m/s
    normal_speed: float = 7.0  # 25km/h
    leave_speed: float = 10.0  # expedite speed to leave/clear an area
    fast_speed: float = 14.0  # running fast to a destination far away

    max_speed: float = 18.0  # 18=60km/h, 25=90km/h, kind of a V-NES (never exceed speed)

    turn_radius: float = 22.0  # m

    acceleration: float = 1.0  # m/s^2, same deceleration
    deceleration: float = -1.0  # m/s^2, same deceleration

    indicator_warning_distance: float = 70.0  # m

    def __str__(self):
        """Returns a string containing only the non-default field values."""
        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values
        s = ", ".join(f"{field.name}={getattr(self, field.name)!r}" for field in fields(self) if getattr(self, field.name) != field.default)
        return f"{type(self).__name__}({s})"


class CursorObject:

    DEFAULT_SPEED = 7  # m/s, 25km/h
    DEFAULT_ACCELERATION = 1.0  # m/s^2, same deceleration

    def __init__(self, filename):
        self.filename = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), "cars", filename))
        self.name = os.path.basename(self.filename).replace(".obj", "")
        self.obj = None
        if os.path.exists(self.filename):
            self.obj = xp.loadObject(self.filename)
            logger.debug(f"{self.name} object {self.filename} loaded")
        else:
            logger.debug(f"{self.name} file {self.filename} not found")

    def __del__(self):
        if self.obj is not None:
            xp.unloadObject(self.obj)
            logger.debug(f"unloaded object {self.filename}")
        logger.debug("deleted")

    @property
    def has_obj(self) -> bool:
        return self.obj is not None


class SimpleQueue:

    def __init__(self) -> None:
        self._items = []

    def empty(self) -> bool:
        return len(self._items) == 0

    def put(self, item):
        self._items.append(item)

    def get(self):
        if len(self._items) > 0:
            i = self._items[0]
            del self._items[0]
            return i
        return None

    def clear(self):
        self._items = []

    def last(self):
        return self._items[-1] if not self.empty() else None

    def qsize(self) -> int:
        return len(self._items)


@dataclass
class OnRoute:
    """4 position with other information"""

    index: int = NOT_ON_ROUTE
    distance: float = 0.0  # distance "forward" from above index

    def __str__(self):
        """Returns a string containing only the non-default field values."""
        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values

        def f(i):
            return sf(i, "m") if type(i) is float else i

        s = ", ".join(f"{field.name}={f(getattr(self, field.name))!r}" for field in fields(self))
        return f"{type(self).__name__}({s})"


@dataclass
class Situation:
    """4 position with other information"""

    sr_route: tuple = tuple()  # smoothRoute, either a straightRoute which is NOT ON sharp route or smoothRoute which is on sharp route
    sr_position = OnRoute()  # position on sr_route equivalent to position

    position: Point | None = None  # position at sr_position(index, distance)
    speed: float = 0.0

    @property
    def sr_end(self) -> OnRoute:
        return OnRoute(index=len(self.sr_route) - 1, distance=0)

    @property
    def current_vertex(self) -> Point:
        return self.sr_route[self.sr_position.index]

    @property
    def heading(self) -> float:
        return self.sr_route[self.sr_position.index].getProp(SMOOTH_ROUTE.BEARING)

    def __str__(self):
        """Returns a string containing only the non-default field values."""
        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values

        def f(i):
            if type(i) in [list, tuple] and len(i) > 0 and isinstance(i[0], Point):
                return f"[ route[{len(i)}] ]"
            if isinstance(i, Point):
                return [round(p, 5) for p in i.coords()]
            if type(i) is float:
                if i > 100000000.0:
                    return st(i)
                else:
                    return round(i, 1)
            return i

        s = ", ".join(f"{field.name}={f(getattr(self, field.name))!r}" for field in fields(self) if getattr(self, field.name) != field.default)
        return f"{type(self).__name__}({s})"


class Cursor:
    # Linear interpolator

    def __init__(self, detail, route) -> None:
        self.detail = detail
        self.cursor_object = CursorObject(detail.filename)
        # self.indicator_object = CursorObject("indicator/indicator.obj")
        self.cursor = XPObject(None, 0, 0, 0)

        self._indicator = INDICATOR.FOLLOW_ME
        self.indicator_object = None
        self.indicator_cursor = None
        if detail.indicator:
            indicator = CursorType(filename="indicator/indicator.obj", indicator_shift=detail.indicator_shift)
            self.indicator_object = CursorObject(indicator.filename)
            self.indicator_cursor = XPObject(None, 0, 0, 0)

        self._status = CURSOR_STATUS.NEW
        self.active = False  # accepts futures if active

        self.route = route  # route that the cursor must follow
        self.en_route = False

        self._future = SimpleQueue()

        # Current, initialized with init() and incrementally followed
        self.current = Situation()
        self.target = Situation()

        # working var for interpolation
        self.refcursor = "FtG:cursor"
        self.flightLoop = None
        self.nextIter = -1

        self.cnt = -1
        self.msg = ""
        self.last_dist_to_next_vertex = 0.0

        # monitoring
        self._aim_speed = 0.0
        self.current_distance = 0.0  # distance to acf
        self.distance_range = [0.0, 0.0]
        self.current_bearing = 0.0  # acf -> fmcar
        self.uturned = False  # now fmcar -> acf!

        logger.info(str(self.detail))
        logger.debug(f"route end: {self.route.move}, {self.route.departure_runway}, {self.route.arrival_runway}")

    def __del__(self):
        self.destroy()
        self.status = CURSOR_STATUS.DELETED

    @property
    def status(self) -> CURSOR_STATUS:
        return self._status

    @status.setter
    def status(self, status: CURSOR_STATUS):
        if status != self._status:
            self._status = status
            logger.info(f"{type(self).__name__} is now {status}")

    @property
    def indicator(self) -> int:
        return self._indicator.value

    @property
    def aim_speed(self) -> float:
        return self._aim_speed

    @aim_speed.setter
    def aim_speed(self, speed: float) -> float:
        self.speed_reached = False
        self._aim_speed = speed
        logger.debug(f"new aim speed={sf(self.aim_speed, 'm/s')}")

    @indicator.setter
    def indicator(self, indicator: INDICATOR):
        if indicator != self._indicator:
            self._indicator = indicator
            logger.info(f"Indicator is now {indicator.name}")

    @property
    def usable(self) -> bool:
        return self.cursor is not None and self.cursor_object.has_obj

    @property
    def inited(self) -> bool:
        return self.current.position is not None and self.route is not None

    @property
    def on_route(self) -> bool:
        return self.current.route_index >= 0

    def last_speed(self) -> float:
        # last know requested speed
        r = self._future.last()
        return r.speed if r is not None else self.target.speed  # (position, hdg, speed, t, edge, text)

    # Creation, destruction
    #
    def init(self, route: tuple, position: Point, heading: float, speed: float = 0.0):
        # spawn cursor
        if self.inited:  # only init once
            return
        self.current.sr_route = route
        self.current.position = Point(lat=position.lat, lon=position.lon)  # take a local copy of the supplied position
        self.current.speed = speed
        self.current.sr_position = OnRoute(index=0, distance=0.0)
        self.target.sr_position = OnRoute(index=len(self.current.sr_route) - 1, distance=0)

        self.cursor.position = self.current.position  # initial position where will appear
        self.cursor.heading = self.current.heading
        self.cursor.place(lightType=self.cursor_object)
        self.cursor.on()
        if self.indicator_cursor is not None:
            self.indicator_cursor.position = self.current.position  # initial position where will appear
            self.indicator_cursor.heading = self.current.heading
            self.indicator_cursor.place(lightType=self.indicator_object)
            self.indicator_cursor.on()

        self.active = True
        self.status = CURSOR_STATUS.READY
        logger.debug(f"initialized pos={self.current.position.coords()}, speed={sf(self.current.speed, 'm/s')}, sr_position={self.current.sr_position}")
        self.startFlightLoop()

    def destroy(self):
        self.stopFlightLoop()
        if self.indicator_cursor is not None:
            self.indicator_cursor.destroy()
            self.indicator_cursor = None
        if self.indicator_object is not None:
            del self.indicator_object
            self.indicator_object = None
        if self.cursor is not None:
            self.cursor.destroy()
            self.cursor = None
        if self.cursor_object is not None:
            del self.cursor_object  # unloads object
            self.cursor_object = None
        self.status = CURSOR_STATUS.DESTROYED

    def isDeleted(self) -> bool:
        if self.status == CURSOR_STATUS.FINISHED:
            self.destroy()
            return True
        return False

    # Movement execution
    #
    def startFlightLoop(self):
        if self.flightLoop is None and self.cursor is not None and self.usable:
            self.flightLoop = xp.createFlightLoop(callback=self.cursorFLCB, phase=xp.FlightLoop_Phase_AfterFlightModel, refCon=self.refcursor)
            xp.scheduleFlightLoop(self.flightLoop, self.nextIter, 1)
            self.status = CURSOR_STATUS.ACTIVE
            logger.debug("cursor tracking started")

    def stopFlightLoop(self):
        if self.flightLoop is not None:
            xp.destroyFlightLoop(self.flightLoop)
            self.flightLoop = None
            self.status = CURSOR_STATUS.READY
        logger.debug("cursor tracking stopped")

    def cursorFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # collects new position/eading and places car at that positon/heading
        try:
            r = self._move(t=elapsedSinceLastCall)
            return r if type(r) in [int, float] else -1
        except:
            logger.error("error", exc_info=True)
        return 5.0

    def canContinue(self, ftg):
        if self.indicator != INDICATOR.STOP:
            return
        self.indicator = INDICATOR.FOLLOW_ME
        # Need to add new future to restart without waiting for acf movement
        logger.debug("continuing after stop..")

        if ftg.lights is None:
            logger.warning("..no light, cannot continue")
            return
        closestLight, dist = ftg.lights.closest(ftg.aircraft.position())
        if closestLight is None:
            logger.debug("..no close light? cannot continue")
            return

        ahead = ftg.aircraft.adjustAhead(rabbit_mode=ftg.flightLoop.rabbitMode)
        light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead)
        self.target.sr_position = OnRoute(index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
        self.adjustSpeed(aircraft=ftg.aircraft, rabbit_mode=ftg.lights.rabbit_mode, ahead=ahead)
        logger.debug("..continuing")

    # Abrupt change or route, reset
    #
    def addRoute(self, route, index: int | None = None, distance: float | None = None, tick: bool = False) -> bool:
        # Returns whether ticked
        self._future.put((route, index, distance))
        if index is not None and distance is not None:
            logger.debug("added new route with target")
        if tick:
            return self.loadRoute()
        return False

    def loadRoute(self, adjust: bool = True) -> bool:
        # Installs a route to travel automatically.
        # Target is set if present.
        # Returns whether ticked
        if self._future.qsize() == 0:
            logger.debug("no more route")
            return False
        old_route = self.current.sr_route
        route_data = self._future.get()
        self.current.sr_route = route_data[0]
        # need to adjust current pos...
        c = self.route.srClosestOnRoute(route=self.current.sr_route, point=old_route[-1]) if adjust else (0, 0.0)
        self.current.sr_position = OnRoute(index=c[0], distance=c[1])
        logger.debug(f"new route loaded c={self.current.sr_position}")
        if route_data[1] is not None and route_data[2] is not None:
            self.target.sr_position = OnRoute(index=route_data[1], distance=route_data[2])
            logger.debug(f"new target set t={self.target.sr_position}")
        else:
            self.target.sr_position = OnRoute(index=len(self.current.sr_route) - 1, distance=0)
            logger.debug("new target set end of route")
        return True

    def resetRoute(self):
        # They won't be any valid route anymore.
        # We have to stop the future
        logger.log(8, f"reseting cursor, {self._future.qsize()} planned route(s) removed)..")
        self._future.clear()
        logger.log(8, "..reset")

    def changeRoute(self, ftg):
        if self.status != CURSOR_STATUS.ACTIVE:
            logger.warning(f"change route: Cursor is not active (is {self.status})")
            return
        try:
            self.status = CURSOR_STATUS.HOLD  # lock, prevents tick when changing routes
            logger.debug("change route..")
            self.route = ftg.route
            logger.log(8, "..new route installed..")

            acf_speed = ftg.aircraft.speed()

            if ftg.lights is None:
                logger.warning("..no light, cannot route to new route")
                return
            closestLight, dist = ftg.lights.closest(ftg.aircraft.position())
            if closestLight is None:
                logger.debug("..no close light to start, directing to start of route..")
                closestLight = 0

            logger.log(8, "..estimate new position ahead of aircraft..")
            # if route changed we assume aircraft is moving and this.inited
            ahead = ftg.aircraft.adjustAhead(rabbit_mode=ftg.flightLoop.rabbitMode)
            join_time = 20  # secs, reasonable time from spawn position to ahead of acf, aircraft will speed up
            acf_ahead = min(acf_speed, self.detail.fast_speed) * (join_time * 1.5)
            ahead_at_join = acf_ahead + ahead
            light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)

            join_route = self.route.srStraightRoute(start=self.current.position, end=light_ahead.position, heading=light_ahead.heading)
            self.resetRoute()
            self.addRoute(join_route)
            self.addRoute(self.route.smoothRoute, index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
            self.adjustSpeed(aircraft=ftg.aircraft, rabbit_mode=ftg.lights.rabbit_mode, ahead=ahead)
            # self.current.sr_position = OnRoute(index=0, distance=0.0)
            #
            # Turn from here to
            # vtx = destination(self.current.position, self.current.heading, d=30)
            # turn = Turn(vertex=vtx, l_in=self.current.heading, l_out=join_route.bearing(), radius=self.detail.turn_radius)
            # join_route = turn.points + light_ahead.position
            #
            # we will move the car well ahead, the car should not backup
            # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
            light_progress = closestLight + int(acf_ahead / ftg.lights.distance_between_green_lights)
            logger.debug(
                f"..move on route at {sf(ahead_at_join, 'm')} ahead, heading={round(join_route.bearing(), 0)}, in {round(join_time, 1)}s (aircraft will be at light index {light_progress}).."
            )
            # we move the car in front of acf, and progress at same speed as acf.
            self.status = CURSOR_STATUS.ACTIVE  # ! possible chance of tick attempt between this and process future() below
            logger.debug("..route changed, already taxiing")
        except:
            self.status = CURSOR_STATUS.ACTIVE
            logger.error("error while changing route", exc_info=True)

    # Information external interface
    #
    def distance(self, position) -> float:
        # compute and uses bearing to see if car in front of acf or behind
        brng = bearing(self.current.position, position)
        self.uturned = abs(self.current_bearing - brng) > 160
        if self.uturned:
            logger.debug("aircraft passed fmcar")
        self.current_bearing = brng
        self.current_distance = distance(self.current.position, position)
        return self.current_distance

    def speed(self) -> float:
        return self.current.speed

    def _targetReached(self, target: OnRoute) -> bool:
        r = False
        if self.current.sr_position.index > target.index:
            r = True
        elif self.current.sr_position.index == target.index and self.current.sr_position.distance >= target.distance:
            r = True
        # logger.debug(f"{r}: {self.current.sr_position} {'>=' if r else '<'} {self.target.sr_position}")
        return r

    def targetReached(self) -> bool:
        return self._targetReached(target=self.target.sr_position)

    def destinationReached(self) -> bool:
        return self._targetReached(target=self.current.sr_end)

    # Speed adjustment
    #
    def smoothConverge(self, s1: float, s2: float) -> float:
        # smoothly accelerate or decelerate from s1 to s2
        SMOOTH = 0.1
        return s1 + SMOOTH * (s2 - s1)

    def adjustSpeed(self, aircraft, rabbit_mode: RABBIT_MODE, ahead: float, speed_type: str = "normal") -> float:  # speed_type = {normal, fast, slow, max!}
        # "Slow" speed adjustment procedure, called by flightloop when aircraft has moved; sets aim_speed
        #
        default_speed = getattr(self.detail, speed_type + "_speed")
        acf_speed = aircraft.speed()
        if acf_speed < AIRCRAFT_MIN_SPEED or self.current.position is None:  # almost at rest
            self.aim_speed = default_speed
            logger.debug(f"aim={sf(default_speed, 'm/s')} (rabbit mode={rabbit_mode}, target={sf(acf_speed, 'm/s')})")
            return self.aim_speed
        #
        # Adjust the car speed according to requests and acf speed
        fmcar_speed = acf_speed  # initial value
        dist = self.distance(aircraft.position_point())
        drange = aircraft.aheadRange(rabbit_mode=rabbit_mode)
        rf = aircraft.RABBIT_FACTOR_SPEED[rabbit_mode]  # official rabbit factor
        f2 = 1.0  # alternate factor

        logger.debug(f"d={sf(dist, 'm/s')}, range={drange}, should be={sf(ahead, 'm/s')}, rabbit mode={rabbit_mode}, acf={sf(acf_speed, 'm/s')}..")

        if dist > drange[1]:  # does the car need to slow down because too far?
            f2 = min(rf, 0.9)
            logger.debug(f"fmcar too far, need to slow down (factor={f2}, {sf(dist, 'm')} > {sf(drange[1], 'm')})")
            fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
        elif dist < drange[0]:  # does the car need to accelerate because too close?
            logger.debug(f"fmcar too close.. ({sf(dist, 'm')} < {sf(drange[0], 'm')})")
            if rabbit_mode in [RABBIT_MODE.SLOWER, RABBIT_MODE.SLOWEST]:  # does the car need to slow down because nearing a turn, stop, etc. (rabbit slower, slowest)
                logger.debug(f"..but it is ok because we need to go slow (rabbit factor={rf})")
                fmcar_speed = self.smoothConverge(fmcar_speed, acf_speed * rf)
            else:  # does the car need to accelerate because long straight line? (rabbit faster, fastest)
                f0 = 1 + 0.1 * acf_speed
                f2 = max(rf, f0)
                logger.debug(f"..need to accelerate (factor={round(f2, 2)})")
                fmcar_speed = self.smoothConverge(fmcar_speed, acf_speed * f2)
        else:  # we are within range, we keepup with the aircraft but we might need to show something with rabbit...
            logger.debug(f"fmcar on target (rabbit factor={rf})")
            if dist < ahead:
                f2 = 1.2
                fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
                logger.debug("fmcar should be more ahead, speeding up a bit")
            elif dist > ahead:
                f2 = 0.9
                fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
                logger.debug("fmcar should be less ahead, slowing down a bit")
            else:
                fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * rf)

        self.aim_speed = min(fmcar_speed, self.detail.max_speed)
        speed_type = "" if speed_type == "normal" else speed_type + " "
        logger.debug(f"..{speed_type}aim={sf(self.aim_speed, 'm/s')}")
        return self.aim_speed

    def _adjustLocalSpeeds(self):
        # Internal ("fast") speed adjustment process, while car is moving on long path.
        # On smaller path, adjustment is done on start and there is no need of re-adjustment during the path.
        #
        # Car current.speed converges towards target.speed.
        # Target.speed converges towards target_speed.
        # Target_speed has to be moving a bit at least, otherwise we converge towards speed=0.
        # Please note: Only speed is adjusted, not target time.
        ots = self.target.speed  # orignal target speed, for debugging purpose
        ocs = self.current.speed
        if self.active:
            self.target.speed = self.smoothConverge(self.target.speed, self.aim_speed)  # self.faster((self.target.speed + self.aim_speed) / 2)  # speeds avg
        self.current.speed = self.smoothConverge(self.current.speed, self.target.speed)  # self.faster((self.current.speed + self.target.speed) / 2)  # speeds avg
        # speeds = (self.aim_speed, self.current.speed, self.target.speed, ots, ocs)
        # if abs(max(speeds) - min(speeds)) > 0.05:  # minimize logging
        if abs(self.current.speed - self.aim_speed) < 0.1 and not self.speed_reached:
            self.speed_reached = True
            logger.debug(
                f"aim speed ~reached={sf(self.aim_speed, 'm/s')}: curr={sf(ocs, 'm/s')}->{sf(self.current.speed, 'm/s')}, target={sf(ots, 'm/s')}->{sf(self.target.speed, 'm/s')}"
            )

    def nextTurnIndicator(self) -> INDICATOR:
        # returns a turn indicator to display if necessary
        # Only comes here if indicator is not STOP.
        #
        edge_idx = self.current.current_vertex.getProp(SMOOTH_ROUTE.ROUTE_INDEX)
        if edge_idx is None or edge_idx == -1:  # not on aircraft route, no indicator
            return INDICATOR.FOLLOW_ME
        vertex = self.route.vertices[edge_idx]
        distance_on_edge = distance(vertex, self.current.position)  # roughly
        if round(self.last_dist_to_next_vertex, 1) == round(distance_on_edge, 1):  # not moved
            logger.log(8, f"car is not moving, no change {self._indicator.name}")
            return self._indicator
        self.last_dist_to_next_vertex = distance_on_edge

        dist_to_next_turn_at_start_vtx = self.route.dtb[edge_idx]
        dist_to_next_turn = dist_to_next_turn_at_start_vtx - distance_on_edge
        turn_vertex = vertex.getProp("tobrake_index")
        turn = self.route.turns[turn_vertex]
        logger.log(8, f"after vertex {edge_idx}, d={sf(distance_on_edge, 'm')}, next turn at {sf(dist_to_next_turn, 'm')}, {sf(turn, 'D')}")
        if dist_to_next_turn < self.detail.indicator_warning_distance:  # and abs(turn) > TURN_LIMIT
            return INDICATOR.LEFT if turn < 0 else INDICATOR.RIGHT
        return INDICATOR.FOLLOW_ME

    # Move
    #
    def nextPosition(self, t: float):
        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("probably changing route....cannot move")
            return self.current.position, self.current.heading, self.current.sr_position, 0.0
        if self.destinationReached():
            logger.debug("destination reached")
            if not self.loadRoute():
                msg = "no more route"
                if self.msg != msg:
                    logger.debug(msg)
                    self.msg = msg
                return self.current.position, self.current.heading, self.current.sr_position, 0.0
        if self.targetReached():
            msg = "target reached"
            if self.msg != msg:
                logger.debug(msg)
                self.msg = msg
            if self.aim_speed > 0:
                self.aim_speed = 0.0
        self._adjustLocalSpeeds()
        if self.current.speed == 0.0:
            msg = "at rest"
            if self.msg != msg:
                logger.debug(msg)
                self.msg = msg
            return self.current.position, self.current.heading, self.current.sr_position, 0.0
        if self.indicator != INDICATOR.STOP:
            self.indicator = self.nextTurnIndicator()  # compute turn indicator code for turns
        d = t * self.current.speed
        point, hdg, idx, dist = self.route.srAheadRoute(self.current.sr_route, i=self.current.sr_position.index, start=self.current.sr_position.distance, dist=d)
        sr_position = OnRoute(index=idx, distance=dist)
        # logger.debug(f"d={sf(self.distance(self.aircraft.position_point()), 'm')}, car={sf(self.current.speed, 'm/s')}, acf={sf(self.aircraft.speed(), 'm/s')}")
        # logger.debug(f"progress {idx} {sf(dist, 'm')}")
        return point, hdg, sr_position, self.current.speed

    def _move(self, t: float) -> int | float:
        # Currently: only linear interposition
        # between start and end
        # Future: d += speed * t with avg(speed) for acceleration
        def slow_debug(c, s):
            if c % 200 == 0:
                logger.debug(s)

        if self.cursor is None:
            slow_debug(self.cnt, "no cursor to move")
            self.cnt += 1
            return 2.0  # secs

        self.current.position, dummy, self.current.sr_position, self.current.speed = self.nextPosition(t=t)
        if self.current.speed > 0:
            self.cursor.move(lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.above_ground)
            if self.indicator_cursor is not None:
                self.indicator_cursor.move(
                    lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.indicator_shift[0], fwd=self.detail.indicator_shift[1]
                )
        return -1

    # End of route elegance: End of route is reached and Cursor progress a little more then vanishes
    #
    def finish(self, message: str = ""):
        # @todo: Do better move, especially on runways
        # Add a last move, ahead and sideway, wait a few seconds and vanishes
        if not self.active:
            logger.debug("cursor not active")
            return
        if self.status == CURSOR_STATUS.FINISHING:
            logger.debug("cursor already finishing")
            return

        self.status = CURSOR_STATUS.FINISHING
        LEAVE_DIST_AHEAD = 100  # m
        LEAVE_DIST_SIDE = 50  # m

        hdg = self.route.orientLastVertex()
        rnd = 1 if (len(self.route.route) % 2) == 0 else -1
        if self.route.move == MOVEMENT.DEPARTURE and self.route.departure_runway is not None:
            # we have to set the rwy heading on the last future (its future heading...)
            last_pos = self._future.last()
            txt = "(target)"
            if last_pos is None:
                last_pos = self.target
                txt = "(last)"
            logger.log(8, f"last segment before runway: {last_pos} {txt}")
            LEAVE_DIST_AHEAD = 200
            LEAVE_DIST_SIDE = 100  # m
            if self.route.precise_start is not None:  # leaves towards departure area, like return to position
                rnd = -self.route.departure_runway.side(self.route.precise_start)
        elif self.route.move == MOVEMENT.ARRIVAL:
            LEAVE_DIST_AHEAD = 40  # m, to service road in front of aircraft?
            LEAVE_DIST_SIDE = 100  # m, on service road, away to vanish out of sight
        else:
            logger.debug("default finish")
        end = self.route.vertices[-1]
        # Last point of route to "away"
        d1 = destination(src=end, brngDeg=hdg, d=LEAVE_DIST_AHEAD)
        # self.returnToRamp(final_position=d1)
        spd = self.detail.leave_speed
        hdg1 = hdg
        hdg = hdg + 90 * rnd
        td = LEAVE_DIST_AHEAD / spd
        logger.debug(f"carry forward {sf(LEAVE_DIST_AHEAD, 'm')} in {sf(td, 's')} heading {sf(hdg1, 'D')}, terminates heading {sf(hdg, 'D')}")
        leave_sr_route = self.route.srStraightRoute(start=end, end=d1, heading=hdg)
        self.addRoute(leave_sr_route)

        # returnToRamp(final_position=d1)

        # "Away" to away and on the size
        final_dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        spd = self.detail.leave_speed
        td = LEAVE_DIST_SIDE / spd
        logger.debug(f"carry sideway {sf(LEAVE_DIST_SIDE, 'm')} in {sf(td, 's')} heading {sf(hdg, 'D')}")
        exit_sr_route = self.route.srStraightRoute(start=d1, end=final_dest, heading=hdg)
        self.addRoute(exit_sr_route)
        self.active = False
        logger.debug("cursor inactive")
        logger.debug(f"cursor finish programmed ({message})")

    # Interface to flight loop
    #
    def spawn(self, ftg, nextStop: int) -> tuple:
        SPAWN_SIDE_DISTANCE = 50
        ROUTE_JOIN_TIME = 20  # secs

        self.aircraft = ftg.aircraft
        pos = self.aircraft.position()

        if not self.aircraft.moving() and ftg.move == MOVEMENT.DEPARTURE:
            # 1. Spawn the car next to (random) side of aircraft
            rnd = 1 if (int(pos[0] * 10000) % 2) == 0 else -1
            fs = ftg.route.before_route()
            # spawn at spot randomly left or right of current aircraft position
            spawn = destination(fs.start, fs.bearing() + rnd * 90, SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # s1 = destination(fs.start, fs.bearing() + rnd * 90, self.SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # spawn = destination(s1, fs.bearing(), self.SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # from spot to begining of route
            join_sr_route = self.route.srStraightRoute(start=spawn, end=ftg.route.vertices[0], heading=ftg.route.edges_orient[0])
            self.init(route=join_sr_route, position=spawn, heading=join_sr_route[0].getProp(SMOOTH_ROUTE.BEARING), speed=0.0)  # @todo always spawned at rest?
            ahead = ftg.aircraft.adjustAhead(rabbit_mode=ftg.lights.rabbit_mode)
            light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=0, ahead=ahead)
            next_stop_light = ftg.lights.lights[nextStop]
            if next_stop_light.srIndex < light_ahead.srIndex or (next_stop_light.srIndex == light_ahead.srIndex and next_stop_light.distFromsrIndex < light_ahead.distFromsrIndex):
                self.indicator = INDICATOR.STOP
                self.addRoute(self.route.smoothRoute, index=next_stop_light.srIndex, distance=next_stop_light.distFromsrIndex)
            else:
                self.addRoute(self.route.smoothRoute, index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
            self.aim_speed = self.detail.normal_speed
            return light_index, 0
        # If arrival or moving:
        # Aircraft is moving (example if new green request) or we are on arrival (or both)
        #
        # 1. Spawn the car next to (random) side of aircraft, half way "ahead" so that pilot can see the car on the side
        ahead = self.aircraft.adjustAhead(rabbit_mode=ftg.lights.rabbit_mode)
        rnd = 1 if (int(ahead) % 2) == 0 else -1
        spawn = destination(ftg.route.precise_start, self.aircraft.heading(), ahead / 2)  # ahead/2 ahead
        spawn = destination(spawn, self.aircraft.heading() + rnd * 90, SPAWN_SIDE_DISTANCE)
        closestLight, dist = ftg.lights.closest(pos)
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0
        # during join travel, aircraft will move forward, aircraft might still be running fast, we limit ot speed of car:
        fast = self.adjustSpeed(aircraft=ftg.aircraft, rabbit_mode=ftg.lights.rabbit_mode, ahead=ahead, speed_type="fast")
        acf_ahead = fast * ROUTE_JOIN_TIME
        ahead_at_join = acf_ahead + ahead
        light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
        join_route = self.route.srStraightRoute(start=spawn, end=light_ahead.position, heading=light_ahead.heading)
        initial_speed = join_route[-1].getProp(SMOOTH_ROUTE.TOTAL) / ROUTE_JOIN_TIME
        logger.debug(f"spawning ahead {round(ahead / 2, 1)}m at {rnd} {SPAWN_SIDE_DISTANCE}m side of precise start position, speed is {round(initial_speed,1)}m/s..")
        # we spawn the car at aircraft speed + speed to travel in front of acf.
        self.init(route=join_route, position=join_route[0], heading=join_route[0].getProp(SMOOTH_ROUTE.BEARING), speed=initial_speed)  # @todo always spawned at rest?
        #
        # 2. Movement from where the car is spawned to ahead of acf on route, goes in a straight line
        # we will move the car well ahead, the car should not backup
        # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
        # we can expect "cannot backup on route" while aircraft catches up with its supposed position
        # and the fmcar already in position
        acf_light_progress = min(closestLight + int(acf_ahead / ftg.lights.distance_between_green_lights), len(ftg.lights.lights) - 1)
        fmc_light_progress = light_index
        logger.debug(
            f"..move on route at {round(ahead_at_join, 1)}m ahead, heading={sf(join_route[0].getProp(SMOOTH_ROUTE.BEARING), 'D')}, in {round(join_time, 1)}s (aircraft will be at light index {acf_light_progress} when fmcar join route).."
        )
        # we move the car in front of acf, and progress at same speed as acf.
        self.addRoute(self.route.smoothRoute)
        self.aim_speed = initial_speed  # go!
        # finally, we have to tell future_index() where car is when it join route
        # so that when move() catches up with future_index() it will start from there
        # (after above future)
        logger.debug(f"..already taxiing (car at light {fmc_light_progress})")
        return fmc_light_progress, acf_light_progress

    def move(self, ftg, acf_speed, acf_move, closestLight, nextStop, fmc_light_progress, acf_light_progress) -> tuple:
        logger.debug("moving..")
        ahead = ftg.aircraft.adjustAhead(rabbit_mode=ftg.lights.rabbit_mode)
        total_ahead = acf_move + ahead
        light = ftg.lights.lights[closestLight]
        logger.debug(f"aircraft closest light={closestLight} on edge index={light.edgeIndex}, distance from edge={round(light.distFromEdgeStart, 1)}m")
        # logger.debug(f"ahead={round(total_ahead, 1)}m = {round(ahead, 1)}m + acf move={round(acf_move, 1)}m")
        # At next iteration, acf will move acf_move, and fmcar need to be ahead
        # So at next iteration (t=now + iterTime), car need to be (acf_move+ahead) in front
        logger.debug(f"should move {round(total_ahead, 1)}m (ahead={round(ahead, 1)}m + acf={round(acf_move, 1)}m)")
        light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=total_ahead)
        logger.debug(f"should move to light={light_index} on edge index={light_ahead.edgeIndex}, distance from edge={round(light_ahead.distFromEdgeStart, 1)}m")
        if light_index > nextStop:
            logger.debug(
                f"car is at light={fmc_light_progress}, cannot move to light={light_index} because it is after stop at light {nextStop}, need to clear stop before (note: indicator={self.indicator})"
            )
            # logger.debug("..not moved")
            if fmc_light_progress < nextStop:
                light_at_stop = ftg.lights.lights[nextStop]
                self.target.sr_position = OnRoute(index=light_at_stop.srIndex, distance=light_at_stop.distFromsrIndex)
                self.adjustSpeed(aircraft=ftg.aircraft, rabbit_mode=ftg.lights.rabbit_mode, ahead=total_ahead)
                fmc_light_progress = nextStop
                logger.debug(f"..moved to next stop (car at light {fmc_light_progress})")
            else:
                logger.debug(f"..not moved: car is at light={fmc_light_progress}, next  stop at light {nextStop}")
        else:
            # logger.debug(f"light ahead={light_index} on edge index={light_ahead.edgeIndex}, distance from edge={round(light_ahead.distFromEdgeStart, 1)}m")
            # logger.debug(f"future_index to i={light_ahead.edgeIndex}, d={round(light_ahead.distFromEdgeStart,1)}m, spd={round(fmc_speed,1)}m/s")
            self.target.sr_position = OnRoute(index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
            self.adjustSpeed(aircraft=ftg.aircraft, rabbit_mode=ftg.lights.rabbit_mode, ahead=total_ahead)
            fmc_light_progress = light_index
            logger.debug(f"..moved  (car at light {fmc_light_progress})")
        # Checks for end of lights/end of trip
        if light_index == (len(ftg.lights.lights) - 1) and self.status != CURSOR_STATUS.FINISHING:  # reached last light
            logger.debug(f"fmcar reached end of lights (car at light={light_index}/{len(ftg.lights.lights) - 1}), initiating finish trip")
            self.finish("end of lights")

        return fmc_light_progress, acf_light_progress
