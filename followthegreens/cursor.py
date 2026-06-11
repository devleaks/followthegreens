from __future__ import annotations
import os
from dataclasses import dataclass, fields
from enum import StrEnum
from datetime import datetime
from random import random

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import RABBIT_MODE, logger, MOVEMENT, INDICATOR, AIRCRAFT_MIN_SPEED, PLANE_MONITOR_DURATION
from .geo import Point, bearing, destination, distance, turn
from .lights import XPObject, LightType
from .route import Vehicle, SMOOTH_ROUTE, OnRoute, NOT_ON_ROUTE
from .aircraft import AIRCRAFT_STOPPED_SPEED


class CURSOR_STATUS(StrEnum):
    NEW = "NEW"  # cursor just created
    READY = "READY"  # cursor initialized, got starting position, cursor spawned, flight loop not running
    ACTIVE = "ACTIVE"  # flight loop running
    FINISHING = "FINISHING"  # initiated finish
    FINISHED = "FINISHED"  # finish finished, can be deleted
    DESTROYED = "DESTROYED"  # cursor destroyed
    DELETED = "DELETED"  # cursor deleted
    HOLD = "HOLD"  # cursor temporarily held
    LOAD_ROUTE = "LOAD_ROUTE"  # use of current set temporarily disabled while updating route, current and target positions


class HUD_TEXT(StrEnum):
    FOLLOW_ME = "FOLLOW CAR"
    SLOW = ">> S L O W <<"
    STOP = ">> S T O P <<"
    LEFT = "<<<  T U R N"
    RIGHT = "T U R N >>>"
    EMPTY = " "


# PROVIDED (X-CSL)
FM_CAR_PREFERENCE = "Preference"
FOLLOW_ME_CARS = {
    "Follow Me Truck": {"filename": "xcsl/FMC.obj", "indicator": True, "indicator_shift": [1.95, -0.70]},
    "Follow Me Car": {"filename": "xcsl/FMC2.obj", "indicator": True, "indicator_shift": [2.02, -1.8]},
    FM_CAR_PREFERENCE: {},  # MUST be empty
}


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


NO_STOP_AHEAD = -1
# AIRCRAFT_STOPPED_SPEED = 0.01  # m/s, under that speed, things are considered stopped, not moving.

SHOW_BRACKET = True  # debugging stuff


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

    max_speed: float = 18.0  # 18=60km/h, 25=90km/h, kind of a V-NE (never exceed speed)

    turn_radius: float = 22.0  # m
    brake_distance: float = 20.0  # m, could be a property function of speed

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
class Situation:
    """4 position with other information"""

    sr_route: tuple = tuple()  # current route for Cursor
    sr_position = OnRoute()  # position on sr_route equivalent to position

    sr_min = OnRoute()  # braket or buffer values from best distance range
    sr_max = OnRoute()  # sr_route should remain between those two values
    sr_stop = OnRoute(index=NOT_ON_ROUTE, distance=NO_STOP_AHEAD, name="no stop")  # sr_route cannot drive beyond this point, distance < 0 is sign there is no stop

    speed: float = 0.0

    @property
    def position(self) -> Point:
        return self.sr_position.point

    @property
    def sr_end(self) -> OnRoute:
        return OnRoute(index=len(self.sr_route) - 1, distance=0, route=self.sr_route, name=f"route end")

    @property
    def current_vertex(self) -> Point:
        return self.sr_route[self.sr_position.index]

    @property
    def heading(self) -> float:
        return self.sr_route[self.sr_position.index].getProp(SMOOTH_ROUTE.BEARING)

    def atEnd(self) -> bool:
        return self.sr_position.reached(target=self.sr_end)

    def hasStop(self) -> bool:
        return self.sr_stop.distance != NO_STOP_AHEAD

    def atStop(self) -> bool:
        return self.sr_position.reached(target=self.sr_stop)

    def clearStop(self):
        self.sr_stop = OnRoute(index=NOT_ON_ROUTE, distance=NO_STOP_AHEAD, name="no stop")  # sr_route cannot drive beyond this point, distance < 0 is sign there is no stop

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


@dataclass
class RoutePart:

    route: tuple | None = None  # pointer to route
    index: int = NOT_ON_ROUTE
    distance: float = 0.0  # distance "forward" from above index
    speed: float = -1.0  # no speed provided
    adjust: bool = True
    comment: str = ""

    def __str__(self):
        return self.comment


class Cursor(Vehicle):

    def __init__(self, detail: CursorType, ftg) -> None:
        Vehicle.__init__(self)
        self._ftg = ftg
        self.detail = detail

        self.cursor_object = CursorObject(detail.filename)
        self.cursor = XPObject(None, 0, 0, 0)

        self.show_bracket = SHOW_BRACKET and ftg.prefs.get("DEVELOPER_PREFERENCE_ONLY", False)
        self.cursor_min = XPObject(None, 0, 0, 0)
        self.cursor_max = XPObject(None, 0, 0, 0)
        self.cursor_mid = XPObject(None, 0, 0, 0)
        self.cursor_stop = XPObject(None, 0, 0, 0)

        self._indicator = INDICATOR.FOLLOW_ME
        self.hudText = INDICATOR.FOLLOW_ME.name
        self.hudExtra = ""
        self.indicator_object = None
        self.indicator_cursor = None
        if detail.indicator:
            indicator = CursorType(filename="indicator/indicator.obj", indicator_shift=detail.indicator_shift)
            self.indicator_object = CursorObject(indicator.filename)
            self.indicator_cursor = XPObject(None, 0, 0, 0)

        self._status = CURSOR_STATUS.NEW
        self.active = False  # accepts external requests if active, can be active but "on hold"

        self.route = ftg.route  # route that the cursor must follow
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
        self._msgs = {}
        self.last_dist_to_next_vertex = 0.0

        # monitoring
        self._last_acf_speed = 0.0
        self._acf_accel = 0.0
        self._last_call = 0
        self._last_call_max = 5.0
        self._last_call_std = PLANE_MONITOR_DURATION
        self._eor = False
        self._eod = False
        self._last_position = (self.current.sr_position, self.current.speed)
        self._paused = False
        self._pause_speed = 0.0
        self.current_distance = 0.0  # distance to acf
        self.current_bearing = -360.0  # acf -> fmcar
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
    def nextStop(self) -> int:
        return NO_STOP_AHEAD if self._ftg is None else self._ftg.flightLoop.nextStop

    @property
    def lastLit(self) -> int:
        return NO_STOP_AHEAD if self._ftg is None else self._ftg.flightLoop.lastLit

    @property
    def status(self) -> CURSOR_STATUS:
        return self._status

    @status.setter
    def status(self, status: CURSOR_STATUS):
        if status != self._status:
            self._status = status
            logger.info(f"{type(self).__name__} is now {status}")

    @property
    def paused(self) -> bool:
        # no FL means no action here
        return self._ftg.flightLoop.paused if self._ftg.flightLoop is not None else True

    def pause(self):
        self._pause_speed = self.aim_speed
        self._paused = True
        logger.debug("paused")
        self.setAimSpeed(speed=0.0, reason="pause")

    def unpause(self):
        self.setAimSpeed(speed=self._pause_speed, reason="unpause")
        self._paused = False
        logger.debug("unpaused")

    @property
    def indicator(self) -> int:
        return self._indicator.value

    @indicator.setter
    def indicator(self, indicator: INDICATOR):
        if indicator == INDICATOR.SLOW:
            self.setHudText(HUD_TEXT.SLOW.value)
            logger.info(f"Hud text is now {indicator.name}")
        elif indicator == INDICATOR.EMPTY:
            self.setHudText(HUD_TEXT.EMPTY.value)
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
            self.hudText = HUD_TEXT.STOP.value
        elif self._indicator == INDICATOR.LEFT:
            self.hudText = HUD_TEXT.LEFT.value
        elif self._indicator == INDICATOR.RIGHT:
            self.hudText = HUD_TEXT.RIGHT.value
        else:
            self.hudText = HUD_TEXT.FOLLOW_ME.value

    def setHudExtra(self, text: str = ""):
        self.hudExtra = text

    def getExtraLine(self) -> str:
        t = self.aircraft.brake_temperature()
        ts = "" if t == 0.0 else f" B {t: 5.1f}"
        return f"A {round(self.aircraft.speed(), 1): 4.1f} C {round(self.speed(), 1): 4.1f} D {round(self.current_distance, 1): 5.1f}" + ts

    def setAimSpeed(self, speed, reason: str = ""):
        if reason != "" and reason[0] != ",":
            reason = ", " + reason
        if self._aim_speed != speed:
            self.speed_reached = False
            logger.debug(f"new aim speed={sf(self.aim_speed, 'm/s')} -> {sf(speed, 'm/s')}{reason}")
            self._aim_speed = speed
        # else:
        #     logger.debug(f"aim speed already set at {speed}{reason}")

    def stop(self, reason: str = "stop"):
        self.setAimSpeed(speed=0.0, reason=reason)

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
        c = self.cursor is not None and self.cursor_object.has_obj
        f = self._ftg is not None and self.lights is not None
        return c and f

    @property
    def inited(self) -> bool:
        return self.route is not None and self.current is not None and self.current.sr_route is not None and len(self.current.sr_route) > 0

    def sMO(self, ident: int, message: str | None) -> bool | str:
        # Print debug message once for ident, reset with message=None
        if message is None:
            del self._msgs[ident]
            return False
        m = self._msgs.get(ident)
        d = m is None or m != message
        self._msgs[ident] = message
        return message if d else False

    # Creation, destruction
    #
    def init(self, route: tuple, position: Point, heading: float, speed: float = 0.0):
        # spawn cursor
        if self.inited:  # only init once
            return
        self.current.sr_route = route
        self.current.speed = speed
        self.setAimSpeed(speed=speed, reason="initial speed")
        self.current.sr_position = OnRoute(index=0, distance=0.0, route=self.current.sr_route, name="initial position")
        self.target.sr_position = OnRoute(index=len(self.current.sr_route) - 1, distance=0, route=self.current.sr_route, name="initial target position")
        self._last_position = (self.current.sr_position, self.current.speed)

        self.cursor.position = self.current.position  # initial position where will appear
        self.cursor.heading = self.current.heading
        self.cursor.place(lightType=self.cursor_object)
        self.cursor.on()

        if self.show_bracket:
            min_light = LightType.create(name="lmin.obj", color=(0, 1, 0), size=40, intensity=60, texture=3)  # green
            self.cursor_min.position = self.current.position  # initial position where will appear
            self.cursor_min.heading = self.current.heading
            self.cursor_min.place(lightType=LightType("min_light", min_light))
            self.cursor_min.on()
            max_light = LightType.create(name="lmax.obj", color=(1, 0, 1), size=40, intensity=40, texture=3)  # magenta
            self.cursor_max.position = self.current.position  # initial position where will appear
            self.cursor_max.heading = self.current.heading
            self.cursor_max.place(lightType=LightType("max_light", max_light))
            self.cursor_max.on()
            mid_light = LightType.create(name="lmid.obj", color=(0, 0, 1), size=40, intensity=40, texture=3)  # blue, ideal
            self.cursor_mid.position = self.current.position  # initial position where will appear
            self.cursor_mid.heading = self.current.heading
            self.cursor_mid.place(lightType=LightType("mid_light", mid_light))
            self.cursor_mid.on()
            stop_light = LightType.create(name="lstop.obj", color=(1, 0, 0), size=40, intensity=80, texture=3)  # red, stop
            self.cursor_stop.position = self.current.position  # initial position where will appear
            self.cursor_stop.heading = self.current.heading
            self.cursor_stop.place(lightType=LightType("stop_light", stop_light))
            logger.debug("added bracket visualizer")

        if self.indicator_cursor is not None:
            self.indicator_cursor.position = self.current.position  # initial position where will appear
            self.indicator_cursor.heading = self.current.heading
            self.indicator_cursor.place(lightType=self.indicator_object)
            self.indicator_cursor.on()
            logger.debug("added indicator")

        self.active = True
        self.status = CURSOR_STATUS.READY
        logger.debug(f"first route installed, speed={sf(self.current.speed, 'm/s')}, sr_position={self.current.sr_position}")  # , initialized pos={self.current.position.coords()}
        self.startFlightLoop()

    def destroy(self):
        self.stopFlightLoop()
        if self.indicator_cursor is not None:
            self.indicator_cursor.destroy()
            self.indicator_cursor = None
        if self.indicator_object is not None:
            del self.indicator_object
            self.indicator_object = None
        if self.show_bracket:
            if self.cursor_min is not None:
                self.cursor_min.destroy()
                self.cursor_min = None
            if self.cursor_max is not None:
                self.cursor_max.destroy()
                self.cursor_max = None
            if self.cursor_mid is not None:
                self.cursor_mid.destroy()
                self.cursor_mid = None
            if self.cursor_stop is not None:
                self.cursor_stop.destroy()
                self.cursor_stop = None
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
        return self.status == CURSOR_STATUS.DESTROYED

    # Movement execution
    #
    def startFlightLoop(self):
        if self.flightLoop is None and self.usable:
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
        #
        if self.lights is None:
            self.stop(reason="no lights")
            return 3.0
        # Slow loop for speed/distance adjustments
        self._last_call += elapsedSinceLastCall
        if not self._paused and self._last_call > self._last_call_max:  # self._last_call_max dynamically adjusted
            try:
                self._adjust(elapsedSinceLastCall=self._last_call)
                self._last_call = 0
            except:
                logger.error("issue in _adjust flight loop, retrying in next call", exc_info=True)
        # logger.debug(f"{round(elapsedSinceLastCall, 3)} => {round(self._last_call, 3)} / {round(self._last_call_max, 3)}")
        # Fast loop for cursor movement
        try:
            r = self._move(t=elapsedSinceLastCall)
            return r if type(r) in [int, float] else -1
        except:
            logger.error("issue in _move flight loop, retrying in 5 seconds", exc_info=True)
        return 5.0

    # Abrupt change or route, reset
    #
    def onRoute(self) -> bool:
        a = self.current.sr_route
        return self.route is not None and a is not None and a == self.route.smoothRoute

    def addRoute(self, route_part: RoutePart, tick: bool = False) -> bool:
        # Returns whether ticked
        self._future.put(route_part)
        t = " with target" if route_part.index >= 0 else ""
        u = ", ticking.." if tick else ""
        logger.debug(f"added new route {route_part}{t}{u}")
        if tick:
            r = self.loadRoute()
            logger.debug(f"..ticked ({r})")
            return r
        return False

    def loadRoute(self) -> bool:
        # Installs a route to travel automatically.
        # Target is set if present.
        # Start is adjustd on new route if requested to do so, otherwise route starts at starting position
        # Returns whether ticked
        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("probably changing route....cannot load route")
            return False

        if self._future.qsize() == 0:
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
            return False

        old_status = self.status
        self.status = CURSOR_STATUS.LOAD_ROUTE  # lock, prevents tick when changing routes

        try:
            # Change ROUTE
            old_route = self.current.sr_route
            route_part = self._future.get()
            self.current.sr_route = route_part.route
            logger.debug(f"new route loaded {route_part.comment} (adjust={route_part.adjust})")
            # need to adjust current pos...
            start = OnRoute(index=0, distance=0.0, route=self.current.sr_route)
            c = self.route.srClosestOnRoute(route=self.current.sr_route, point=old_route[-1]) if route_part.adjust else start
            self.current.sr_position = c
            logger.debug(f"new current position {self.current.sr_position}")
            # need to adjust target pos...
            if route_part.index >= 0:
                self.target.sr_position = OnRoute(index=route_part.index, distance=route_part.distance, route=self.current.sr_route, name="new target position (supplied)")
                logger.debug(f"new target set from route {self.target.sr_position}")
            else:
                self.target.sr_position = OnRoute(index=len(self.current.sr_route) - 1, distance=0, route=self.current.sr_route, name="new target position (default)")
                logger.debug(f"new target set to end of route {self.target.sr_position}")
            # set speed if requested
            if route_part.speed >= 0.0:
                self.setAimSpeed(speed=route_part.speed, reason="requirement from loaded route")
            else:
                logger.debug("no route speed requirement")
            if self.cursor_mid is not None:
                # target_pos = self.route.srDestinationRoute(route=self.current.sr_route, i=self.target.sr_position.index, dist=self.target.sr_position.distance)
                self.cursor_mid.move(lat=self.target.position.lat, lon=self.target.position.lon, hdg=0, elev=1.0)
        except:
            logger.error("error", exc_info=True)

        self.status = old_status
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

            old_status = self.status
            self.status = CURSOR_STATUS.HOLD  # lock, prevents tick when changing routes

            logger.debug("change route..")
            self.route = self._ftg.route
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
            ahead = self.aircraft.adjustAhead(rabbit_mode=self._ftg.flightLoop.rabbitMode)
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
            join_route = self.route.mkSmoothJoinRoute(start=self.current.position, end=light_ahead.position, heading=light_ahead.heading)
            # later: Add smooth turn from current heading to join_route
            self.resetRoute()
            self.addRoute(route_part=RoutePart(route=join_route, adjust=False, comment="join route on new route"))
            self.status = CURSOR_STATUS.ACTIVE  # for tick to work
            # start = OnRoute.fromLight(light=light_ahead, route=self.route.smoothRoute, name="start of new route")
            # self.addRoute(route_part=RoutePart(route=self.route.smoothRoute, start=start, comment="new route"), tick=True)  # starts the move right away)
            self.addRoute(
                route_part=RoutePart(route=self.route.smoothRoute, index=light_ahead.srIndex, distance=light_ahead.distFromsrIndex, comment="new route"), tick=True
            )  # starts the move right away)
            self._adjust(elapsedSinceLastCall=0.0, speed_type="fast")

            # The plugin currently providing traffic gave us a target with no ID.
            # Express range into min/max targets: [range] -> [sr_min, sr_max]
            drange = self.aircraft.adjustAheadRange(rabbit_mode=self.lights.rabbit_mode)
            self.updateBracket(light=light_ahead, drange=drange)
            logger.debug(f"bracket placed from light {closestLight} -> {light_index}")
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
            self.status = old_status
            logger.error("error while changing route", exc_info=True)

    def updateBracket(self, light, drange):
        DISTANCE_MARGIN = 10.0  # meters
        sr_cl = OnRoute.fromLight(light=light, route=self.current.sr_route, name=f"light position")
        d0 = drange[0] + DISTANCE_MARGIN
        self.current.sr_min = sr_cl.forward(dist=d0)
        self.current.sr_min.name = "bracket min"
        if self.show_bracket:
            self.cursor_min.move(lat=self.current.sr_min.point.lat, lon=self.current.sr_min.point.lon, hdg=0, elev=1.0)
        d1 = (d0 + DISTANCE_MARGIN) if drange[1] < (d0 + DISTANCE_MARGIN) else drange[1] - DISTANCE_MARGIN
        self.current.sr_max = sr_cl.forward(dist=d1)
        self.current.sr_max.name = "bracket max"
        if self.show_bracket:
            self.cursor_max.move(lat=self.current.sr_max.point.lat, lon=self.current.sr_max.point.lon, hdg=0, elev=1.0)
        logger.debug(f"bracket light={sr_cl}, [{self.current.sr_min}, {self.current.sr_max}]")

    # Information Vehicle interface
    #
    def position(self) -> tuple:
        p = self.position_point
        return (p.lat, p.lon)

    def position_point(self) -> Point:
        return self.current.position

    def speed(self) -> float:
        return self.current.speed

    def warningDistance(self, target: float = 0.0) -> float:
        return self.detail.indicator_warning_distance

    # Information external interface
    #
    def distance(self, position) -> float:
        # This is the bird's-eye view distance between the car and the position
        # Position can be anywhere.
        #
        # compute and uses bearing to see if car in front of acf or behind
        brng = bearing(self.current.position, position)
        if self.current_bearing != -360.0:
            self.uturned = abs(self.current_bearing - brng) > 160
        self.current_distance = distance(self.current.position, position)
        # logger.debug(f"d={sf(self.current_distance, 'm')}, before={sf(self.current_bearing, 'D')}, after={sf(brng, 'D')} {self.uturned}")
        self.current_bearing = brng
        return self.current_distance

    def at_rest(self) -> bool:
        return self.current.speed == 0  # please note "at_rest()" is different from "not moving()"

    def moving(self) -> bool:
        return self.current.speed > 0.1  # 10cm/sec is moving. please note "at_rest()" is different from "not moving()"

    def brakingDistance(self) -> float:
        # this is a good estimate of the distance necessary to stop the fmcar
        return 2 * self.current.speed

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
        turn_vertex = self.route.dtb_at[edge_idx]  # vertex.getProp("tobrake_index")
        turn = self.route.turns[turn_vertex]
        logger.log(8, f"after vertex {edge_idx}, d={sf(distance_on_edge, 'm')}, next turn at {sf(dist_to_next_turn, 'm')}, {sf(turn, 'D')}")
        if dist_to_next_turn < self.detail.indicator_warning_distance:  # and abs(turn) > TURN_LIMIT
            return INDICATOR.LEFT if turn < 0 else INDICATOR.RIGHT
        return INDICATOR.FOLLOW_ME

    # Stop bar handling from aircraft position
    #
    def mustStopSoon(self):
        # Aim is to block until canContinue()
        self.indicator = INDICATOR.STOP
        if not self.onRoute():
            logger.warning(f"got next stop {self.nextStop} and not on route")

        light = self.lights.lights[self.nextStop]
        self.current.sr_stop = OnRoute.fromLight(light=light, route=self.route.smoothRoute, name=f"stop at light {self.nextStop}")
        self.cursor_stop.move(lat=light.position.lat, lon=light.position.lon, hdg=0, elev=1.0)
        self.cursor_stop.on()

        # Remove braking distance
        tor = self.current.sr_stop.backward(dist=self.detail.brake_distance)
        dc = self.current.sr_stop.distanceTo(target=tor)
        # Must check that backup is NOT "before" current car position
        reached = self.current.sr_position.reached(tor)
        logger.debug(f"backup on route: {self.current.sr_stop} - {self.detail.brake_distance} -> {tor} (ok={reached}, dc={sf(dc, 'm')})")
        if not reached:
            self.current.sr_stop = tor  # self.detail.brake_distance before nextStop light position
        else:
            logger.debug("already beyond braking distance position")

        if self.nextStopReached():
            self.setAimSpeed(speed=0.0, reason=f"next stop {self.nextStop} reached")

    def mustStop(self) -> bool:
        return self.nextStop != NO_STOP_AHEAD

    def distanceToStop(self) -> bool:
        return self.current.sr_position.distanceTo(target=self.current.sr_stop)

    def canContinue(self):
        # Aim is to restart after mustStopSoon()
        if not self.mustStop():
            logger.debug("no stop, can continue")
            return
        # Need to add new future to restart without waiting for acf movement
        logger.debug("continuing after stop..")
        self.indicator = INDICATOR.FOLLOW_ME
        self.current.sr_stop = OnRoute(index=NOT_ON_ROUTE, distance=NO_STOP_AHEAD, name="no stop")
        self.cursor_stop.off()

        if self.lights is None:
            logger.warning("..no light, cannot continue")
            return
        closestLight, dist = self.lights.closest(self._ftg.aircraft.position())
        if closestLight is None:
            logger.debug("..no close light? cannot continue")
            return

        ahead = self._ftg.aircraft.adjustAhead(rabbit_mode=self._ftg.flightLoop.rabbitMode)
        light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead)
        self.target.sr_position = OnRoute.fromLight(light=light_ahead, route=self.route.smoothRoute, name="target can continue")
        self.cursor_mid.move(lat=light_ahead.position.lat, lon=light_ahead.position.lon, hdg=0, elev=1.0)
        self._adjust(elapsedSinceLastCall=0.0)
        logger.debug("..continuing")

    # Speed adjustment
    #
    def smoothConverge(self, s1: float, s2: float) -> float:
        # smoothly converge from s1 to s2, slower acceleration
        SMOOTH = 0.07 if s2 > s1 else 0.02
        return s1 + SMOOTH * (s2 - s1)

    def _adjustLocalSpeeds(self):
        # Internal ("fast") speed adjustment process, while car is moving
        # Car current.speed converges towards target.speed.
        # Target.speed converges towards aim_speed.
        # aim_speed has to be moving a bit at least, otherwise we converge towards speed=0.
        # ocs = self.current.speed  # orignal speeds, for debugging purpose
        # ots = self.target.speed
        # No decision or condition here, just adjust car speed
        if self.target.speed != self.aim_speed:
            self.target.speed = self.smoothConverge(self.target.speed, self.aim_speed)
        if self.current.speed != self.target.speed:
            self.current.speed = self.smoothConverge(self.current.speed, self.target.speed)
        if not self.speed_reached and abs(self.current.speed - self.aim_speed) < 0.1:
            self.speed_reached = True
            logger.debug(f"aim speed reached={sf(self.aim_speed, 'm/s')}")
            # logger.debug(
            #     f"aim speed ~reached={sf(self.aim_speed, 'm/s')}: curr={sf(ocs, 'm/s')}->{sf(self.current.speed, 'm/s')}, target={sf(ots, 'm/s')}->{sf(self.target.speed, 'm/s')}"
            # )

    # Local targets
    #
    def nextStopReached(self) -> bool:
        r = False if not self.current.hasStop() else self.current.atStop()
        # if r:
        #     logger.debug("next stop reached")
        return r

    def afterBracket(self) -> bool:
        r = self.current.sr_position.reached(self.current.sr_max)
        # if r:
        #     logger.debug("after bracket")
        return r

    def beforeBracket(self) -> bool:
        r = not self.current.sr_position.reached(self.current.sr_min)
        if r:
            logger.debug("before bracket")
        return r

    def targetReached(self) -> bool:
        r = False if not self.onRoute() else self.current.sr_position.reached(target=self.target.sr_position)
        # if r:
        #     logger.debug("target reached")
        return r

    def endOfRoute(self) -> bool:
        # end of route is end of current sr_route
        r = self.current.sr_position.reached(target=self.current.sr_end)
        if r and not self._eor:
            self._eor = True
            logger.debug("end of route")
        return r

    def destinationReached(self) -> bool:
        # Destination is the last point on the route
        r = self.current.sr_position.reached(target=OnRoute(index=len(self.route.smoothRoute) - 1, distance=0.0, route=self.route.smoothRoute, name="destination"))
        if r and not self._eod:
            self._eod = True
            logger.debug("destination reached")
        return r

    # Move
    #
    def nextPosition(self, t: float):
        if self.status == CURSOR_STATUS.LOAD_ROUTE:
            logger.debug("loading route .. cannot move")
            return self._last_position

        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("changing route .. cannot move")
            return self._last_position  # speed = 0.0 is wrong...

        if self.endOfRoute():
            msg = "end of route reached"
            if not self.loadRoute():
                if self.aim_speed == 0:
                    msg = msg + ", no more route"
                else:
                    self.setAimSpeed(speed=0.0, reason="no more route")
                if self.msg != msg:
                    self.msg = msg
                    logger.debug(self.msg)
                return self.current.sr_position, 0.0
            if self.msg != msg:
                self.msg = msg
                logger.debug(self.msg)

        if self.at_rest() and self.aim_speed == 0.0:  # must remain at rest
            if a := self.sMO(1, "at rest, must remain at rest"):
                logger.debug(a)
            return self.current.sr_position, 0.0
        # logger.debug(f"not at rest: {self.at_rest()}, {self.aim_speed}")
        # self.msg = ""

        if self.onRoute():
            if self.destinationReached():
                logger.debug("destination reached")  # need to continue on finishing route, do not change speed

            if self.current.sr_min.index != NOT_ON_ROUTE and self.current.sr_max.index != NOT_ON_ROUTE:
                if self.nextStopReached():
                    # logger.debug("next stop reached, must stop")
                    self.setAimSpeed(speed=0.0, reason="next stop reached")
                if self.at_rest():  # and we may move, it is time to restart moving?
                    if not self.beforeBracket():
                        logger.debug("at rest and after minimal distance, no need to move on")
                        # speed will be adjsuted in _adjust() since acf_dist < drange[0]
                        return self.current.sr_position, 0.0
                    else:  # no move yet
                        logger.debug("before minimal distance, need to move on")  # debug, remove
                elif self.afterBracket():
                    if self.aim_speed != 0.0:
                        if self.aim_speed < AIRCRAFT_MIN_SPEED:
                            self.setAimSpeed(speed=0.0, reason="reached maximal distance, need to stop")
                        else:
                            self.setAimSpeed(speed=round(0.6 * min(self.current.speed, self.aircraft.speed()), 1), reason="reached maximal distance, need to slow down")
                    # else:
                    #     logger.debug("reached bracket end but aim speed is already 0")  # debug, remove
            # else:
            #     logger.debug("on route, but no sr_min/sr_max yet, will check target")

        if self.targetReached():
            if self.onRoute():
                if self.current.sr_min.index == NOT_ON_ROUTE or self.current.sr_max.index == NOT_ON_ROUTE:
                    if self.current.speed > 0 and self.aim_speed != 0.0:
                        # logger.debug("on route, target reached, no sr_min/sr_max, matches aircraft speed")
                        self.setAimSpeed(speed=round(self.aircraft.speed(), 1), reason="on route, target reached, no sr_min/sr_max, matches aircraft speed")
            else:  # not onRoute
                if self.aim_speed > 0:
                    self.setAimSpeed(speed=0.0, reason="not on route, target reached, stopping")
                else:
                    if self.current.speed > 0:
                        logger.debug("not on route, target reached, slowing down to stop")
                    # else:
                    #     logger.debug("target reached, stopped")

        # self.cnt += 1
        # if self.cnt % 3 == 0:
        self._adjustLocalSpeeds()

        if self.indicator != INDICATOR.STOP:  # STOP/FOLLOW CAR is set in mustStopAt()/canContinue()
            self.indicator = self.nextTurnIndicator()  # compute turn indicator code for turns

        d = t * self.current.speed
        sr_position = self.current.sr_position.forward(dist=d)
        sr_position.name = "current position"
        # logger.debug(f"d={sf(self.distance(self.aircraft.position_point()), 'm')}, car={sf(self.current.speed, 'm/s')}, acf={sf(self.aircraft.speed(), 'm/s')}")
        # logger.debug(f"progress {idx} {sf(dist, 'm')}")
        self._last_position = (sr_position, self.current.speed)  # in case we need
        return sr_position, self.current.speed

    def _move(self, t: float) -> int | float:
        self.current.sr_position, self.current.speed = self.nextPosition(t=t)
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

        if not self.aircraft.moving() and self._ftg.move == MOVEMENT.DEPARTURE:
            # 1. Spawn the car next to (random) side of aircraft
            rnd = -1 + 2 * int(random() / 0.5)
            fs = self._ftg.route.beforeRoute()
            # spawn at spot randomly left or right of current aircraft position
            spawn = destination(fs.start, fs.bearing() + rnd * 90, SPAWN_SIDE_DISTANCE)  # use acf.heading()?
            ahead = self.aircraft.adjustAhead(rabbit_mode=self.lights.rabbit_mode)
            initbrgn, initdist, initdiff = self.lights.initial(self.aircraft.position(), self.aircraft.heading())
            logger.debug(f"first light ({initbrgn}, {initdist}, {initdiff})")
            if abs(initdiff) < 60:
                ahead = max(0, ahead - initdist)
                logger.debug(f"light is {initdist}m almost in front ({initdiff}), reduced ahead to {ahead}m")

            closestLight, dist = self.lights.closest(pos)
            if closestLight is None:
                logger.debug("no close light to start")
                closestLight = 0
            light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead)
            onr_la = OnRoute.fromLight(light=light_ahead, route=self.route.smoothRoute, name="light ahead")
            next_stop_light = self.lights.lights[nextStop]
            onr_ns = OnRoute.fromLight(light=next_stop_light, route=self.route.smoothRoute, name="next stop light")
            # if next_stop_light.srIndex < light_ahead.srIndex or (next_stop_light.srIndex == light_ahead.srIndex and next_stop_light.distFromsrIndex < light_ahead.distFromsrIndex):
            light = next_stop_light if onr_la.after(target=onr_ns) else light_ahead
            prev_li = nextStop if onr_la.after(target=onr_ns) else light_index
            if prev_li > 0:
                prev_li = prev_li - 1
            prev_light = self.lights.lights[prev_li]
            logger.debug(f"close light {closestLight} at {sf(dist, 'm')}, join at light {prev_li} (ahead {sf(ahead, 'm')})")
            join_sr_route = self.route.mkSmoothJoinRoute(start=spawn, end=prev_light.position, heading=light.heading)
            self.init(route=join_sr_route, position=spawn, heading=join_sr_route[0].getProp(SMOOTH_ROUTE.BEARING), speed=0.0)  # @todo always spawned at rest?
            if prev_li > 0:  # goes from prev_light to light
                self.addRoute(
                    route_part=RoutePart(route=self.route.smoothRoute, index=light.srIndex, distance=light.distFromsrIndex, comment="join on route, aircraft at rest")
                )  # otherwise, we are at start of route
            self.setAimSpeed(speed=self.detail.normal_speed, reason="just spawned, start moving, departure and aircraft not moving")
            return
        # If arrival or moving:
        # Aircraft is moving (example if new green request) or we are on arrival (or both)
        #
        # 1. Spawn the car next to (random) side of aircraft, half way "ahead" so that pilot can see the car on the side
        ahead = self.aircraft.adjustAhead(rabbit_mode=self.lights.rabbit_mode)
        rnd = 1 if (int(ahead) % 2) == 0 else -1
        spawn = destination(self._ftg.route.precise_start, self.aircraft.heading(), ahead / 2)  # ahead/2 ahead
        spawn = destination(spawn, self.aircraft.heading() + rnd * 90, SPAWN_SIDE_DISTANCE)
        closestLight, dist = self.lights.closest(pos)
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0
        # during join travel, aircraft will move forward, aircraft might still be running fast, we limit ot speed of car:
        self._adjust(elapsedSinceLastCall=0.0, speed_type="fast")
        acf_speed = self.aircraft.speed()
        acf_ahead = acf_speed * ROUTE_JOIN_TIME
        ahead_at_join = acf_ahead + ahead
        logger.debug(f"ahead_at_join={round(ahead_at_join, 1)}m = ahead={round(ahead,1)}m + acf_ahead={round(acf_ahead,1)}m")
        light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
        join_route = self.route.mkSmoothJoinRoute(start=spawn, end=light_ahead.position, heading=light_ahead.heading)
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
        self._adjust(elapsedSinceLastCall=0.0)
        self.addRoute(route_part=RoutePart(route=self.route.smoothRoute, speed=self.aim_speed, comment="route, aircraft moving or arrival"))
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

        end = self.lights.lights[-1].position  # last position of car is last light, not last point if route
        # end = self.route.smoothRoute(-1)
        # end = self.current.position
        # should may be go from last light to last point of route first? (which is threshold or start of runway)
        # Last position of car to "away"
        d1 = destination(src=end, brngDeg=hdg, d=LEAVE_DIST_AHEAD)
        # self.returnToRamp(final_position=d1)
        spd = self.detail.leave_speed
        hdg1 = hdg
        hdg = hdg + 90 * rnd
        td = LEAVE_DIST_AHEAD / spd
        logger.debug(f"carry forward {sf(LEAVE_DIST_AHEAD, 'm')} in {sf(td, 's')} heading {sf(hdg1, 'D')}, terminates heading {sf(hdg, 'D')}")
        leave_sr_route = self.route.mkSmoothJoinRoute(start=end, end=d1, heading=hdg)
        self.addRoute(route_part=RoutePart(route=leave_sr_route, speed=self.detail.normal_speed, comment="leaving route"))
        self.setAimSpeed(speed=self.detail.normal_speed, reason="finishing, start quitting")

        # "Away" to away and on the size
        final_dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        spd = self.detail.leave_speed
        td = LEAVE_DIST_SIDE / spd
        logger.debug(f"carry sideway {sf(LEAVE_DIST_SIDE, 'm')} in {sf(td, 's')} heading {sf(hdg, 'D')}")
        exit_sr_route = self.route.mkSmoothJoinRoute(start=d1, end=final_dest, heading=hdg)
        self.addRoute(route_part=RoutePart(route=exit_sr_route, speed=self.detail.normal_speed, comment="exit scenery"))
        self.active = False
        logger.debug("cursor inactive")  # i.e. does not respond to external messages anymore
        logger.debug(f"cursor finish programmed ({message})")

    def _adjust(self, elapsedSinceLastCall: float, speed_type: str = "normal"):
        # Assert situation (acf and car), collect information:
        #   - distance to stop
        #   - distance to next turn
        #   - determine bracket
        #   - distance/relation car-aircraft
        #   - rabbit advise (= trend)
        #   - aircraft speed trend (± acceleration)
        # Adjust positions: Ideal cursor position, acceptable position bracket
        #   - Car remain in bracket
        #   - Car remain sufficiently ahead of aircraft except if stop ahead
        # Adjust car speed
        # Advise on aircraft speed (through hud, car indicator)
        logger.debug("adjusting..")
        # "Slow" speed adjustment procedure, called by flightloop when aircraft has moved; sets aim_speed
        #
        default_speed = getattr(self.detail, speed_type + "_speed")

        # Not ready to move
        if not self.inited:  # we're on initial move
            logger.debug("not inited")
            self.setAimSpeed(speed=0.0, reason="not inited")
            return

        # IF car is off-route, finishing after the route, we do no modify its behavior
        if self.status in [CURSOR_STATUS.FINISHING, CURSOR_STATUS.FINISHED]:
            logger.debug("finishing or finished")
            self.setAimSpeed(speed=default_speed, reason="cursor finishing, no more speed adjustment, set default speed")
            return

        # If not on route, there is no control of the speed.
        # The car goes at its initial off-route speed.
        if not self.onRoute():
            # logger.debug("not on route")
            if self.current.speed < default_speed and self.aim_speed < default_speed:
                stopped = "stopped" if self.current.speed == 0 else "insufficient speed"
                logger.debug(f"not on route, {stopped}; set default speed {default_speed} (current aim speed {sf(self.aim_speed, 'm/s')})")
                self.setAimSpeed(speed=default_speed, reason=f"not on route, {stopped}; set default speed {default_speed}")
                return
            logger.debug(f"not on route, continue at same speed current={sf(self.current.speed, 'm/s')} -> aim={sf(self.aim_speed, 'm/s')}")
            return

        # Aircraft status from main loop:
        rabbit_mode = self.lights.rabbit_mode

        aircraft = self.aircraft
        if aircraft.stopped():
            if self.onRoute() and self.aim_speed > 0.0:
                self.setAimSpeed(speed=0.0, reason="on route and aircraft stopped")
            else:
                msg = "aircraft stopped, nothing to adjust"
                if self.msg != msg:
                    self.msg = msg
                    logger.debug(self.msg)
            return
        self.msg = ""

        acf_speed = aircraft.speed()
        ahead, drange = aircraft.adjustAhead(rabbit_mode=rabbit_mode, return_range=True)
        pos_pt = aircraft.position_point()
        acf_dist = self.distance(pos_pt)
        logger.debug(f"acf at {round(acf_dist, 1)}m")

        acf_move = acf_speed * elapsedSinceLastCall
        total_ahead = acf_move + ahead

        logger.debug(f"acf move {round(acf_move, 1)}m (loop={round(elapsedSinceLastCall, 3)}secs * speed={sf(acf_speed, 'm/s')}), accel={sf(self._acf_accel, 'm/s2')}")

        closestLight, dist = aircraft.closestLight(lights=self.lights)
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0
        closest_light = self.lights.lights[closestLight]
        logger.debug(f"aircraft closest light={closestLight} at {sf(dist, 'm')}, on edge index={closest_light.edgeIndex}, distance={round(closest_light.distFromEdgeStart, 1)}m")

        # The plugin currently providing traffic gave us a target with no ID.
        # Express range into min/max targets: [range] -> [sr_min, sr_max]
        self.updateBracket(light=closest_light, drange=drange)
        logger.debug(f"bracket placed from light {closestLight}")
        #
        # Aircraft too slow, cannot recommend speed from acf speed, returns standard speed
        if acf_speed < AIRCRAFT_MIN_SPEED and acf_dist > drange[0]:
            if self.aim_speed != 0.0:
                logger.debug("aircraft slow, car stopping")
                self.setAimSpeed(speed=0.0, reason=f"aircraft slow ({sf(acf_speed, 'm/s')}) and not too close ({sf(acf_dist, 'm')}), no move")
            else:
                logger.debug(f"aircraft slow or stopped ({sf(acf_speed, 'm/s')}), sufficient distance ({sf(acf_dist, 'm')} > {drange[0]})")
            return
        #
        # Adjust the car speed according to requests and acf speed

        # 1. status before adjustments
        logger.debug(
            f"d={sf(acf_dist, 'm')}, should be={sf(ahead, 'm')}, range={drange}, car={sf(self.current.speed, 'm/s')}, acf={sf(acf_speed, 'm/s')}, rabbit mode={rabbit_mode}.."
        )

        # 2. adjustment
        rabbit_factor = aircraft.RABBIT_FACTOR_SPEED[rabbit_mode]  # rabbit factor
        acc_factor = 1.0  # alternate factor
        work_msg = ""
        fmcar_speed = self.current.speed

        if self.mustStop():
            work_msg += ", must stop"
            self.setHudText(HUD_TEXT.STOP.value)
            dts = self.distanceToStop()
            bds = self.brakingDistance()
            if dts > bds:
                if fmcar_speed != 0.0:  # if not already stopped, move at slow speed towards stop
                    work_msg += ", slowing down to slow speed"
                    fmcar_speed = self.detail.slow_speed
                else:
                    work_msg += ", already stopped"
            else:
                fmcar_speed = 0.0

        if acf_dist > drange[1]:  # does the car need to slow down because too far?
            range_factor = 1
            if acf_dist != 0:  # if too far, we decelerate a lot, if not too far, we decelerate slowly
                range_factor = 1 - ((acf_dist - drange[1]) / acf_dist)
            acc_factor = min(rabbit_factor, range_factor, 0.8)
            work_msg = f"fmcar too far, need to slow down (factor={acc_factor}, rabbit_factor={round(rabbit_factor, 2)}, range_factor={round(range_factor, 2)}, {sf(acf_dist, 'm')} > {sf(drange[1], 'm')})"
            fmcar_speed = self.smoothConverge(self.current.speed, acf_speed * acc_factor)
        elif acf_dist < drange[0]:  # does the car need to accelerate because too close?
            work_msg = f"fmcar too close ({sf(acf_dist, 'm')} < {sf(drange[0], 'm')})"
            # does the car need to slow down because nearing a turn, stop, etc. (rabbit slower, slowest)
            if self.mustStop():
                work_msg += ", must stop"
                self.setHudText(HUD_TEXT.STOP.value)
                dts = self.distanceToStop()
                bds = self.brakingDistance()
                if dts > bds:
                    if fmcar_speed != 0.0:  # if not already stopped, move at slow speed towards stop
                        work_msg += ", slowing down"
                        fmcar_speed = self.detail.slow_speed
                    else:
                        work_msg += ", already stopped"
                else:
                    fmcar_speed = 0.0
                logger.debug(
                    f"car at {sf(self.current.speed, 'm/s')}, at {sf(dts, 'm')} from stop, needs {sf(bds, 'm')} to brake -> new speed={sf(fmcar_speed, 'm/s')} (acf_speed={sf(acf_speed, 'm/s')})"
                )
            elif rabbit_mode in [RABBIT_MODE.SLOWER, RABBIT_MODE.SLOWEST]:
                work_msg += f" but it is ok because we need to go slow (rabbit mode={rabbit_mode}, rabbit factor={rabbit_factor})"
                self.setHudText(HUD_TEXT.SLOW.value)
                fmcar_speed = acf_speed * rabbit_factor
            else:  # does the car either need to restart moving (from stopped), or accelerate because long straight line? (rabbit faster, fastest)
                RESTART_SPEED = self.detail.slow_speed
                target_speed = max(RESTART_SPEED, fmcar_speed, acf_speed)  # car might be at rest, need to get it moving, impose min speed
                range_factor = 1.0
                if drange[0] != 0:  # if far, we accelerate a lot, if not too far, we accelerate slowly
                    range_factor = 2 - (acf_dist / drange[0])
                acc_factor = max(rabbit_factor, range_factor)
                fmcar_speed = target_speed * acc_factor
                work_msg += f", need to accelerate, new start speed for estimate={round(target_speed, 1)} (factors: acc_factor={round(acc_factor, 2)}, range_factor={round(range_factor, 2)}, rabbit_factor={round(rabbit_factor, 2)})"
                if fmcar_speed > self.detail.normal_speed and fmcar_speed > acf_speed:  # no need to go too fast either
                    fmcar_speed = 1.2 * max(self.detail.normal_speed, acf_speed)
                    work_msg += f" max to {round(fmcar_speed, 1)}, "
        else:  # we are within range, we keepup with the aircraft but we might need to show something with rabbit...
            self.setHudText()  # reset, case it was slow
            work_msg = f"fmcar within range (rabbit factor={rabbit_factor})"
            if self.moving():
                if acf_dist < ahead:
                    acc_factor = 1.2
                    fmcar_speed = self.smoothConverge(self.current.speed, self.current.speed * acc_factor)
                    work_msg += ", fmcar should be more ahead, speeding up a bit"
                elif acf_dist > ahead:
                    acc_factor = 0.9
                    fmcar_speed = self.smoothConverge(self.current.speed, self.current.speed * acc_factor)
                    work_msg += ", fmcar should be less ahead, slowing down a bit"
                else:
                    fmcar_speed = self.smoothConverge(self.current.speed, self.current.speed * rabbit_factor)
            else:
                work_msg += ", fmcar at rest, may remain at rest"

        # 3. action (will also report adjustment)
        self.setAimSpeed(speed=fmcar_speed, reason=work_msg)

        # 4. adjust temporary target for car:
        # logger.debug(f"ahead={round(total_ahead, 1)}m = {round(ahead, 1)}m + acf move={round(acf_move, 1)}m")
        # At next iteration, acf will move acf_move, and fmcar need to be ahead
        # So at next iteration (t=now + iterTime), car need to be (acf_move+ahead) in front
        if acf_move <= 0.0:
            logger.debug("no aircraft movment")
            return
        logger.debug(f"should move {round(total_ahead, 1)}m ahead of aircraft (ahead={round(ahead, 1)}m + acf={round(acf_move, 1)}m)")
        light_ahead, light_index, dist_left = self.lights.lightAhead(index_from=closestLight, ahead=total_ahead)
        logger.debug(f"should move to light={light_index} on edge index={light_ahead.edgeIndex}, distance={round(light_ahead.distFromEdgeStart, 1)}m")
        if self.mustStop() and light_index > self.nextStop and self.lights.mustStopAt(nextStop=self.nextStop):
            logger.debug(f"must stop at nextStop={self.nextStop} {self.lights.mustStopAt(nextStop=self.nextStop)}")
            logger.debug(
                f"car is at light={self.fmc_light_progress}, cannot move to light={light_index} because it is after stop at light {self.nextStop} that is not cleared, need to clear stop before (note: indicator={self.indicator})"
            )
            logger.debug(f"next stop at index={self.nextStop} is {'cleared' if self.lights.stopCleared(self.nextStop) else 'not cleared'}")
            # logger.debug("..not moved")
            if self.fmc_light_progress < self.nextStop:
                light_at_stop = self.lights.lights[self.nextStop]
                self.target.sr_position = OnRoute.fromLight(light=light_at_stop, route=self.route.smoothRoute, name="target with stop")
                self.cursor_mid.move(lat=light_at_stop.position.lat, lon=light_at_stop.position.lon, hdg=0, elev=1.0)
                self.fmc_light_progress = self.nextStop
                logger.debug(f"..moved to next stop (car at light {self.fmc_light_progress}/{len(self.lights.lights) - 1})")
            else:
                logger.debug(f"..not moved: car is at light={self.fmc_light_progress}/{len(self.lights.lights) - 1}, next  stop at light {self.nextStop}")
        else:
            # logger.debug(f"light ahead={light_index} on edge index={light_ahead.edgeIndex}, distance from edge={round(light_ahead.distFromEdgeStart, 1)}m")
            # logger.debug(f"future_index to i={light_ahead.edgeIndex}, d={round(light_ahead.distFromEdgeStart,1)}m, spd={round(fmc_speed,1)}m/s")
            self.target.sr_position = OnRoute.fromLight(light=light_ahead, route=self.route.smoothRoute, name="target no stop")
            self.cursor_mid.move(lat=light_ahead.position.lat, lon=light_ahead.position.lon, hdg=0, elev=1.0)
            self.fmc_light_progress = light_index
            logger.debug(f"..moved  (car at light {self.fmc_light_progress}/{len(self.lights.lights) - 1})")
        # Checks for end of lights/end of trip
        if self.fmc_light_progress == (len(self.lights.lights) - 1) and self.status != CURSOR_STATUS.FINISHING:  # reached last light
            logger.debug(f"fmcar reached end of lights (car at light={light_index}/{len(self.lights.lights) - 1}), initiating finish trip")
            self.finish("end of lights")

        try:
            self._last_call_max = self._adjustedIter(acf_speed=acf_speed)
        except:
            logger.error("issue in _adjustedIter", exc_info=True)
            self._last_call_max = PLANE_MONITOR_DURATION

        logger.debug("..adjusted")

    def _adjustedIter(self, acf_speed: float) -> float:
        # If aircraft move fast, we check/update its status more often
        FASTEST_PLANE_MONITOR_DURATION = 0.8  # fastest "frequency" in secs.
        if acf_speed is None or acf_speed < AIRCRAFT_STOPPED_SPEED:
            # logger.debug(f"stopped, iter {self.nextIter}s")
            return PLANE_MONITOR_DURATION

        if self.lights.rabbit_mode == RABBIT_MODE.SLOWEST:  # probably closing stop or turn, must monitor/adjust speed frequently
            if self._last_call_max != FASTEST_PLANE_MONITOR_DURATION:
                logger.debug(f"close to stop, iter fast {FASTEST_PLANE_MONITOR_DURATION}s")
            return FASTEST_PLANE_MONITOR_DURATION

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
                if j != self._last_call_max:
                    logger.debug(f"acf speed {round(acf_speed, 1)}m/s), iter set to {j}s")
                return j
            i = i + 1
        logger.debug(f"acf speed {round(acf_speed, 1)}m/s), regular iter {PLANE_MONITOR_DURATION}s")
        return PLANE_MONITOR_DURATION


#
