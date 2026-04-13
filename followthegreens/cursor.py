from __future__ import annotations
import os
from dataclasses import dataclass, fields
from datetime import datetime
from enum import IntEnum, StrEnum
from sre_compile import IN

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import RABBIT_MODE, logger, MOVEMENT, INDICATOR, AIRCRAFT_MIN_SPEED
from .geo import Point, bearing, destination, distance, turn
from .lightstring import XPObject, LightType
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


class DBG(IntEnum):
    NO_SR_BRACKET = 1


def ts() -> float:
    return datetime.now().timestamp()


def st(t: float) -> float:
    # format timestamp
    if t <= 0:
        return 0.0
    d = datetime.fromtimestamp(t)
    d = d.replace(hour=d.hour - 2, minute=0, second=0, microsecond=0)
    # t0 = d.timestamp()
    return datetime.fromtimestamp(t).strftime("%M:%S.%f")  # round(t - t0, 3)


def sf(t: float, unit: str = "") -> str:
    # format distance or speed
    return f"{round(t, 1)}{unit}"


def slow_debug(c, s):
    if c % 200 == 0:
        logger.debug(s)


NOT_ON_ROUTE = -1
SHOW_BRACKET = True


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
    route: tuple | None = None  # pointer to route

    def __str__(self):
        """Returns a string containing only the non-default field values."""
        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values

        def f(i):
            if type(i) in [list, tuple] and len(i) > 0 and isinstance(i[0], Point):
                return f"[ route[{len(i)}] ]"
            return sf(i, "m") if type(i) is float else i

        s = ", ".join(f"{field.name}={f(getattr(self, field.name))!r}" for field in fields(self))
        return f"{type(self).__name__}({s})"

    def reached(self, target: OnRoute) -> bool:
        # Means self is at or after target
        if target.index == NOT_ON_ROUTE:
            logger.debug(f"target not on route {target}")
            return False
        r = False
        if self.index > target.index:
            r = True
        elif self.index == target.index and self.distance >= target.distance:
            r = True
        # logger.debug(f"{r}: {self.current.sr_position} {'>=' if r else '<'} {self.target.sr_position}")
        return r


@dataclass
class Situation:
    """4 position with other information"""

    sr_route: tuple = tuple()  # current route for Cursor
    sr_position = OnRoute()  # position on sr_route equivalent to position

    sr_min = OnRoute()  # braket or buffer values from best distance range
    sr_max = OnRoute()  # sr_route should remain between those two values
    sr_stop = OnRoute(index=NOT_ON_ROUTE, distance=-1)  # sr_route cannot drive beyond this point, distance < 0 is sign there is no stop

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

    def hasStop(self) -> bool:
        return self.sr_stop.distance >= 0

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

    def __init__(self, detail, ftg) -> None:
        self._ftg = ftg
        self.detail = detail
        self.cursor_object = CursorObject(detail.filename)
        # self.indicator_object = CursorObject("indicator/indicator.obj")
        self.cursor = XPObject(None, 0, 0, 0)

        self.cursor_min = XPObject(None, 0, 0, 0)
        self.cursor_max = XPObject(None, 0, 0, 0)
        self.cursor_mid = XPObject(None, 0, 0, 0)

        self._indicator = INDICATOR.FOLLOW_ME
        self.hudText = INDICATOR.FOLLOW_ME.name
        self.indicator_object = None
        self.indicator_cursor = None
        if detail.indicator:
            indicator = CursorType(filename="indicator/indicator.obj", indicator_shift=detail.indicator_shift)
            self.indicator_object = CursorObject(indicator.filename)
            self.indicator_cursor = XPObject(None, 0, 0, 0)

        self._status = CURSOR_STATUS.NEW
        self.active = False  # accepts external requests if active

        self.route = ftg.route  # route that the cursor must follow
        self.en_route = False
        self.fmc_light_progress = 0

        self._future = SimpleQueue()

        # Current, initialized with init() and incrementally followed
        self.current = Situation()  # where it is
        self.target = Situation()  # up to where it can go

        self._aim_speed = 0.0

        # working var for interpolation
        self.refcursor = "FtG:cursor"
        self.flightLoop = None
        self.nextIter = -1

        self.cnt = -1
        self.msg = ""
        self.last_dist_to_next_vertex = 0.0

        # monitoring
        self.current_distance = 0.0  # distance to acf
        self.current_bearing = 0.0  # acf -> fmcar
        self.uturned = False  # now fmcar -> acf!

        logger.info(str(self.detail))
        logger.debug(f"route end: {self.route.move}, {self.route.departure_runway}, {self.route.arrival_runway}")

    def __del__(self):
        self.destroy()
        self.status = CURSOR_STATUS.DELETED

    @property
    def ftg(self):
        return self._ftg

    @property
    def lights(self):
        return self._ftg.lights

    @property
    def aircraft(self):
        return self._ftg.aircraft

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

    @indicator.setter
    def indicator(self, indicator: INDICATOR):
        if indicator == INDICATOR.SLOW:
            self.setHudText(">> S L O W <<")
            logger.info(f"Hud text is now {indicator.name}")
        elif indicator == INDICATOR.EMPTY:
            self.setHudText(" ")
            logger.info("Hud text is now empty/blank")
        elif indicator != self._indicator:
            self._indicator = indicator
            self.setHudText()
            logger.info(f"Indicator is now {indicator.name}")

    def setHudText(self, text: str = ""):
        if text != "":
            self.hudText = text
            return
        if self._indicator == INDICATOR.STOP:
            self.hudText = "S T O P"
        elif self._indicator == INDICATOR.LEFT:
            self.hudText = "<<<  LEFT"
        elif self._indicator == INDICATOR.RIGHT:
            self.hudText = "RIGHT >>>"
        else:
            self.hudText = "FOLLOW CAR"

    def setAimSpeed(self, speed, reason: str = "") -> float:
        if reason != "":
            reason = ", " + reason
        if self._aim_speed != speed:
            self.speed_reached = False
            logger.debug(f"new aim speed={self.aim_speed} -> {speed}{reason}")
            self._aim_speed = speed
        # else:
        #     logger.debug(f"aim speed already set at {speed}{reason}")

    @property
    def aim_speed(self) -> float:
        return self._aim_speed

    @aim_speed.setter
    def aim_speed(self, speed: float) -> float:
        # if self.active ...
        speed = round(speed, 1)
        if self._aim_speed != speed:
            self.speed_reached = False
            logger.debug(f"new aim speed={self.aim_speed} -> {speed}")
            self._aim_speed = speed

    @property
    def usable(self) -> bool:
        return self.cursor is not None and self.cursor_object.has_obj

    @property
    def inited(self) -> bool:
        return self.current.position is not None and self.route is not None

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

        if SHOW_BRACKET:
            min_light = LightType.create(name="lmin.obj", color=(0, 1, 0), size=40, intensity=60, texture=3)
            self.cursor_min.position = self.current.position  # initial position where will appear
            self.cursor_min.heading = self.current.heading
            self.cursor_min.place(lightType=LightType("min_light", min_light))
            self.cursor_min.on()
            max_light = LightType.create(name="lmax.obj", color=(1, 0, 0), size=40, intensity=40, texture=3)
            self.cursor_max.position = self.current.position  # initial position where will appear
            self.cursor_max.heading = self.current.heading
            self.cursor_max.place(lightType=LightType("max_light", max_light))
            self.cursor_max.on()
            mid_light = LightType.create(name="lmid.obj", color=(0, 0, 1), size=40, intensity=40, texture=3)
            self.cursor_mid.position = self.current.position  # initial position where will appear
            self.cursor_mid.heading = self.current.heading
            self.cursor_mid.place(lightType=LightType("mid_light", mid_light))
            self.cursor_mid.on()

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
        if SHOW_BRACKET:
            self.cursor_min.destroy()
            self.cursor_min = None
            self.cursor_max.destroy()
            self.cursor_max = None
            self.cursor_mid.destroy()
            self.cursor_mid = None
            # NOTE: min_light, max_light, and mid_light objects not destroyed (we're in debug mode...)
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
        if self.cursor is None:
            if self.cnt % 200 == 0:
                slow_debug(self.cnt, "no cursor")
            self.cnt += 1
            return 3.0

        try:
            r = self._move(t=elapsedSinceLastCall)
            return r if type(r) in [int, float] else -1
        except:
            logger.error("error", exc_info=True)
        return 5.0

    def mustStop(self) -> bool:
        # should not stop on straightRoutes. Only onRoute().
        return self.onRoute() and self.indicator == INDICATOR.STOP  # Kinda a side effect to notify fm car must stop, dedicated status var would be cleaner

    def mustStopAt(self, nextStop: int):
        # Aim is to block until canContinue()
        self.indicator = INDICATOR.STOP
        if self.onRoute():
            light = self.lights.lights[nextStop]
            self.current.sr_stop = OnRoute(index=light.srIndex, distance=light.distFromsrIndex)
        # If nextStop reached, self.aim_speed = 0.0

    def canContinue(self):
        # Aim is to restart after mustStopAt()
        if not self.mustStop():
            logger.debug("can continue, must not stop")
            return
        self.indicator = INDICATOR.FOLLOW_ME
        # Need to add new future to restart without waiting for acf movement
        logger.debug("continuing after stop..")
        self.current.sr_stop = OnRoute(index=NOT_ON_ROUTE, distance=-1)

        if self.ftg.lights is None:
            logger.warning("..no light, cannot continue")
            return
        closestLight, dist = self.ftg.lights.closest(self.ftg.aircraft.position())
        if closestLight is None:
            logger.debug("..no close light? cannot continue")
            return

        ahead = self.ftg.aircraft.adjustAhead(rabbit_mode=self.ftg.flightLoop.rabbitMode)
        light_ahead, light_index, dist_left = self.ftg.lights.lightAhead(index_from=closestLight, ahead=ahead)
        self.target.sr_position = OnRoute(index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
        self.cursor_mid.move(lat=light_ahead.position.lat, lon=light_ahead.position.lon, hdg=0, elev=1.0)
        self.adjustSpeed(ahead=ahead)
        logger.debug("..continuing")

    # Abrupt change or route, reset
    #
    def onRoute(self) -> bool:
        a = self.current.sr_route
        return self.route is not None and a is not None and a == self.route.smoothRoute

    def addRoute(self, route, index: int | None = None, distance: float | None = None, speed: float | None = None, tick: bool = False) -> bool:
        # Returns whether ticked
        self._future.put((route, index, distance, speed))
        if index is not None and distance is not None:
            logger.debug("added new route with target")
        if tick:
            return self.loadRoute()
        return False

    def loadRoute(self, adjust: bool = True) -> bool:
        # Installs a route to travel automatically.
        # Target is set if present.
        # Returns whether ticked
        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("probably changing route....cannot load route")
            return False

        if self._future.qsize() == 0:
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
            return False
        old_route = self.current.sr_route
        route_data = self._future.get()
        self.current.sr_route = route_data[0]
        logger.debug(f"new route loaded {self.current.sr_position}")
        # need to adjust current pos...
        c = self.route.srClosestOnRoute(route=self.current.sr_route, point=old_route[-1]) if adjust else (0, 0.0)
        self.current.sr_position = OnRoute(index=c[0], distance=c[1])
        logger.debug(f"new current position {c}")
        if route_data[1] is not None and route_data[2] is not None:
            self.target.sr_position = OnRoute(index=route_data[1], distance=route_data[2])
            logger.debug(f"new target set t={self.target.sr_position}")
        else:
            self.target.sr_position = OnRoute(index=len(self.current.sr_route) - 1, distance=0)
            logger.debug("new target set end of route")
        if route_data[3] is not None:
            self.setAimSpeed(speed=route_data[3], reason="requirement from route loaded")
        else:
            logger.debug("no route speed requirement")
        if self.cursor_mid is not None:
            target_pos = self.route.srDestinationRoute(route=self.current.sr_route, i=self.target.sr_position.index, dist=self.target.sr_position.distance)
            self.cursor_mid.move(lat=target_pos.lat, lon=target_pos.lon, hdg=0, elev=1.0)
        return True

    def resetRoute(self):
        # They won't be any valid route anymore.
        # We have to stop the future
        logger.log(8, f"reseting cursor, {self._future.qsize()} planned route(s) removed)..")
        self._future.clear()
        logger.log(8, "..reset")

    def changeRoute(self):
        if self.status != CURSOR_STATUS.ACTIVE:
            logger.warning(f"change route: Cursor is not active (is {self.status})")
            return
        try:
            NEW_ROUTE_JOIN_TIME = 20  # secs, reasonable time from spawn position to ahead of acf, aircraft will speed up

            self.status = CURSOR_STATUS.HOLD  # lock, prevents tick when changing routes
            logger.debug("change route..")
            self.route = self.ftg.route
            logger.log(8, "..new route installed..")

            acf_speed = self.aircraft.speed()

            if self.lights is None:
                logger.warning("..no light, cannot route to new route")
                return
            closestLight, dist = self.lights.closest(self.aircraft.position())
            if closestLight is None:
                logger.debug("..no close light to start, directing to start of route..")
                closestLight = 0

            logger.log(8, "..estimate new position ahead of aircraft..")
            # if route changed we assume aircraft is moving and this.inited
            ahead = self.aircraft.adjustAhead(rabbit_mode=self.ftg.flightLoop.rabbitMode)
            acf_ahead = min(acf_speed, self.detail.fast_speed) * (NEW_ROUTE_JOIN_TIME * 1.5)
            ahead_at_join = acf_ahead + ahead
            logger.debug(f"..car need to be {sf(ahead, 'm')} ahead when joining route, acf will travel  {sf(acf_ahead, 'm')}, total ahead={sf(ahead_at_join, 'm')}..")
            # if closestLight is far ahead, we substract that part
            ahead_brgn = bearing(self.aircraft.position_point(), self.lights.lights[closestLight].position)
            brgn_diff = turn(self.aircraft.heading(), ahead_brgn)
            if abs(brgn_diff) < 60 and dist > self.aircraft.acf_length:
                ahead_at_join -= dist
                logger.debug(
                    f"..reduced total ahead distance to {sf(ahead_at_join, 'm')}, acf is at {sf(dist, 'm')} from closest light (bearing acf={sf(self.aircraft.heading(), 'D')}, light={sf(ahead_brgn, 'D')}, diff={sf(brgn_diff, 'D')}).."
                )
            else:
                logger.debug(
                    f"..not reduced: acf is at {sf(dist, 'm')} from closest light (bearing acf={sf(self.aircraft.heading(), 'D')}, light={sf(ahead_brgn, 'D')}, diff={sf(brgn_diff, 'D')}).."
                )
            light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
            self.fmc_light_progress = light_index
            join_route = self.route.srStraightRoute(start=self.current.position, end=light_ahead.position, heading=light_ahead.heading)
            self.resetRoute()
            self.addRoute(join_route)
            self.status = CURSOR_STATUS.ACTIVE
            self.addRoute(self.route.smoothRoute, index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex, tick=True)  # starts the move right away)
            self.adjustSpeed(ahead=ahead, speed_type="fast")
            #
            # we will move the car well ahead, the car should not backup
            # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
            light_progress = closestLight + int(acf_ahead / self.lights.distance_between_green_lights)
            logger.debug(
                f"..move on route at {sf(ahead_at_join, 'm')} ahead, heading={round(light_ahead.heading, 0)}, in {round(NEW_ROUTE_JOIN_TIME, 1)}s (aircraft will be around light index {light_progress}).."
            )
            # we move the car in front of acf, and progress at same speed as acf.
            logger.debug("..route changed, continue taxiing")
        except:
            self.status = CURSOR_STATUS.ACTIVE
            logger.error("error while changing route", exc_info=True)

    # Information external interface
    #
    def distance(self, position) -> float:
        # This is the bird's-eye view distance between the car and the position
        # Position can be anywhere.
        #
        # compute and uses bearing to see if car in front of acf or behind
        brng = bearing(self.current.position, position)
        self.uturned = abs(self.current_bearing - brng) > 160
        if self.uturned:
            logger.debug("aircraft passed fmcar")
        self.current_bearing = brng
        self.current_distance = distance(self.current.position, position)
        return self.current_distance

    def route_distance(self, sr_position) -> float:
        # This is the distance between two points on the same sr_route
        # following the path, turns, etc.
        #
        c = self.current
        return self.route.srDistanceRoute(route=c.sr_route, i1=c.sr_position.index, dist1=c.sr_position.distance, i2=sr_position.index, dist2=sr_position.distance)

    # @property
    # def speed(self) -> float:
    #     return self.current.speed

    # @speed.setter
    # def speed(self, speed):
    #     self.current.speed = speed

    def at_rest(self) -> bool:
        return self.current.speed == 0  # please note "at_rest()" is different from "not moving()"

    def moving(self) -> bool:
        return self.current.speed > 0.1  # 10cm/sec is moving. please note "at_rest()" is different from "not moving()"

    def nextTurnIndicator(self) -> INDICATOR:
        # returns a turn indicator to display if necessary
        # Only comes here if indicator is not STOP.
        #
        if self.mustStop():
            logger.debug("must stop, cannot change indicator")
            return INDICATOR.STOP
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

    # Speed adjustment
    #
    def smoothConverge(self, s1: float, s2: float) -> float:
        # smoothly converge from s1 to s2
        SMOOTH = 0.1 if s2 > s1 else 0.02
        return s1 + SMOOTH * (s2 - s1)

    def adjustSpeed(self, ahead: float, speed_type: str = "normal") -> float:  # speed_type = {normal, fast, slow, max!}
        # "Slow" speed adjustment procedure, called by flightloop when aircraft has moved; sets aim_speed
        #
        rabbit_mode = self.lights.rabbit_mode
        default_speed = getattr(self.detail, speed_type + "_speed")

        if not self.inited:  # we're on initial move
            self.setAimSpeed(speed=default_speed, reason="not inited")
            return self.aim_speed

        if self.status in [CURSOR_STATUS.FINISHING, CURSOR_STATUS.FINISHED]:
            self.setAimSpeed(speed=default_speed, reason="cursor finishing, no more speed adjustment, set default speed")
            return self.aim_speed

        if not self.onRoute():
            self.setAimSpeed(speed=default_speed, reason="not on route, no speed adjustment, set default speed")
            return self.aim_speed

        aircraft = self.aircraft
        acf_speed = aircraft.speed()
        drange = aircraft.aheadRange(rabbit_mode=rabbit_mode)
        pos_pt = aircraft.position_point()
        acf_dist = self.distance(pos_pt)

        # The plugin currently providing traffic gave us a target with no ID.
        # Express range into min/max targets: [range] -> [sr_min, sr_max]
        DISTANCE_MARGIN = 10.0  # meters
        closestLight, dist = self.lights.closest((pos_pt.lat, pos_pt.lon))
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0
        closest_light = self.lights.lights[closestLight]
        pt, brg, idx, dist = self.route.srAheadRoute(route=self.current.sr_route, i=closest_light.srIndex, dist=closest_light.distFromsrIndex, start=drange[0])
        self.current.sr_min = OnRoute(index=idx, distance=dist + DISTANCE_MARGIN)
        self.cursor_min.move(lat=pt.lat, lon=pt.lon, hdg=0, elev=1.0)
        pt, brg, idx, dist = self.route.srAheadRoute(route=self.current.sr_route, i=closest_light.srIndex, dist=closest_light.distFromsrIndex, start=drange[1])
        if dist > DISTANCE_MARGIN:
            dist -= DISTANCE_MARGIN
        self.current.sr_max = OnRoute(index=idx, distance=dist)
        self.cursor_max.move(lat=pt.lat, lon=pt.lon, hdg=0, elev=1.0)
        #
        # Aircraft too slow, cannot recommend speed from acf speed, returns standard speed
        if acf_speed < AIRCRAFT_MIN_SPEED and acf_dist > drange[0]:
            self.setAimSpeed(speed=0.0, reason=f"aircraft slow ({sf(acf_speed, 'm/s')}) and not too close ({sf(acf_dist, 'm')}), no move")
            return self.aim_speed
        #
        # Adjust the car speed according to requests and acf speed
        fmcar_speed = self.current.speed  # initial value
        rf = aircraft.RABBIT_FACTOR_SPEED[rabbit_mode]  # official rabbit factor
        f2 = 1.0  # alternate factor

        # 1. status
        logger.debug(
            f"d={sf(acf_dist, 'm')}, should be={sf(ahead, 'm')}, range={drange}, car={sf(self.current.speed, 'm/s')}, acf={sf(acf_speed, 'm/s')}, rabbit mode={rabbit_mode}.."
        )
        logger.debug(f"current speed {sf(fmcar_speed, 'm/s')} (start speed for estimate)")

        # 2. work
        work_msg = ""
        if acf_dist > drange[1]:  # does the car need to slow down because too far?
            f2 = min(rf, 0.8)
            work_msg = f"fmcar too far, need to slow down (factor={f2}, rf={round(rf, 2)}, {sf(acf_dist, 'm')} > {sf(drange[1], 'm')})"
            fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
        elif acf_dist < drange[0]:  # does the car need to accelerate because too close?
            work_msg = f"fmcar too close.. ({sf(acf_dist, 'm')} < {sf(drange[0], 'm')})"
            if rabbit_mode in [RABBIT_MODE.SLOWER, RABBIT_MODE.SLOWEST]:  # does the car need to slow down because nearing a turn, stop, etc. (rabbit slower, slowest)
                work_msg += f"..but it is ok because we need to go slow (rabbit factor={rf})"
                self.setHudText(">> S L O W <<")
                fmcar_speed = self.smoothConverge(fmcar_speed, acf_speed * rf)
            else:  # does the car either need to restart moving (from stopped), or accelerate because long straight line? (rabbit faster, fastest)
                if self.mustStop():
                    work_msg += "..must stop"
                    self.setHudText(">> S T O P <<")
                    self.setAimSpeed(speed=0.0, reason=work_msg)
                    return self.aim_speed
                target_speed = max(self.detail.normal_speed, acf_speed)  # car might be at rest, need to get it moving, impose min speed
                f1 = 1.0
                if drange[0] != 0:
                    f1 = 2 - (acf_dist / drange[0])
                f2 = max(rf, f1)
                if self.current.speed < self.detail.normal_speed:  # car was at rest or not moving fast enought
                    fmcar_speed = target_speed * f2
                else:
                    fmcar_speed = self.smoothConverge(fmcar_speed, target_speed * f2)
                work_msg += f"..need to accelerate, new start speed for estimate={round(target_speed, 1)} (factors: f2={round(f2, 2)}, f1={round(f1, 2)}, rf={round(rf, 2)})"
        else:  # we are within range, we keepup with the aircraft but we might need to show something with rabbit...
            self.setHudText()  # reset, case it was slow
            work_msg = f"fmcar within range (rabbit factor={rf})"
            if self.moving():
                if acf_dist < ahead:
                    f2 = 1.2
                    fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
                    work_msg += ", fmcar should be more ahead, speeding up a bit"
                elif acf_dist > ahead:
                    f2 = 0.9
                    fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * f2)
                    work_msg += ", fmcar should be less ahead, slowing down a bit"
                else:
                    fmcar_speed = self.smoothConverge(fmcar_speed, fmcar_speed * rf)
            else:
                work_msg += ", fmcar at rest, may remain at rest"

        # 3. action
        self.setAimSpeed(speed=fmcar_speed, reason=work_msg)
        return self.aim_speed

    def _adjustLocalSpeeds(self):
        # Internal ("fast") speed adjustment process, while car is moving
        # Car current.speed converges towards target.speed.
        # Target.speed converges towards aim_speed.
        # aim_speed has to be moving a bit at least, otherwise we converge towards speed=0.
        # ocs = self.current.speed  # orignal speeds, for debugging purpose
        # ots = self.target.speed
        if self.active and self.target.speed != self.aim_speed:
            self.target.speed = self.smoothConverge(self.target.speed, self.aim_speed)
        if self.current.speed != self.target.speed:
            self.current.speed = self.smoothConverge(self.current.speed, self.target.speed)
        # speeds = (self.aim_speed, self.current.speed, self.target.speed, ots, ocs)
        # if abs(max(speeds) - min(speeds)) > 0.05:  # minimize logging
        if not self.speed_reached and abs(self.current.speed - self.aim_speed) < 0.1:
            self.speed_reached = True
            logger.debug(f"aim speed reached={sf(self.aim_speed, 'm/s')}")
            # logger.debug(
            #     f"aim speed ~reached={sf(self.aim_speed, 'm/s')}: curr={sf(ocs, 'm/s')}->{sf(self.current.speed, 'm/s')}, target={sf(ots, 'm/s')}->{sf(self.target.speed, 'm/s')}"
            # )

    # Local targets
    #
    def _targetReached(self, target: OnRoute) -> bool:
        if target.index == NOT_ON_ROUTE:
            logger.debug(f"target not on route {target}")
            return False
        r = False
        if self.current.sr_position.index > target.index:
            r = True
        elif self.current.sr_position.index == target.index and self.current.sr_position.distance >= target.distance:
            r = True
        # logger.debug(f"{r}: {self.current.sr_position} {'>=' if r else '<'} {target.sr_position}")
        return r

    def nextStopReached(self) -> bool:
        return False if not self.current.hasStop() else self._targetReached(self.current.sr_stop)

    def bracketEndReached(self) -> bool:
        return self._targetReached(self.current.sr_max)

    def beforeBracket(self) -> bool:
        return not self._targetReached(self.current.sr_min)

    def targetReached(self) -> bool:
        # target is point where car should be on route (slows down after, accelerate before)
        return False if not self.onRoute() else self._targetReached(target=self.target.sr_position)

    def endOfRoute(self) -> bool:
        # end of route is end of current sr_route
        return self._targetReached(target=self.current.sr_end)

    def destinationReached(self) -> bool:
        # Destination is the last point on the route
        return self._targetReached(target=OnRoute(index=len(self.route.smoothRoute) - 1, distance=0.0))

    # Move
    #
    def nextPosition(self, t: float):
        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("probably changing route....cannot move")
            return self.current.position, self.current.heading, self.current.sr_position, 0.0  # speed = 0.0 is wrong...

        if self.destinationReached():
            logger.debug("destination reached")  # need to continue on finishing route

        if self.endOfRoute():
            logger.debug("end of route reached")
            if not self.loadRoute():
                if self.aim_speed == 0:
                    logger.debug("no more route")
                else:
                    self.setAimSpeed(speed=0.0, reason="no more route")
                return self.current.position, self.current.heading, self.current.sr_position, 0.0

        if self.at_rest() and self.aim_speed == 0.0:  # must remain at rest
            logger.debug("at rest, must remain at rest")
            return self.current.position, self.current.heading, self.current.sr_position, 0.0

        if self.onRoute():
            if self.current.sr_min.index != NOT_ON_ROUTE and self.current.sr_max.index != NOT_ON_ROUTE:
                if self.nextStopReached():
                    logger.debug("next stop reached, must stop")
                    self.setAimSpeed(speed=0.0, reason="next stop reached")
                if self.at_rest():  # and we may move, it is time to restart moving?
                    if not self.beforeBracket():
                        logger.debug("at rest and after minimal distance, no need to move on")
                        # speed will be adjsuted in adjustSpeed() since acf_dist < drange[0]
                        return self.current.position, self.current.heading, self.current.sr_position, 0.0
                    else:  # no move yet
                        logger.debug("before minimal distance, need to move on")  # debug, remove
                elif self.bracketEndReached():
                    if self.aim_speed != 0.0:
                        if self.aim_speed < AIRCRAFT_MIN_SPEED:
                            self.setAimSpeed(speed=0.0, reason="reached maximal distance, need to stop")
                        else:
                            self.setAimSpeed(speed=round(0.6 * min(self.current.speed, self.aircraft.speed()), 1), reason="reached maximal distance, need to slow down")
                    else:
                        logger.debug("reached bracket end but aim speed is already 0")  # debug, remove
            # else:
            #     logger.debug("on route, but no sr_min/sr_max yet, will check target")

        if self.targetReached():
            if not self.onRoute():
                if self.aim_speed > 0:
                    self.setAimSpeed(speed=0.0, reason="target reached")
                else:
                    if self.current.speed > 0:
                        logger.debug("target reached, stopping")
                    # else:
                    #     logger.debug("target reached, stopped")
            else:
                if self.current.sr_min.index == NOT_ON_ROUTE or self.current.sr_max.index == NOT_ON_ROUTE:
                    if self.current.speed > 0 and self.aim_speed != 0.0:
                        logger.debug("on route, target reached, no sr_min/sr_max, should slow down")
                        self.setAimSpeed(speed=round(self.aircraft.speed(), 1), reason="target reached")

        # self.cnt += 1
        # if self.cnt % 3 == 0:
        self._adjustLocalSpeeds()

        if not self.mustStop():
            self.indicator = self.nextTurnIndicator()  # compute turn indicator code for turns

        d = t * self.current.speed
        point, hdg, idx, dist = self.route.srAheadRoute(self.current.sr_route, i=self.current.sr_position.index, start=self.current.sr_position.distance, dist=d)
        sr_position = OnRoute(index=idx, distance=dist)
        # logger.debug(f"d={sf(self.distance(self.aircraft.position_point()), 'm')}, car={sf(self.current.speed, 'm/s')}, acf={sf(self.aircraft.speed(), 'm/s')}")
        # logger.debug(f"progress {idx} {sf(dist, 'm')}")
        return point, hdg, sr_position, self.current.speed

    def _move(self, t: float) -> int | float:
        self.current.position, dummy, self.current.sr_position, self.current.speed = self.nextPosition(t=t)
        if self.current.speed > 0:
            self.cursor.move(lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.above_ground)
            if self.indicator_cursor is not None:
                self.indicator_cursor.move(
                    lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.indicator_shift[0], fwd=self.detail.indicator_shift[1]
                )
        return -1

    # Interface to flight loop
    #
    # I. Creation
    def spawn(self, nextStop: int):
        SPAWN_SIDE_DISTANCE = 50
        ROUTE_JOIN_TIME = 20  # secs

        pos = self.aircraft.position()

        if not self.aircraft.moving() and self.ftg.move == MOVEMENT.DEPARTURE:
            # 1. Spawn the car next to (random) side of aircraft
            rnd = 1  # 1 if (int(pos[0] * 10000) % 2) == 0 else -1
            fs = self.ftg.route.before_route()
            # spawn at spot randomly left or right of current aircraft position
            spawn = destination(fs.start, fs.bearing() + rnd * 90, SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # s1 = destination(fs.start, fs.bearing() + rnd * 90, self.SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # spawn = destination(s1, fs.bearing(), self.SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            # from spot to begining of route
            join_sr_route = self.route.srStraightRoute(start=spawn, end=self.ftg.route.vertices[0], heading=self.ftg.route.edges_orient[0])
            self.init(route=join_sr_route, position=spawn, heading=join_sr_route[0].getProp(SMOOTH_ROUTE.BEARING), speed=0.0)  # @todo always spawned at rest?
            ahead = self.aircraft.adjustAhead(rabbit_mode=self.lights.rabbit_mode)
            closestLight, dist = self.lights.closest(pos)
            if closestLight is None:
                logger.debug("no close light to start")
                closestLight = 0
            light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead)
            next_stop_light = self.lights.lights[nextStop]
            if next_stop_light.srIndex < light_ahead.srIndex or (next_stop_light.srIndex == light_ahead.srIndex and next_stop_light.distFromsrIndex < light_ahead.distFromsrIndex):
                self.mustStopAt(nextStop)
                self.addRoute(self.route.smoothRoute, index=next_stop_light.srIndex, distance=next_stop_light.distFromsrIndex)
            else:
                self.addRoute(self.route.smoothRoute, index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
            self.setAimSpeed(speed=self.detail.normal_speed, reason="just spawned, start moving, departure and aircraft not moving")
            return
        # If arrival or moving:
        # Aircraft is moving (example if new green request) or we are on arrival (or both)
        #
        # 1. Spawn the car next to (random) side of aircraft, half way "ahead" so that pilot can see the car on the side
        ahead = self.aircraft.adjustAhead(rabbit_mode=self.lights.rabbit_mode)
        rnd = 1 if (int(ahead) % 2) == 0 else -1
        spawn = destination(self.ftg.route.precise_start, self.aircraft.heading(), ahead / 2)  # ahead/2 ahead
        spawn = destination(spawn, self.aircraft.heading() + rnd * 90, SPAWN_SIDE_DISTANCE)
        closestLight, dist = self.lights.closest(pos)
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0
        # during join travel, aircraft will move forward, aircraft might still be running fast, we limit ot speed of car:
        fast = self.adjustSpeed(ahead=ahead, speed_type="fast")
        acf_speed = self.aircraft.speed()
        acf_ahead = acf_speed * ROUTE_JOIN_TIME
        ahead_at_join = acf_ahead + ahead
        logger.debug(f"ahead_at_join={round(ahead_at_join, 1)}m = ahead={round(ahead,1)}m + acf_ahead={round(acf_ahead,1)}m")
        light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
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
        acf_light_progress = min(closestLight + int(acf_ahead / self.lights.distance_between_green_lights), len(self.lights.lights) - 1)
        self.fmc_light_progress = light_index
        logger.debug(
            f"..move on route at {round(ahead_at_join, 1)}m ahead, heading={sf(join_route[0].getProp(SMOOTH_ROUTE.BEARING), 'D')}, in {round(ROUTE_JOIN_TIME, 1)}s (aircraft will be at light index {acf_light_progress} when fmcar join route).."
        )
        # we move the car in front of acf, and progress at same speed as acf.
        medspeed = self.adjustSpeed(ahead=ahead)
        self.addRoute(self.route.smoothRoute, speed=medspeed)
        self.setAimSpeed(speed=initial_speed, reason="just spawned, start moving, aircraft moving or arrival")
        # finally, we have to tell future_index() where car is when it join route
        # so that when move() catches up with future_index() it will start from there
        # (after above future)
        logger.debug(f"..already taxiing (car at light {self.fmc_light_progress})")

    #
    # II. End of route elegance: End of route is reached and Cursor progress a little more then vanishes
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
        self.setAimSpeed(speed=self.detail.normal_speed, reason="finishing, start quitting")

        # "Away" to away and on the size
        final_dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        spd = self.detail.leave_speed
        td = LEAVE_DIST_SIDE / spd
        logger.debug(f"carry sideway {sf(LEAVE_DIST_SIDE, 'm')} in {sf(td, 's')} heading {sf(hdg, 'D')}")
        exit_sr_route = self.route.srStraightRoute(start=d1, end=final_dest, heading=hdg)
        self.addRoute(exit_sr_route)
        self.active = False
        logger.debug("cursor inactive")  # i.e. does not respond to external messages anymore
        logger.debug(f"cursor finish programmed ({message})")

    #
    # III. Slow move, called by slow flight loop
    def move(self, elapsedSinceLastCall, closestLight, nextStop):
        logger.debug("moving..")
        acf_speed = self.aircraft.speed()
        acf_move = acf_speed * elapsedSinceLastCall
        logger.debug(f"acf move {round(acf_move, 1)}m (loop={round(elapsedSinceLastCall, 3)}secs * speed={round(acf_speed, 2)}m/s)")
        ahead = self.aircraft.adjustAhead(rabbit_mode=self.lights.rabbit_mode)
        total_ahead = acf_move + ahead
        light = self.lights.lights[closestLight]
        logger.debug(f"aircraft closest light={closestLight} on edge index={light.edgeIndex}, distance from edge={round(light.distFromEdgeStart, 1)}m")
        # logger.debug(f"ahead={round(total_ahead, 1)}m = {round(ahead, 1)}m + acf move={round(acf_move, 1)}m")
        # At next iteration, acf will move acf_move, and fmcar need to be ahead
        # So at next iteration (t=now + iterTime), car need to be (acf_move+ahead) in front
        logger.debug(f"should move {round(total_ahead, 1)}m (ahead={round(ahead, 1)}m + acf={round(acf_move, 1)}m)")
        light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=total_ahead)
        logger.debug(f"should move to light={light_index} on edge index={light_ahead.edgeIndex}, distance from edge={round(light_ahead.distFromEdgeStart, 1)}m")
        if nextStop is not None:
            logger.debug(f"next stop at index={nextStop} is {self.lights.nextStopCleared(nextStop)}")
        if light_index > nextStop and not self.lights.nextStopCleared(nextStop=nextStop):
            logger.debug(
                f"car is at light={self.fmc_light_progress}, cannot move to light={light_index} because it is after stop at light {nextStop} that is not cleared, need to clear stop before (note: indicator={self.indicator})"
            )
            logger.debug(f"next stop at index={nextStop} is {'cleared' if self.lights.nextStopCleared(nextStop) else 'not cleared'}")
            # logger.debug("..not moved")
            if self.fmc_light_progress < nextStop:
                light_at_stop = self.lights.lights[nextStop]
                self.target.sr_position = OnRoute(index=light_at_stop.srIndex, distance=light_at_stop.distFromsrIndex)
                self.cursor_mid.move(lat=light_at_stop.position.lat, lon=light_at_stop.position.lon, hdg=0, elev=1.0)
                self.adjustSpeed(ahead=total_ahead)
                self.fmc_light_progress = nextStop
                logger.debug(f"..moved to next stop (car at light {self.fmc_light_progress}/{len(self.lights.lights) - 1})")
            else:
                logger.debug(f"..not moved: car is at light={self.fmc_light_progress}/{len(self.lights.lights) - 1}, next  stop at light {nextStop}")
        else:
            # logger.debug(f"light ahead={light_index} on edge index={light_ahead.edgeIndex}, distance from edge={round(light_ahead.distFromEdgeStart, 1)}m")
            # logger.debug(f"future_index to i={light_ahead.edgeIndex}, d={round(light_ahead.distFromEdgeStart,1)}m, spd={round(fmc_speed,1)}m/s")
            self.target.sr_position = OnRoute(index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex)
            self.cursor_mid.move(lat=light_ahead.position.lat, lon=light_ahead.position.lon, hdg=0, elev=1.0)
            self.adjustSpeed(ahead=total_ahead)
            self.fmc_light_progress = light_index
            logger.debug(f"..moved  (car at light {self.fmc_light_progress}/{len(self.lights.lights) - 1})")
        # Checks for end of lights/end of trip
        if self.fmc_light_progress == (len(self.lights.lights) - 1) and self.status != CURSOR_STATUS.FINISHING:  # reached last light
            logger.debug(f"fmcar reached end of lights (car at light={light_index}/{len(self.lights.lights) - 1}), initiating finish trip")
            self.finish("end of lights")

        return
