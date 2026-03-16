import os
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum

from .oned import eq2

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import logger, MOVEMENT, INDICATOR
from .geo import Point, Line, destination, distance
from .lightstring import XPObject


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
    return round(t - t0, 3)


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

    max_speed: float = 18.0

    turn_radius: float = 25.0  # m

    acceleration: float = 1.0  # m/s^2, same deceleration
    deceleration: float = -1.0  # m/s^2, same deceleration

    indicator_warning_distance: float = 50.0  # m

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

    position: Point | None = None
    time: float = ts()
    heading: float = 0.0
    speed: float = 0.0

    route_index: int = NOT_ON_ROUTE  # index of edge of position on sharp route, -1 if not on sharp route

    vertex: Point | None = None  # starting vertex of above edge index
    distance_on_edge: float = 0.0  # distance forward of above vertex to position

    end: tuple = (NOT_ON_ROUTE, 0)  # forced position on sharp route
    # position is route_index = end[0], distance_on_edge=end[1]

    sr_route: tuple = tuple()  # smoothRoute, either a straightRoute which is NOT ON sharp route or smoothRoute which is on sharp route

    sr_position = OnRoute()  # position on sr_route equivalent to position
    sr_end = OnRoute()  # position on sr_route equivalent to forced end

    last_time: float = 0  # time before update, to measure delta, could store last increment instead
    last_inc_time: float = 0  # store last increment instead
    comment: str = ""

    path_length: float = 0.0
    path_time: float = 0.0

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

    SPAWN_SIDE_DISTANCE = 20

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
        self.start = Situation()  # when new route segment started

        # working var for interpolation
        self.refcursor = "FtG:cursor"
        self.flightLoop = None
        self.nextIter = -1
        self._qin = 0
        self._qout = 0
        self.cnt = -1
        self._total_distance = 0
        self._timer = None
        self._set_current = False
        self.msg = ""
        self.last_dist_to_next_vertex = 0.0
        self._acf_speed = 0.0
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
    def init(self, position: Point, heading: float, speed: float = 0.0):
        # spawn cursor
        if self.inited:  # only init once
            return
        self.current.position = Point(lat=position.lat, lon=position.lon)  # take a local copy of the supplied position
        self.current.heading = heading
        self.current.speed = speed
        # Enforce speed for now
        if self.current.speed <= 0.1:
            self.current.speed = self.detail.normal_speed
            logger.warning(f"set current speed {round(self.current.speed, 1)}m/s")
        self.current.time = ts()
        self.current.comment = "init"
        self.current.route_index = NOT_ON_ROUTE  # we start not on route

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
        logger.debug(f"initialized at {st(self.current.time)}, pos={self.current.position.coords()}, speed={sf(self.current.speed, 'm/s')}, sr_position={self.current.sr_position}")
        logger.debug("cursor active")
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

    def canDelete(self) -> bool:
        if self.status != CURSOR_STATUS.FINISHED:
            logger.debug("not finished, cannot delete")
            return False
        self.destroy()
        return True

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
            r = self.move(t=elapsedSinceLastCall)
            return r if type(r) in [int, float] else -1
        except:
            logger.error("error", exc_info=True)
        return 5.0

    # Information external interface
    #
    def distance(self, position) -> float:
        return distance(self.current.position, position)

    def set_aircraft_speed(self, speed: float):
        self._acf_speed = speed

    def faster(self, s: float) -> float:
        return max(s + 2.0, s * 1.2)

    def speed(self) -> float:
        return self.current.speed

    def canContinue(self):
        if self.indicator == INDICATOR.STOP:
            self.indicator = INDICATOR.FOLLOW_ME

    def adjustedSpeed(self, speed_type: str = "normal", reference: float = 0.0) -> float:
        # reference is a possibility to inout acf speed (i.e. the thing following fmcar)
        if reference < 3:  # almost at rest
            if speed_type == "slow":
                logger.debug(f"recommanded speed {sf(self.detail.slow_speed, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
                return self.detail.slow_speed
            elif speed_type == "fast":
                logger.debug(f"recommanded speed {sf(self.detail.fast_speed, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
                return self.detail.fast_speed
            else:
                logger.debug(f"recommanded speed {sf(self.detail.normal_speed, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
                return self.detail.normal_speed
        if speed_type == "fast":
            s = reference + self.detail.fast_speed
            logger.debug(f"recommanded speed {sf(s, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
            return min(s, self.detail.max_speed)
        if speed_type == "slow":
            s = reference + self.detail.slow_speed
            logger.debug(f"recommanded speed {sf(s, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
            return min(s, self.detail.max_speed)
        # a little bit faster than reference if provided
        s = (1.05 * reference) if reference > 0.0 else self.detail.normal_speed
        logger.debug(f"recommanded speed {sf(s, 'm/s')} ({speed_type}, {sf(reference, 'm/s')})")
        return min(s, self.detail.max_speed)

    # Abrupt change or route, reset
    #
    def resetRoute(self):
        # They won't be any valid route anymore.
        # We have to stop the future
        logger.log(8, "reseting cursor planned route..")
        self._future.clear()
        logger.log(8, "..reset")

    def changeRoute(self, ftg):
        if self.status != CURSOR_STATUS.ACTIVE:
            logger.warning(f"change route: Cursor is not active (is {self.status})")
            return
        try:
            self.status = CURSOR_STATUS.HOLD  # lock, prevents tick when changing routes
            logger.debug("change route..")
            if self.route is not None:
                self.resetRoute()
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
            acf_ahead = min(acf_speed, self.detail.fast_speed) * join_time
            ahead_at_join = acf_ahead + ahead
            light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
            join_route = Line(start=self.current.position, end=light_ahead.position)
            initial_speed = join_route.length() / join_time
            self.current.speed = initial_speed
            self.current.heading = join_route.bearing()
            dt = ts() + join_time
            # we will move the car well ahead, the car should not backup
            # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
            light_progress = closestLight + int(acf_ahead / ftg.lights.distance_between_green_lights)
            logger.debug(
                f"..move on route at {sf(ahead_at_join, 'm')} ahead, heading={round(join_route.bearing(), 0)}, in {round(join_time, 1)}s (aircraft will be at light index {light_progress}).."
            )
            # we move the car in front of acf, and progress at same speed as acf.
            self.status = CURSOR_STATUS.ACTIVE
            self.future(
                position=join_route.end,
                hdg=light_ahead.heading,
                speed=acf_speed,
                t=dt,
                edge=NOT_ON_ROUTE,  # not on route
                tick=True,
                text="go on route ahead of aircraft after new route",
                end=(light_ahead.edgeIndex, light_ahead.distFromEdgeStart),
            )
            # finally, we have to tell future_index() where car is when it join route
            # so that when move() catches up with future_index() it will start from there
            # (after above future)
            logger.debug("..route changed, already taxiing")
        except:
            logger.error("error", exc_info=True)

    # Itinerary: Next positions (as requested from client)
    #
    def future(self, position: Point, hdg: float, speed: float, t: float, edge: int = NOT_ON_ROUTE, tick: bool = False, text: str = "", end: tuple = (NOT_ON_ROUTE, 0)):
        # Itinerary: Next position and desired approximate time of arrival at that position.
        # If the position is on route, edge points at the edge on which we currently are.
        # If edge is -1, we are NOT on self.route and we travel to some position
        # On a future() we always travel in a straight line, from the last position towards the target_position
        #
        if not self.active:
            logger.debug("cursor not active")
            return
        if self.status == CURSOR_STATUS.FINISHED:
            logger.debug("cursor finished, does not accept future position")
            return
        logger.debug("adding future..")
        f = Situation(position=position, heading=hdg, speed=speed, time=t, route_index=edge, comment=text, end=end)
        #
        # immediately convert route data into smooth route data
        #
        if f.end[0] >= 0:
            f.sr_end = OnRoute(*self.route.srEquiv(i=f.end[0], dist=f.end[1]))
            logger.debug(f"srEquiv forced end {f.end} -> {f.sr_end}")
        if edge >= 0:  # if we are on sharp route
            if f.end[0] >= 0:  # if there is a "forced end"
                f.route_index = f.end[0]
                f.distance_on_edge = f.end[1]
                f.vertex = self.route.vertices[f.route_index]
                f.sr_position = f.sr_end
                logger.debug(
                    f"srEquiv at route end {f.end} -> {f.sr_position} (d={sf(distance(position, self.route.srDestination(f.sr_position.index, f.sr_position.distance)), 'm')})"
                )
            else:  # no forced end, just a move on the edge
                # f.route_index = edge
                f.vertex = self.route.vertices[edge]
                f.distance_on_edge = distance(f.vertex, position)
                f.sr_position = OnRoute(*self.route.srEquiv(i=f.route_index, dist=f.distance_on_edge))
                logger.debug(
                    f"srEquiv on route {f.route_index},{sf(f.distance_on_edge, 'm')} -> {f.sr_position} (d={sf(distance(position, self.route.srDestination(f.sr_position.index, f.sr_position.distance)), 'm')})"
                )
        # else:  If not on sharp route, we will compute the target position in _mkPathToTarget()
        if f.speed <= 0.1:
            f.speed = self.detail.normal_speed
            logger.warning(f"temporarily adjusted future speed to {sf(f.speed, 'm/s')}")

        self._future.put(f)
        self._qin += 1
        logger.debug(f"..added future #{self._qin} (q.len={self._future.qsize()}): {f}{', ticking immediately..' if tick else ''}")
        if tick:
            ignore = self._tick()
            if ignore:
                logger.debug("..ticked immediately")

    def future_index(self, edge: int, dist: float, speed: float, t: float):
        # future_index() always travel on a route.
        # we assume WE ARE on a route curr_dist from start of curr_edge.
        # we will move on the route to dist from start of edge.
        # we will TERMINATE at speed, heading fixed by edge heading.
        # This routine creates a set of future() to satisfy the above.
        #
        if not self.active:
            logger.debug("cursor not active")
            return
        last_pos = self._future.last()
        txt = "(target)"
        if last_pos is None:
            last_pos = self.target
            txt = "(last)"
        logger.log(8, f"new future starts at last future: {last_pos} {txt}")

        last_route_index = last_pos.route_index
        last_distance_on_edge = last_pos.distance_on_edge
        if last_pos.end[0] >= 0:
            last_route_index = last_pos.end[0]
            last_distance_on_edge = last_pos.end[1]
        logger.log(8, f"last route index: {last_route_index}, last distance on edge: {round(last_distance_on_edge, 1)}m")

        # convert trip on the route into "future()" segements:
        if edge < last_route_index:
            logger.debug(f"cannot backup edges ({edge} < {last_route_index})")
            return
        logger.log(8, f"currently on edge {last_route_index} at {round(last_distance_on_edge, 1)}m, need to go on edge {edge} at {round(dist, 1)}m")
        logger.log(8, f"currently at speed {last_pos.speed}m/s, will terminate at {round(speed, 1)}m/s")
        if edge == last_route_index:  # remains on same edge
            if dist > last_distance_on_edge:
                dest = self.route.on_edge(edge, dist)  # destination(self.route.vertices[edge], self.route.edges_orient[edge], dist)
                hdg = self.route.edges_orient[edge]
                self.future(position=dest, hdg=hdg, speed=speed, t=t, edge=edge, text=f"go further on edge (d={sf(dist, 'm')})")
                logger.log(8, f"progress on edge {edge} from {round(last_distance_on_edge, 1)}m to {round(dist, 1)}m, distance adjusted")
            else:
                logger.log(8, f"no progress on edge {edge}, ({round(dist, 1)}m <= {round(last_distance_on_edge, 1)}m)")
            return

        vertices = self.route.vertices

        local_speed = last_pos.speed
        if local_speed == 0:
            if speed > 0:
                local_speed = speed
            else:
                local_speed = self.detail.normal_speed
                logger.log(8, f"no speed for future, forced normal local speed {round(local_speed, 1)}m/s")
        logger.debug(f"speeds: requested at end {speed}, last_pos={last_pos.speed}, local={local_speed}m/s")

        # first quick precompute
        e = self.route.edges[last_route_index]
        total_dist = e.cost - last_distance_on_edge  # finish current edge
        last_index = last_route_index + 1
        # travel entire next edges
        while last_index < edge and last_index < (len(vertices) - 1):
            e = self.route.edges[last_index]
            total_dist += e.cost  # add intermediate edges
            last_index = last_index + 1
        last_index = last_index - 1
        total_dist += dist  # on "target" edge
        total_time = total_dist / local_speed
        logger.log(8, f"total distance to travel {round(total_dist, 1)}m at {round(local_speed, 1)}m/s -> total travel time ={round(total_time, 1)}s, last_edge={last_index}")

        start_time = t - total_time

        # travel to end of current edge
        control_dist = 0
        control_time = 0
        e = self.route.edges[last_route_index]
        d = e.cost - last_distance_on_edge
        control_dist += d
        logger.log(8, f"edge {last_route_index} length={round(e.cost, 1)}m, heading={round(e.bearing(), 0)}, start_time={start_time}, end_time={t}")
        tt = d / local_speed
        control_time += tt
        start_time += tt
        hdg = self.route.edges_orient[min(last_route_index + 1, len(self.route.edges) - 1)]
        txt = f"{round(d, 1)}m to end of current edge {last_route_index}"
        if last_route_index < 0:
            txt = f"{round(d, 1)}m to end of segment (not on route)"

        # RESET
        last_index = last_route_index + 1

        self.future(position=vertices[last_route_index + 1], hdg=hdg, speed=local_speed, t=start_time, edge=last_route_index, text=txt, end=(last_index, 0))
        # logger.log(8, f"progress {round(d, 1)}m on edge {last_route_index} to end of edge in {round(tt, 1)}s")

        # travel entire next edges
        while last_index < edge and last_index < (len(self.route.edges)):
            e = self.route.edges[last_index]
            control_dist += e.cost
            tt = e.cost / local_speed
            control_time += tt
            start_time += tt
            # route to edge
            hdg = self.route.edges_orient[min(last_index + 1, len(self.route.edges) - 1)]
            # s = speed if last_index == last_edge else local_speed  # carry on as last speed
            self.future(
                position=vertices[last_index + 1],
                hdg=hdg,
                speed=local_speed,
                t=start_time,
                edge=last_index,
                text=f"{round(e.cost, 1)}m to end of edge {last_index}",
                end=(last_index + 1, 0),
            )
            logger.log(8, f"progress on edge {last_index} (whole length {round(e.cost, 1)}m, in {round(tt, 1)}s)")
            last_index = last_index + 1

        # travel on new current edge
        newpos = self.route.on_edge(edge, dist)
        self.future(position=newpos, hdg=self.route.edges_orient[edge], speed=speed, t=t, edge=edge, text=f"{round(dist, 1)}m on edge {edge}")
        last_index = edge
        control_dist += dist
        tt = dist / local_speed
        control_time += tt
        start_time += tt
        logger.log(8, f"progress on edge {edge} (length {round(dist, 1)}m, in {round(tt, 1)}s)")
        logger.log(8, f"control distance travelled {round(control_dist, 1)}m, in {round(control_time, 1)}s")

    # Movement: Computation of next position
    #
    # Places next straight line to walk (if any)
    #
    def _tick(self) -> bool:
        # returns whether it ticked, new target set, and path constructed
        if self.status == CURSOR_STATUS.HOLD:
            logger.debug("cursor temporarily on hold, cannot tick")
            return False
        if self._future.empty():
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
            return False
        f = self._future.get()
        if f is not None:
            self._qout += 1
            logger.debug(f"ticking future #{self._qout} (q.len={self._future.qsize()}) at {st(self.current.time)}: {f}..")  #
            if self.set_target(f):
                self._mkPathToTarget()
                self._set_current = False
                logger.debug("..ticked")
                return True
            logger.debug("..not ticked")
        return False

    def set_start(self) -> bool:
        # copy start values from current at start of new future()
        self.start.time = self.current.time
        self.start.position = self.current.position
        self.start.heading = self.current.heading
        self.start.speed = self.current.speed
        self.start.comment = self.current.comment
        self.start.vertex = self.current.vertex
        self.start.sr_end = self.current.sr_end
        self.start.sr_position = self.current.sr_position
        self.start.sr_route = self.current.sr_route
        logger.debug(f"start set from current at {st(self.current.time)}")
        return True

    def set_current(self) -> bool:
        # adjust current from target depending on "cases" (on route/off route, etc.)
        if self._set_current:
            return False
        logger.debug(f"setting current.. {self.current}")
        logger.debug(f"..from target {self.target}..")

        # self.current.position = self.target.position
        logger.log(8, f"current position vs target before adjustments {sf(distance(self.current.position, self.target.position), 'm')}")

        # 1. Where are we coming from (current is at target, but still holds info from where it is coming)
        if self.current.route_index == NOT_ON_ROUTE:
            logger.log(8, "control: we were off route")
            # 1.2. Where are we going to
            if self.target.route_index != NOT_ON_ROUTE or self.target.end[0] >= 0:
                logger.log(8, "control: we go on route")
                if self.target.end[0] >= 0:  # target is on route, there is a forced end
                    self.current.route_index = self.target.end[0]
                    self.current.vertex = self.route.vertices[self.target.end[0]]
                    # we are a little bit further on the route
                    self.current.distance_on_edge = distance(self.current.vertex, self.current.position)
                    self.current.sr_position = OnRoute(*self.route.srEquiv(i=self.current.route_index, dist=self.current.distance_on_edge))
                    logger.debug(f"adjustments because end of turn reached {sf(self.current.distance_on_edge, 'm')}")
                    # self.current.sr_position = self.target.sr_end  # should be the case...
                    logger.log(8, f"control: {sf(distance(self.current.position, self.route.srDestination(self.current.route_index, self.current.distance_on_edge)), 'm')}")
                    logger.debug(
                        f"set current from forced end on route {self.target.end}: {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m from edge start"
                    )
                else:
                    self.current.route_index = self.target.route_index
                    self.current.distance_on_edge = self.target.distance_on_edge
                    self.current.vertex = self.target.vertex
                    logger.log(8, f"control: {sf(distance(self.current.position, self.route.srDestination(self.target.end[0], self.target.end[1])), 'm')}")
                    logger.debug(f"set current from position: {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m")
            else:
                logger.log(8, "control: we go off route")
                self.current.sr_position = OnRoute(index=0, distance=0)  # we are at the start of that straightRoute
                # self.current.vertex = self.target.vertex  # ?
                # self.current.distance_on_edge = 0  # ?
                logger.debug("set current position to start of new smooth route")
        else:
            logger.log(8, "control: we were on route")
            # 2. Where are we going to
            if self.target.route_index != NOT_ON_ROUTE or self.target.end[0] >= 0:
                logger.log(8, "control: we go on route")
                if self.target.end[0] >= 0:  # target is on route, there is a forced end
                    self.current.route_index = self.target.end[0]
                    self.current.vertex = self.route.vertices[self.target.end[0]]
                    self.current.distance_on_edge = self.target.end[1]
                    self.current.sr_position = OnRoute(*self.route.srEquiv(i=self.current.route_index, dist=self.current.distance_on_edge))
                    # self.current.sr_position = self.target.sr_end  # should be the case...
                    logger.log(8, f"control: {sf(distance(self.current.position, self.route.srDestination(self.target.end[0], self.target.end[1])), 'm')}")
                    logger.debug(
                        f"set current from forced end on route {self.target.end}: {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m from edge start"
                    )
                else:
                    self.current.route_index = self.target.route_index
                    self.current.distance_on_edge = self.target.distance_on_edge
                    self.current.vertex = self.target.vertex
                    self.current.sr_position = OnRoute(*self.route.srEquiv(i=self.current.route_index, dist=self.current.distance_on_edge))
                    logger.log(8, f"control: {sf(distance(self.current.position, self.route.srDestination(self.current.route_index, self.current.distance_on_edge)), 'm')}")
                    logger.debug(f"set current from position: {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m")
            else:
                logger.log(8, "control: we go off route")
                self.current.sr_position = OnRoute(index=0, distance=0)  # we are at the start of that straightRoute
                # self.current.vertex = self.target.vertex  # ?
                # self.current.distance_on_edge = 0  # ?
                logger.debug("set current position to start of new smooth route")

        self.current.end = self.target.end
        self.current.sr_end = self.target.sr_end
        logger.debug(f"set current sr_end={self.current.sr_end} from target")
        # self.current.heading = self.target.heading
        self.current.speed = self.target.speed
        self.current.comment = self.target.comment
        self._set_current = True
        logger.log(8, f"current position vs target after adjustments {sf(distance(self.current.position, self.target.position), 'm')}")
        logger.debug(f"..current set from target reached {self.current}")
        return True

    def set_target(self, target: Situation) -> bool:
        # set new target from future()
        logger.log(8, f"current {self.current.comment}")
        logger.debug(f"setting target {target.comment}..")
        # logger.debug(f"target sr_position {target.sr_end}")
        # logger.debug(f"target sr_end {target.sr_end}")
        if self.current.route_index < 0:  # direct route to target
            self.set_start()
            self.target = target
            logger.debug("..target set from future (current not on route)")
            return True
        if target.route_index < 0:
            self.set_start()
            self.target = target
            logger.debug("..target set from future (target not on route)")
            return True
        # we are on route
        if self.current.route_index > target.route_index:
            logger.debug(f"..cannot backup edge ({target.route_index} < {self.current.route_index}), target not set")
            return False
        if self.current.route_index == target.route_index and self.current.distance_on_edge > target.distance_on_edge:
            logger.debug(f"..cannot backup on current edge ({round(target.distance_on_edge, 1)}m < {round(self.current.distance_on_edge, 1)}m), target not set")
            return False
        if self.current.sr_position.index >= target.sr_position.index and self.current.sr_position.distance >= target.sr_position.distance:
            logger.debug("..cannot backup on smooth edge, target not set")
            return False
        self.set_start()
        self.target = target
        logger.debug("..target set from future (on route)")
        return True

    def _mkPathToTarget(self):
        logger.debug("building path..")
        current = self.current
        target = self.target
        # CASE 1: WE ARE NOT ON THE ROUTE:
        # If edge is -1, we are NOT on self.route and we travel from the current position which is not on route
        # to a position on route in a straight line. The straight line us first smmothed to terminate with a turn to align on the route.
        if self.current.route_index < 0:  # not on route
            self.current.vertex = self.current.position
            self.current.distance_on_edge = 0
            # logger.debug(f"direct path, need to travel {round(self.path_length, 1)}m in {round(self.path_time, 1)}")
            current.sr_route = self.route.srStraightRoute(start=current.position, end=target.position, heading=target.heading)
            target.sr_position = OnRoute(len(current.sr_route) - 2, current.sr_route[-1].getProp("srDistance"))
            # or target.sr_position = OnRoute(len(target.sr_route)-1, 0)
            logger.debug(f"not on route, srEquiv direct route on custom smooth route -> {target.sr_position} (end={target.sr_end})")
        # CASE 2: WE ARE ON THE ROUTE
        # If the position is on route, edge points at the edge on which we currently are sitting.
        # The position is converted into a pair (vertex index, distance from that vertex) on the smoothed route.
        else:
            if self.target.route_index < 0:  # going off-route
                current.sr_route = self.route.srStraightRoute(start=current.position, end=target.position, heading=target.heading)
                self.start.sr_position = OnRoute(index=0, distance=0.0)
                current.sr_position = OnRoute(index=0, distance=0.0)  # we are at the start of the straightRoute
                target.sr_position = OnRoute(index=len(current.sr_route) - 1, distance=0.0)  # end of straightRoute
                logger.debug(f"leaving route, srEquiv direct route on custom smooth route -> {target.sr_position} (end={target.sr_end})")
            else:
                current.sr_route = self.route.smoothRoute
                logger.debug(f"route on smooth route from {current.sr_position} to target {target.sr_position} (end={target.sr_end})")

        path_length = self.route.srDistanceRoute(
            route=current.sr_route, i1=current.sr_position.index, dist1=current.sr_position.distance, i2=target.sr_position.index, dist2=target.sr_position.distance
        )
        # self.path_length = path_length
        r = eq2(displacement=path_length, initial_velocity=current.speed, final_velocity=target.speed, time=None)
        path_time = r[3]
        time_end = self.start.time + path_time
        logger.debug(f"control sr values: {sf(path_length, 'm')} in {sf(path_time, 's')}, end at {st(time_end)} ({sf(current.speed, 'm/s')} -> {sf(target.speed, 'm/s')})")
        self.target.time = time_end
        #
        self.current.path_length = path_length
        self.current.path_time = path_time
        # if self.target.time < time_end:
        #     t = time_end - self.target.time
        #     self.target.time = time_end
        #     logger.log(8, f"new target time {st(self.target.time)} ({round(t, 1)}s later)")
        # elif self.target.time > time_end:
        #     t = self.target.time - time_end
        #     self.target.time = time_end
        #     logger.log(8, f"target time is ahead, would wait {round(t, 1)}s; adjusted, will not wait")
        self.en_route = True
        logger.debug("..built")
        # Note: At end of path: move finished (cannot progress)
        # 1. set_current()     current <- target(old): Transfert a few info from old target to current
        # Then tick()
        # 2. set_target()      target(old) <- target(new): Install new target
        # 3. mkPath current => target(new) <- build route from current to new target
        # 4. set_start()       start <- current at begining of path
        # When ticked() move can continue

    def targetReached(self) -> bool:
        r = False
        if self.current.sr_position.index > self.target.sr_position.index:
            r = True
        elif self.current.sr_position.index == self.target.sr_position.index and self.current.sr_position.distance >= self.target.sr_position.distance:
            r = True
        # if not r:
        #     if self.current.time >= self.target.time and self.en_route:  # note: might turn bruptly or change speed instantaneously to catch up
        #         # experimentally, we observed delay might occur if X-Plane activity introduces tiny delays (~ a few millisecs)
        #         logger.debug(f"target not reached but time is out {round(self.current.time - self.target.time, 3)}, continuing..")
        #         # r = True
        # else:
        if r and self.current.time > self.target.time and self.en_route:  # note: might turn bruptly or change speed instantaneously to catch up
            logger.debug(f"target reached late {round(self.current.time - self.target.time, 3)}s")
        # logger.debug(f"{r}: {self.current.sr_position} {'>=' if r else '<'} {self.target.sr_position}")
        return r

    def nextPosition(self):
        # test: self.indicator = int(self.current.time / 10) % 4
        if self.targetReached():
            return self.current.position, self.current.heading, self.current.sr_position, True
        if self.indicator != INDICATOR.STOP:
            self.indicator = self.nextTurnIndicator(self.current.route_index)  # compute turn indicator code for turns
        dt = self.current.time - self.start.time
        if (self.current.path_length > 50.0 or self.current.path_time > 10) and not self.status != CURSOR_STATUS.FINISHING:  # adjust fmcar_speed
            ots = self.target.speed  # orignal target speed
            self.target.speed = faster((self.target.speed + self._acf_speed) / 2)
            # logger.debug(f"new speeds: {sf(self.start.speed, 'm/s')} -> {sf(self.target.speed, 'm/s')} (was {sf(ots, 'm/s')})")
        # slow_debug(c=self.cnt, s=f"speeds: {sf(self.start.speed, 'm/s')} -> {sf(self.target.speed, 'm/s')}")
        r = eq2(displacement=None, initial_velocity=self.start.speed, final_velocity=self.target.speed, time=dt)
        d = r[0]
        point, hdg, idx, dist = self.route.srAheadRoute(self.current.sr_route, i=self.start.sr_position.index, start=self.start.sr_position.distance, dist=d)
        sr_position = OnRoute(index=idx, distance=dist)
        # debug
        dc = distance(self.current.position, point)
        if dc > 10.0:  # meters
            logger.debug(f"apparent big jump d={sf(d, 'm')} t={round(self.current.last_inc_time, 3)}s")

        return point, hdg, sr_position, False

    def move(self, t: float) -> int | float:
        # Currently: only linear interposition
        # between start and end
        # Future: d += speed * t with avg(speed) for acceleration
        def slow_debug(c, s):
            if c % 200 == 0:
                logger.debug(s)

        self.cnt += 1
        self.current.last_time = self.current.time
        self.current.last_inc_time = t
        self.current.time += t

        if self.cursor is None:
            slow_debug(self.cnt, "no cursor to move")
            return 2.0  # secs

        # self.indicator = INDICATOR(int(self.current.time / 5) % 4)

        # debug, can be suppressed, ticker to control move is working
        now = ts()
        msg = f"now={st(now)}: curr_time={st(self.current.time)} (diff={round(self.current.time - now, 3)}), target={st(self.target.time)}, before target={round(self.target.time-self.current.time, 3)}"
        slow_debug(self.cnt, msg)

        self.current.position, self.current.heading, self.current.sr_position, finished = self.nextPosition()
        if finished:
            if self.en_route:
                logger.debug(f"target '{self.target.comment}' reached")
                self.en_route = False
            if self.set_current():
                logger.debug("current adjusted")
            if not self._tick():
                # slow_debug(self.cnt, "no more future (distance)")
                return 1.0  # no need to move cursor
        # logger.debug(f"move at {st(self.current.time)}: {self.current.route_index} {self.current.sr_position} {sf(self.current.heading, '')}")
        self.cursor.move(lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.above_ground)
        if self.indicator_cursor is not None:
            self.indicator_cursor.move(
                lat=self.current.position.lat, lon=self.current.position.lon, hdg=self.current.heading, elev=self.detail.indicator_shift[0], fwd=self.detail.indicator_shift[1]
            )
        return -1

    def nextTurnIndicator(self, edge: int) -> INDICATOR:
        # returns a turn indicator to display if necessary
        TURN_LIMIT = 30.0  # no indicator for turns below that

        if edge == NOT_ON_ROUTE:
            edge = -1
        next_vertex = min(edge + 1, len(self.route.vertices) - 1)
        nextvtx = self.route.vertices[next_vertex]
        dist_to_next_vertex = distance(self.current.position, nextvtx)
        if round(self.last_dist_to_next_vertex, 1) == round(dist_to_next_vertex, 1):  # not moved
            return self._indicator
        self.last_dist_to_next_vertex = dist_to_next_vertex
        turn = self.route.turns[edge]
        idx = next_vertex
        while abs(turn) < TURN_LIMIT and idx < len(self.route.turns):
            turn = self.route.turns[idx]
            idx = idx + 1
        if idx >= len(self.route.route):  # end of route
            idx = len(self.route.route) - 1
        dist_to_next_turn = 0 if abs(self.route.turns[next_vertex]) > TURN_LIMIT else self.route.dtb[next_vertex]
        dist_to_next_turn += dist_to_next_vertex
        # logger.debug(f"at edge {edge}, next turn at edge {idx}, turn={sf(turn, 'D')}, at d={sf(dist_to_next_turn, 'm')}")
        indicator = INDICATOR.FOLLOW_ME
        if abs(turn) > TURN_LIMIT and dist_to_next_turn < self.detail.indicator_warning_distance:
            indicator = INDICATOR.LEFT if turn < 0 else INDICATOR.RIGHT
        return indicator

    # End of route elegance: End of route is reached and Cursor progress a little more then vanishes
    #
    def isFinishing(self) -> bool:
        return self.status == CURSOR_STATUS.FINISHING

    def isFinished(self) -> bool:
        return self.status == CURSOR_STATUS.FINISHED

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
        LEAVE_WAIT_BEFORE = 30  # secs, will be dynamic later

        hdg = self.route.orientLastVertex()
        rnd = 1 if (int(ts()) % 2) == 0 else -1
        if self.route.move == MOVEMENT.DEPARTURE and self.route.departure_runway is not None:
            # we have to set the rwy heading on the last future (its future heading...)
            last_pos = self._future.last()
            txt = "(target)"
            if last_pos is None:
                last_pos = self.target
                txt = "(last)"
            logger.log(8, f"last segment before runway: {last_pos} {txt}")
            last_pos.heading = hdg
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
        t = ts() + LEAVE_WAIT_BEFORE + td
        tt = td
        logger.debug(f"carry forward {sf(LEAVE_DIST_AHEAD, 'm')} in {sf(td, 's')} heading {sf(hdg1, 'D')}, terminates heading {sf(hdg, 'D')}")
        self.future(position=d1, hdg=hdg, speed=spd, t=t, text=f"carry on forward (reason={message})")

        # returnToRamp(final_position=d1)

        # "Away" to away and on the size
        final_dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        spd = self.detail.leave_speed
        td = LEAVE_DIST_SIDE / spd
        t = t + td
        tt = tt + td
        logger.debug(f"carry sideway {sf(LEAVE_DIST_SIDE, 'm')} in {sf(td, 's')} heading {sf(hdg, 'D')}")
        self.future(position=final_dest, hdg=hdg, speed=spd, t=t, text=f"leaving on the side (reason={message})")
        self.active = False
        logger.debug("cursor inactive")
        logger.debug(f"cursor finish programmed ({message})")

    def position(self):
        # will be caled by Find() to find the cursor position
        return (self.final_position.lat, self.final_position.lon)

    def returnToRamp(self, final_position: Point):
        # Experimental, will add later
        self.final_position = final_position
        dst = self.route.route[0]
        closest, dist = self.route.graph.findClosestVertex(point=final_position)
        rwy = self.route.departure_runway
        route = Route.Find(
            graph=self.route.graph, aircraft=self, arrival_runway=rwy, dst_pos=dst, dst_type="ramp", move=MOVEMENT.ARRIVAL, use_strict_mode=True, use_threshold=False
        )
        self.status = CURSOR_STATUS.HOLD  # lock, prevents tick when changing routes
        logger.debug("install return route..")
        if self.route is not None:
            self.resetRoute()
        self.route = route
        self.status = CURSOR_STATUS.ACTIVE
        logger.debug("..return route installed..")
        length = route.route[-1].getProp("srTotalDistance")
        speed = self.adjustedSpeed()
        tt = ts() + length / speed
        self.future_index(edge=route.route[-1].getProp("srRevIndex"), dist=length, speed=0.0, t=tt)
        logger.debug("return route programmed")
