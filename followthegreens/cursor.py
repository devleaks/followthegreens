import os
from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from sre_compile import dis

from .oned import eq2

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import MOVEMENT, logger
from .geo import Point, Line, destination, distance
from .lightstring import XPObject

ABOVE_GROUND = 0.25  # xcsl objects offset, in meter


class CURSOR_STATUS(StrEnum):
    NEW = "NEW"  # cursor just created
    READY = "READY"  # cursor initialized, got starting position, cursor spawned
    SCHEDULED = "SCHEDULED"  # flight loop running
    ACTIVE = "ACTIVE"  # got first path, running
    FINISHING = "FINISHING"  # initiated finish
    FINISHED = "FINISHED"  # finish finished, can be deleted
    DESTROYED = "DESTROYED"  # cursor destroyed
    DELETED = "DELETED"  # cursor deleted


def ts() -> float:
    return datetime.now().timestamp()


def st(t: float) -> float:
    if t <= 0:
        return 0.0
    d = datetime.fromtimestamp(t)
    d = d.replace(hour=d.hour - 2, minute=0, second=0, microsecond=0)
    t0 = d.timestamp()
    return round(t - t0, 3)


def slow_debug(c, s):
    if c % 100 == 0:
        logger.debug(s)


@dataclass
class CursorType:
    """Cursor detailed information with default values"""

    filename: str = "xcsl/FMC.obj"
    above_ground: float = ABOVE_GROUND

    slow_speed: float = 3.0  # turns, careful move, all speed m/s
    normal_speed: float = 7.0  # 25km/h
    leave_speed: float = 10.0  # expedite speed to leave/clear an area
    fast_speed: float = 14.0  # running fast to a destination far away

    turn_radius: float = 25.0  # m

    acceleration: float = 1.0  # m/s^2, same deceleration
    deceleration: float = -1.0  # m/s^2, same deceleration

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

    index: int = -1
    distance: float = 0.0  # distance "forward" from above index


@dataclass
class Situation:
    """4 position with other information"""

    position: Point | None = None
    time: float = ts()
    heading: float = 0.0
    speed: float = 0.0

    route_index: int = -1
    vertex: Point | None = None  # vertex of above index
    distance_on_edge: float = 0.0  # distance forward of above vertex
    path_length: float = 0.0  # at end of situation
    end: tuple = (-1, 0)

    comment: str = ""

    def __str__(self):
        """Returns a string containing only the non-default field values."""

        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values
        def f(i):
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
        self.cursor = XPObject(None, 0, 0, 0)

        self._status = CURSOR_STATUS.NEW
        self.active = False  # accepts futures if active

        self.route = route  # route that the cursor must follow

        self._future = SimpleQueue()

        # Current, initialized with init() and incrementally followed
        self.current = Situation()
        self.target = Situation()
        self.segment = None  # when new route segment started

        # Time and position when a new path is initiated
        self.path_start_pos = None
        self.path_start_time = ts()
        self.path_length = 0
        self.path_time = 0

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
        self.current.time = ts()
        self.current.comment = "init"
        self.current.route_index = -1  # we start not on route

        self.cursor.position = self.current.position
        self.cursor.heading = self.current.heading
        self.cursor.place(lightType=self.cursor_object)
        self.cursor.on()

        self.active = True
        self.status = CURSOR_STATUS.READY
        logger.debug(f"initialized at {round(self.current.time, 3)}, pos={self.current.position.coords()}, speed={round(self.current.speed, 1)}m/s")
        self.startFlightLoop()

    def destroy(self):
        self.stopFlightLoop()
        if self.cursor is not None:
            self.cursor.destroy()
            self.cursor = None
        if self.cursor_object is not None:
            del self.cursor_object  # unloads object
            self.cursor_object = None
        self.status = CURSOR_STATUS.DESTROYED

    def can_delete(self) -> bool:
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
            self.status = CURSOR_STATUS.SCHEDULED
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
            self.move(t=elapsedSinceLastCall)
            return -1
        except:
            logger.error("error", exc_info=True)
        return 5.0

    # Abrupt change or route, reset
    #
    def change_route(self, ftg):
        logger.debug("change route..")
        if self.route is not None:
            self.reset_route()
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

        try:
            logger.log(8, "..estimate new position ahead of aircraft..")
            # if route changed we assume aircraft is moving and this.inited
            ahead = ftg.aircraft.adjustAhead()
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
                f"..move on route at {round(ahead_at_join, 1)}m ahead, heading={round(join_route.bearing(), 0)}, in {round(join_time, 1)}s (aircraft will be at light index {light_progress}).."
            )
            # we move the car in front of acf, and progress at same speed as acf.
            self.future(
                position=join_route.end,
                hdg=light_ahead.heading,
                speed=acf_speed,
                t=dt,
                edge=-1,  # not on route
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

    def reset_route(self):
        # They won't be any valid route anymore.
        # We have to stop the future
        logger.log(8, "reseting cursor planned route..")
        self._future.clear()
        logger.log(8, "..reset")

    # Itinerary: Next positions (as requested from client)
    #
    def future(self, position: Point, hdg: float, speed: float, t: float, edge: int = -1, tick: bool = False, text: str = "", end: tuple = (-1, 0)):
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
        f = Situation(position=position, heading=hdg, speed=speed, time=t, route_index=edge, comment=text, end=end)
        if edge >= 0:
            f.vertex = self.route.vertices[edge]
            f.distance_on_edge = distance(f.vertex, position)
        self._future.put(f)
        self._qin += 1
        logger.debug(f"added future ({self._qin}, q={self._future.qsize()})): {f}")  #
        if tick:
            ignore = self._tick()

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
                self.future(position=dest, hdg=hdg, speed=speed, t=t, edge=edge, text="go further on edge")
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
        if self._future.empty():
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
            return False
        f = self._future.get()
        if f is not None:
            self._qout += 1
            logger.debug(f"tick future ({self._qout}, q={self._future.qsize()}) at {st(self.current.time)}): {f}..")  #
            if self._set_target(f):
                self._mkPathToTarget()
                if self.status == CURSOR_STATUS.READY:
                    self.status = CURSOR_STATUS.ACTIVE
                self._set_current = False
                logger.debug(f"..ticked")  #
                return True
        return False

    def _set_target(self, target: Situation):
        logger.log(8, f"current {self.current.comment}")
        logger.debug(f"setting target {target.comment}..")
        if self.current.route_index < 0:  # direct route to target
            logger.debug("direct route to target")
            self.target = target
            logger.debug("..set")
            return True
        if target.route_index < 0:
            logger.debug("direct route to target")
            self.target = target
            logger.debug("..set")
            return True
        # we are on route
        if target.route_index < self.current.route_index:
            logger.debug(f"cannot backup edge ({target.route_index} < {self.current.route_index})")
            return False
        if target.route_index == self.current.route_index and target.distance_on_edge < self.current.distance_on_edge:
            logger.debug(f"cannot backup on current edge ({round(target.distance_on_edge, 1)}m < {round(self.current.distance_on_edge, 1)}m)")
            return False
        self.segment = self.current
        self.target = target
        logger.debug("..set")
        return True

    def _mkPathToTarget(self):
        self.path_start_pos = self.current.position
        self.path_start_time = self.current.time
        self.path_start_speed = self.current.speed
        self.path_length = distance(self.current.position, self.target.position)

        # Enforce speed for now
        if self.current.speed <= 0.1:
            self.current.speed = self.detail.normal_speed
            logger.warning(f"set current speed {round(self.current.speed, 1)}m/s")
        if self.target.speed <= 0.1:
            self.target.speed = self.detail.normal_speed
            logger.warning(f"set target speed {round(self.target.speed, 1)}m/s")

        # Adjust ETA
        r = eq2(displacement=self.path_length, initial_velocity=self.current.speed, final_velocity=self.target.speed, time=None)
        self.path_time = r[3]
        time_end = self.path_start_time + self.path_time
        if self.target.time < time_end:
            t = time_end - self.target.time
            self.target.time = time_end
            logger.log(8, f"new target time {st(self.target.time)} ({round(t, 1)}s later)")
        elif self.target.time > time_end:
            t = self.target.time - time_end
            self.target.time = time_end
            logger.log(8, f"target time is ahead, would wait {round(t, 1)}s; adjusted, will not wait")

        # set path variables for efficient route calc
        if self.current.route_index < 0:  # on route
            self.current.vertex = self.current.position
            self.current.distance_on_edge = 0
            logger.debug(f"direct path, need to travel {round(self.path_length, 1)}m in {round(self.path_time, 1)}")
        else:
            if self.current.route_index != self.target.route_index:  # check
                logger.warning(f"route index differ ({self.current.route_index}, {self.target.route_index})")
            # logger.debug(f"control: {round(self.path_length, 1)}m {round(self.target.distance_on_edge - self.current.distance_on_edge, 1)}m")
            logger.debug(
                f"path on edge {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m from edge start, need to travel {round(self.path_length, 1)}m on edge in {round(self.path_time, 1)}, will finish at {st(self.target.time)}"
            )

    def distance(self, position) -> float:
        return distance(self.current.position, position)

    def speed(self) -> float:
        return self.current.speed

    def adjustedSpeed(self, speed_type: str = "normal", reference: float = 0.0) -> float:
        if speed_type == "fast":
            return self.detail.fast_speed
        return self.detail.normal_speed

    def set_current(self):
        if self._set_current:
            return
        logger.debug(f"at {st(self.current.time)}")
        # DO NOT update self.current_time which continue flowing...
        if self.target.end[0] >= 0:
            self.current.route_index = self.target.end[0]
            self.current.distance_on_edge = self.target.end[1]
            logger.debug(f"set end: set current edge {self.current.route_index}, at {round(self.current.distance_on_edge, 1)}m from edge start")
        else:
            coords = self.target.vertex.coords() if self.target.vertex is not None else "none"
            logger.debug(f"set end: set current edge {self.current.route_index} to target edge {coords}")
            self.current.route_index = self.target.route_index
            self.current.distance_on_edge = self.target.distance_on_edge

        self.current.position = self.target.position
        self.current.heading = self.target.heading
        self.current.speed = self.target.speed
        self.current.comment = self.target.comment
        self.current.vertex = self.target.vertex
        self._set_current = True

    def nextPosition(self):
        dt = self.current.time - self.path_start_time
        r = eq2(displacement=None, initial_velocity=self.current.speed, final_velocity=self.target.speed, time=dt)
        d = r[0]
        if d > self.path_length:
            # logger.debug("nextPosition says path finished")
            return self.current.position, self.current.heading, True
        h = self.current.heading
        p = destination(self.path_start_pos, self.current.heading, d)
        return p, h, False

    def move(self, t: float):
        # Currently: only linear interposition
        # between start and end
        # Future: d += speed * t with avg(speed) for acceleration

        self.cnt += 1
        # old_time = self.current.time
        self.current.time += t

        if self.cursor is None:
            slow_debug(self.cnt, "no cursor to move")
            return

        if self.current.position is None or self.target.position is None:  # not initialized yet, no target
            # if not self.status in [CURSOR_STATUS.ACTIVE, CURSOR_STATUS.FINISHING]:
            slow_debug(
                self.cnt,
                f"no path. curr={self.current.position.coords() if self.current.position is not None else 'none'}, target={self.target.position.coords() if self.target.position is not None else 'none'}",
            )
            return

        now = ts()
        msg = f"now={st(now)}: curr_time={st(self.current.time)} (diff={round(self.current.time - now, 3)}), target={st(self.target.time)}, before target={round(self.target.time-self.current.time, 3)}"
        slow_debug(self.cnt, msg)

        # if at end of time, should be at end of path too...
        if self.current.time >= self.target.time:  # note: might turn bruptly or change speed instantaneously to catch up
            slow_debug(self.cnt, "time is out for path")
            self.set_current()
            if not self._tick():
                # slow_debug(self.cnt, "no more future (time)")
                return

        d = distance(self.path_start_pos, self.current.position)
        # is current position after path_length?
        if d >= self.path_length:
            slow_debug(self.cnt, f"path is finished ({round(d, 1)}m < {round(self.path_length, 1)}m)")
            self.set_current()
            if not self._tick():
                # slow_debug(self.cnt, "no more future (distance)")
                return

        self.current.position, hdg, finished = self.nextPosition()
        self.cursor.move(lat=self.current.position.lat, lon=self.current.position.lon, hdg=hdg, elev=self.detail.above_ground)

    # End of route elegance: End of route is reached and Cursor progress a little more then vanishes
    #
    def is_finishing(self) -> bool:
        return self.status == CURSOR_STATUS.FINISHING

    def is_finished(self) -> bool:
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
        LEAVE_WAIT_BEFORE = 10  # secs, will be dynamic later

        hdg = self.route.edges_orient[-1]
        rnd = 1 if (int(ts()) % 2) == 0 else -1
        has_runway = self.route.departure_runway is not None
        logger.debug(f"{self.route.move}, {has_runway}")
        if self.route.move == MOVEMENT.DEPARTURE and self.route.departure_runway is not None:
            hdg = self.route.departure_runway.bearing()
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
        spd = self.detail.leave_speed
        hdg = hdg + 90 * rnd
        td = LEAVE_DIST_AHEAD / spd
        t = ts() + LEAVE_WAIT_BEFORE + td
        tt = td
        logger.debug(f"carry forward {round(LEAVE_DIST_AHEAD, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=d1, hdg=hdg, speed=spd, t=t, text=f"carry on forward ({message})")

        # "Away" to away and on the size
        final_dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        spd = self.detail.leave_speed
        td = LEAVE_DIST_SIDE / spd
        t = t + td
        tt = tt + td
        logger.debug(f"carry sideway {round(LEAVE_DIST_SIDE, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=final_dest, hdg=hdg, speed=spd, t=t, text=f"leaving on the side ({message})")
        self.active = False
        logger.debug(f"cursor finish programmed ({message})")
