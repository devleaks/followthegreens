from logging import disable
import os
import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .kinematics import getTime, getDistance2

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import logger
from .geo import Point, Line, destination, distance, bearing
from .lightstring import XPObject


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


@dataclass
class CursorType:
    """Cursor detailed information with default values"""

    filename: str = "xcsl/FMC.obj"

    slow_speed: float = 3.0  # turns, careful move, all speed m/s
    normal_speed: float = 7.0  # 25km/h
    leave_speed: float = 10.0  # expedite speed to leave/clear an area
    fast_speed: float = 14.0  # running fast to a destination far away

    turn_radius: float = 25.0  # m

    acceleration: float = 1.0  # m/s^2, same deceleration
    deceleration: float = -1.0  # m/s^2, same deceleration


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

class MyQueue:

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

    def qsize(self) -> int:
        return len(self._items)


class Cursor:
    # Linear interpolator

    SPAWN_SIDE_DISTANCE = 60

    def __init__(self, detail, route) -> None:
        self.detail = detail
        self.cursor_object = CursorObject(detail.filename)
        self.cursor = XPObject(None, 0, 0, 0)

        self._status = CURSOR_STATUS.NEW
        self.active = False  # accepts futures if active

        self.route = route
        self.on_route = False
        self._future = MyQueue()  # Queue element: tuple(lat: float, lon: float, hdg: float, speed: float, t: float, last_speed: float, text: str)
        self.last_future_speed = 0
        self.light_progress = 0

        self.last_time = 0
        self.curr_pos = None
        self.curr_hdg = 0
        self.curr_speed = 0
        self.curr_last_speed = 0
        self.curr_time = ts()
        self.curr_text = ""
        self.curr_index = 0  # where we are now
        self.curr_dist = 0
        self.curr_start_pos = None
        self.curr_start_time = ts()

        self.target_pos = None
        self.target_hdg = 0
        self.target_speed = 0
        self.target_last_speed = 0
        self.target_time = 0
        self.target_text = ""
        self.target_index = 0  # where we will be in the future
        self.target_dist = 0

        # working var for interpolation
        self.path = None  # actually, curr_path on which we are currently moving
        self.refcursor = "FtG:cursor"
        self.flightLoop = None
        self.nextIter = -1
        self._qin = 0
        self._qout = 0
        self.cnt = -1
        self._total_distance = 0
        self._timer = None
        self.msg = ""
        logger.info(str(self.detail))

    @property
    def status(self) -> CURSOR_STATUS:
        return self._status

    @status.setter
    def status(self, status: CURSOR_STATUS):
        if status != self._status:
            self._status = status
            logger.debug(f"{type(self).__name__} is now {status}")

    @property
    def usable(self) -> bool:
        return self.cursor is not None and self.cursor_object.has_obj

    @property
    def inited(self) -> bool:
        return self.curr_pos is not None and self.route is not None

    def init(self, position: Point, heading: float, speed: float = 0.0):
        # spawn cursor
        if self.inited:  # only init once
            return
        self.curr_pos = Point(lat=position.lat, lon=position.lon)
        self.curr_hdg = heading
        self.curr_speed = speed
        self.curr_time = ts()
        self.curr_text = "init"

        self.cursor.position = self.curr_pos
        self.cursor.heading = self.curr_hdg
        self.cursor.place(lightType=self.cursor_object)
        self.cursor.on()

        self.active = True
        self.status = CURSOR_STATUS.READY
        logger.debug(f"initialized at {round(self.curr_time, 3)}, pos={self.curr_pos.coords()}, speed={round(self.curr_speed, 1)}m/s")
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

    def change_route(self, ftg):
        logger.debug("change route..")
        if self.route is not None:
            self.reset_route()
        self.route = ftg.route
        logger.debug("new route installed")

        acf_speed = ftg.aircraft.speed()

        if ftg.lights is None:
            logger.warning(f"no light")
            return
        closestLight, dist = ftg.lights.closest(ftg.aircraft.position())
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0

        # if route changed we assume aircraft is moving and this.inited
        try:
            ahead = ftg.aircraft.adjustAhead()
            join_time = 20  # secs, reasonable time from spawn position to ahead of acf, aircraft will speed up
            acf_ahead = min(acf_speed, self.detail.fast_speed) * join_time
            ahead_at_join = acf_ahead + ahead
            light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
            join_route = Line(start=self.curr_pos, end=light_ahead.position)
            initial_speed = join_route.length() / join_time
            self.curr_speed = initial_speed
            self.curr_hdg = join_route.bearing()
            dt = ts() + join_time
            # we will move the car well ahead, the car should not backup
            # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
            self.light_progress = closestLight + int(acf_ahead / ftg.lights.distance_between_green_lights)
            logger.debug(
                f"..move on route at {round(ahead_at_join, 1)}m ahead, heading={round(join_route.bearing(), 0)}, in {round(join_time, 1)}s (aircraft will be at light index {self.light_progress}).."
            )
            # we move the car in front of acf, and progress at same speed as acf.
            self.future(position=join_route.end, hdg=light_ahead.heading, speed=acf_speed, t=dt, tick=True, text="go on route ahead of aircraft after new route")
            # finally, we have to tell future_index() where car is when it join route
            # so that when move() catches up with future_index() it will start from there
            # (after above future)
            self.set_target_index(edge=light_ahead.edgeIndex, dist=light_ahead.distFromEdgeStart)
            logger.debug("..route changed, already taxiing")
        except:
            logger.debug("error", exc_info=True)

    def reset_route(self):
        # They won't be any valid route anymore.
        # We have to stop the future
        logger.debug("cursor reseting route")
        self._future.clear()
        logger.debug("reset")

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
        try:
            self.move(t=elapsedSinceLastCall)
            return -1
        except:
            logger.error("error", exc_info=True)
        return 5.0

    def future(self, position: Point, hdg: float, speed: float, t: float, edge: int = -1, tick: bool = False, text: str = ""):
        # Adds a move to the list of moves to do.
        # Adds a move from where cursor will be when called, in STRAIGHT LINE to position,
        # planning a turn towards hdg, and terminate at speed.
        # Set time at t.
        # Provoke a tick if requested.
        # Adds comment to the move if provided (it allows to find/understand moves when they are called.)
        if not self.active:
            logger.debug("cursor not active")
            return
        if self.status == CURSOR_STATUS.FINISHED:
            logger.debug("cursor finished, does not accept future position")
            return
        self._future.put((position.lat, position.lon, hdg, speed, t, edge, self.last_future_speed, text))  # args for _set_target()
        self.last_future_speed = speed
        self.on_route = edge != -1
        self._qin += 1
        logger.debug(f"added future ({self._qin}, q={self._future.qsize()}): {text} (h={round(hdg, 0)}D, s={round(speed, 1)}m/s, t={st(t)})")
        if tick:
            ignore = self._tick()

    def set_current_index(self, edge: int, dist: float | None = None):
        self.current_index = edge
        msg = ""
        if dist is not None:
            self.current_dist = dist
            msg = f"{round(dist, 1)}m of "
        logger.debug(f"jumped to {msg}index {edge}")

    def set_target_index(self, edge: int, dist: float):
        self.target_index = edge
        self.target_dist = dist
        logger.debug(f"future at {round(dist, 1)}m of index {edge}")

    def future_index(self, edge: int, dist: float, speed: float, t: float):
        # Creates future() to destination which is a distance from start of edge.
        #
        if not self.active:
            logger.debug("cursor not active")
            return
        # convert trip on the route into "future()" segements:
        if edge < self.target_index:
            logger.debug(f"cannot backup edges ({edge} < {self.target_index})")
            return
        logger.debug(f"smooth route equivalent {self.route.smooth_equiv(edge, dist)}")
        logger.debug(f"currently on edge {self.target_index} at {round(self.target_dist, 1)}m, need to go on edge {edge} at {round(dist, 1)}m")
        logger.debug(f"currently at speed {self.last_future_speed}m/s, will terminate at {round(speed, 1)}m/s")
        if edge == self.target_index:  # remains on same edge
            if dist > self.target_dist:
                dest = self.route.on_edge(edge, dist)  # destination(self.route.vertices[edge], self.route.edges_orient[edge], dist)
                hdg = self.route.edges_orient[edge]
                self.future(position=dest, hdg=hdg, speed=speed, t=t, edge=edge, text="go further on edge")
                logger.debug(f"progress on edge {edge} from {round(self.target_dist, 1)}m to {round(dist, 1)}m")
                self.target_dist = dist
            else:
                logger.log(8, f"no progress on edge {edge}, ({round(dist, 1)}m <= {round(self.target_dist, 1)}m)")
            return

        vertices = self.route.vertices

        local_speed = self.curr_last_speed
        if local_speed == 0:
            if speed > 0:
                local_speed = speed
            else:
                local_speed = self.detail.normal_speed
                logger.debug(f"no speed for future, forced normal local speed {round(local_speed, 1)}m/s")

        # first quick precompute
        e = self.route.edges[self.target_index]
        total_dist = e.cost - self.target_dist
        temp = self.target_index + 1
        last_edge = 0
        # travel entire next edges
        while temp < edge and temp < (len(vertices) - 1):
            e = self.route.edges[temp]
            total_dist += e.cost
            temp = temp + 1
        total_dist += dist
        total_time = total_dist / local_speed
        last_edge = temp - 1
        logger.debug(f"total distance to travel {round(total_dist, 1)}m at {round(local_speed, 1)}m/s -> total travel time ={round(total_time, 1)}s, last_edge={last_edge}")

        start_time = t - total_time

        # travel to end of current edge
        control_dist = 0
        control_time = 0
        e = self.route.edges[self.target_index]
        d = e.cost - self.target_dist
        control_dist += d
        logger.log(8, f"edge {self.target_index} length={round(e.cost, 1)}m, heading={round(e.bearing(), 0)}, start_time={start_time}, end_time={t}")
        tt = d / local_speed
        control_time += tt
        start_time += tt
        hdg = self.route.edges_orient[min(self.target_index + 1, len(self.route.edges) - 1)]
        self.future(
            position=vertices[self.target_index + 1],
            hdg=hdg,
            speed=local_speed,
            t=start_time,
            edge=self.target_index,
            text=f"{round(d, 1)}m to end of current edge {self.target_index}",
        )
        logger.log(8, f"progress {round(d, 1)}m on edge {self.target_index} to end of edge in {round(tt, 1)}s")
        self.target_index = self.target_index + 1

        # travel entire next edges
        while self.target_index < edge and self.target_index < (len(self.route.edges)):
            e = self.route.edges[self.target_index]
            control_dist += e.cost
            tt = e.cost / local_speed
            control_time += tt
            start_time += tt
            # route to edge
            hdg = self.route.edges_orient[min(self.target_index + 1, len(self.route.edges) - 1)]
            # s = speed if self.target_index == last_edge else local_speed  # carry on as last speed
            self.future(
                position=vertices[self.target_index + 1],
                hdg=hdg,
                speed=local_speed,
                t=start_time,
                edge=self.target_index,
                text=f"{round(e.cost, 1)}m to end of edge {self.target_index}",
            )
            logger.log(8, f"progress on edge {self.target_index} (whole length {round(e.cost, 1)}m, in {round(tt, 1)}s)")
            self.target_index = self.target_index + 1

        # travel on new current edge
        newpos = self.route.on_edge(edge, dist)
        self.future(position=newpos, hdg=self.route.edges_orient[edge], speed=speed, t=t, edge=edge, text=f"{round(dist, 1)}m on edge {edge}")
        self.target_index = edge
        self.target_dist = dist
        control_dist += dist
        tt = dist / local_speed
        control_time += tt
        start_time += tt
        logger.log(8, f"progress on edge {edge} (length {round(dist, 1)}m, in {round(tt, 1)}s)")
        logger.log(8, f"control distance travelled {round(control_dist, 1)}m, in {round(control_time, 1)}s")

    def future_index_smooth(self, edge: int, dist: float, speed: float, t: float):
        # Creates future() to destination which is a distance from start of edge.
        #
        if not self.active:
            logger.debug("cursor not active")
            return
        # convert trip on the route into "future()" segements:
        if edge < self.target_index:
            logger.debug(f"cannot backup edges ({edge} < {self.target_index})")
            return
        logger.debug(f"currently on edge {self.target_index} at {round(self.target_dist, 1)}m, need to go on edge {edge} at {round(dist, 1)}m")
        logger.debug(f"currently at speed {self.last_future_speed}m/s, will terminate at {round(speed, 1)}m/s")

        if edge == self.target_index:  # remains on same edge
            if dist > self.target_dist:
                dest = self.route.on_edge_smooth(edge, dist)  # destination(self.route.vertices[edge], self.route.edges_orient[edge], dist)
                hdg = self.route.edges_orient[edge]
                self.future(position=dest, hdg=hdg, speed=speed, t=t, edge=edge, text="go further on edge")
                logger.debug(f"progress on edge {edge} from {round(self.target_dist, 1)}m to {round(dist, 1)}m")
                self.target_dist = dist
            else:
                logger.log(8, f"no progress on edge {edge}, ({round(dist, 1)}m <= {round(self.target_dist, 1)}m)")
            return

        vertices = self.route.smoothRoute

        local_speed = self.curr_last_speed
        if local_speed == 0:
            if speed > 0:
                local_speed = speed
            else:
                local_speed = self.detail.normal_speed
                logger.debug(f"no speed for future, forced normal local speed {round(local_speed, 1)}m/s")

        # first quick precompute
        e = vertices[self.target_index]
        total_dist = e.getProp("srDistance") - self.target_dist
        temp = self.target_index + 1
        last_edge = 0
        # travel entire next edges
        while temp < edge and temp < (len(vertices) - 1):
            e = vertices[temp]
            total_dist += e.getProp("srDistance")
            temp = temp + 1
        total_dist += dist
        total_time = total_dist / local_speed
        last_edge = temp - 1
        logger.debug(f"total distance to travel {round(total_dist, 1)}m at {round(local_speed, 1)}m/s -> total travel time ={round(total_time, 1)}s, last_edge={last_edge}")

        start_time = t - total_time

        # travel to end of current edge
        control_dist = 0
        control_time = 0
        e = vertices[self.target_index]
        d = e.getProp("srDistance") - self.target_dist
        control_dist += d
        logger.log(8, f"edge {self.target_index} length={round(e.getProp("srDistance"), 1)}m, heading={round(e.getProp("srBearing"), 0)}, start_time={start_time}, end_time={t}")
        tt = d / local_speed
        control_time += tt
        start_time += tt
        hdgvtx = vertices[min(self.target_index + 1, len(self.route.edges) - 1)]
        hdg = hdgvtx.getProp("srBearing")
        self.future(
            position=vertices[self.target_index + 1],
            hdg=hdg,
            speed=local_speed,
            t=start_time,
            edge=self.target_index,
            text=f"{round(d, 1)}m to end of current edge {self.target_index}",
        )
        logger.log(8, f"progress {round(d, 1)}m on edge {self.target_index} to end of edge in {round(tt, 1)}s")
        self.target_index = self.target_index + 1

        # travel entire next edges
        while self.target_index < edge and self.target_index < (len(vertices) - 1):
            e = vertices[self.target_index]
            d = e.getProp("srDistance")
            control_dist += d
            tt = d / local_speed
            control_time += tt
            start_time += tt
            # route to edge
            hdgvtx = vertices[min(self.target_index + 1, len(self.route.edges) - 1)]
            hdg = hdgvtx.getProp("srBearing")
            # s = speed if self.target_index == last_edge else local_speed  # carry on as last speed
            self.future(
                position=vertices[self.target_index + 1],
                hdg=hdg,
                speed=local_speed,
                t=start_time,
                edge=self.target_index,
                text=f"{round(e.cost, 1)}m to end of edge {self.target_index}",
            )
            logger.log(8, f"progress on edge {self.target_index} (whole length {round(d, 1)}m, in {round(tt, 1)}s)")
            self.target_index = self.target_index + 1

        # travel on new current edge
        newpos = self.route.on_edge_smooth(edge, dist)
        self.future(position=newpos, hdg=vertices[edge].getProp("srBearing"), speed=speed, t=t, edge=edge, text=f"{round(dist, 1)}m on edge {edge}")
        self.target_index = edge
        self.target_dist = dist
        control_dist += dist
        tt = dist / local_speed
        control_time += tt
        start_time += tt
        logger.log(8, f"progress on edge {edge} (length {round(dist, 1)}m, in {round(tt, 1)}s)")
        logger.log(8, f"control distance travelled {round(control_dist, 1)}m, in {round(control_time, 1)}s")

    def _tick(self) -> bool:
        # returns whether it ticked
        if self._future.empty():
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
                logger.debug("cursor finished")
            return False
        f = self._future.get()  # (lat: float, lon: float, hdg: float, speed: float, t: float, edge: int, last_speed: float, text: str)
        if f is not None:
            self._qout += 1  #                    0           1           2           3             4         5          6                  7
            logger.debug(f"tick future ({self._qout}, q={self._future.qsize()}) at {st(self.curr_time)}: {f[-1]} (h={round(f[2], 0)}D, s={f[3]}, (ls={f[6]}) t={st(f[4])})")
            if self._set_target(*f):
                self._mkPathToTarget()
                if self.status == CURSOR_STATUS.READY:
                    self.status = CURSOR_STATUS.ACTIVE
                return True
        return False

    def _set_target(self, lat: float, lon: float, hdg: float, speed: float, t: float, edge: int, last_speed: float, text: str):
        if edge >= 0:
            # check forward movement
            if edge < self.curr_index:
                logger.debug(f"cannot backup current edge ({edge} < {self.curr_index})")
                return False
            if edge == self.curr_index:
                d = self.route.from_edge(i=edge, position=Point(lat, lon))
                if d < self.curr_dist:
                    logger.debug(f"cannot backup on current edge ({round(d, 1)}m < {round(self.curr_dist, 1)}m)")
                    return False
                e = self.route.edges[edge]
                d0 = e.cost - self.curr_dist
                logger.debug(f"left {round(d0, 1)}m on current edge {edge}")
        self.curr_index = edge
        # move forward
        logger.debug(f"last time {st(self.last_time)} ->  {st(self.curr_time)} ({round(self.curr_time-self.last_time, 3)}s)")
        self.last_time = self.curr_time
        self.target_pos = Point(lat=lat, lon=lon)
        self.target_hdg = hdg
        self.target_speed = speed
        self.target_last_speed = last_speed
        self.target_time = t
        self.target_text = text
        logger.log(8, f"target time is {round(self.target_time, 2)} ({round(self.target_time-self.last_time, 2)} ahead)")
        return True

    def _mkPathToTarget(self):
        # Segment starts at vertex if no turn before, or at end of previous path
        # Previous path has turn or not, i.e. terminates at end vertex if not turn at end, or at end of end turn.
        self.curr_start_time = self.curr_time
        self.curr_start_pos = self.curr_pos
        # DEV
        if self.curr_speed == 0:
            self.curr_speed = self.detail.normal_speed
            logger.debug(f"DEV set current speed {round(self.curr_speed, 1)}m/s")
        if self.target_speed == 0:
            self.target_speed = self.detail.normal_speed
            logger.debug(f"DEV set target speed {round(self.target_speed, 1)}m/s")
        # DEV
        total_time = getTime(displacement=distance(self.curr_pos, self.target_pos), initial_velocity=self.curr_speed, final_velocity=self.target_speed)
        time_end = self.curr_start_time + total_time
        if self.target_time < time_end:
            t = time_end - self.target_time
            self.target_time = time_end
            logger.debug(f"new target time {st(self.target_time)} ({round(t, 1)}s later)")
        else:
            t = self.target_time - time_end
            self.target_time = time_end
            logger.debug(f"target time is ahead, would wait {round(t, 1)}s.. adjusted, will not wait")

    def nextPosition(self):
        if self.curr_time > self.target_time:  # this path is finished
            return self.curr_pos, self.curr_hdg, True

        dt = self.curr_time - self.curr_start_time
        d = getDistance2(initial_velocity=self.curr_speed, final_velocity=self.target_speed, time=dt)
        # logger.debug(f"speeds {round(self.curr_speed, 1)}m/s, {round(self.target_speed, 1)}")
        h = self.curr_hdg
        p = destination(self.curr_start_pos, self.curr_hdg, d)
        return p, h, False

    def move(self, t: float):
        # Currently: only linear interposition
        # between start and end
        # Future: d += speed * t with avg(speed) for acceleration
        ABOVE_GROUND = 0.25  # xcsl objects offset, in meter

        def slow_debug(s):
            if self.cnt % 100 == 0:
                logger.debug(s)

        self.cnt += 1
        # old_time = self.curr_time
        self.curr_time += t

        if self.cursor is None:
            slow_debug("no cursor to move")
            return
        if self.curr_pos is None or self.target_pos is None:  # not initialized yet, no target
            slow_debug(
                f"no path. curr={self.curr_pos.coords() if self.curr_pos is not None else 'none'}, target={self.target_pos.coords() if self.target_pos is not None else 'none'}"
            )
            return

        now = ts()
        msg = f"curr_time={st(self.curr_time)}, now={st(now)} (diff={round(self.curr_time - now, 3)}), target={st(self.target_time)}, before next={round(self.target_time-self.curr_time, 3)}"
        if self.path:
            msg = f"on path=speed={round(self.curr_speed, 1)}, {self.path.desc()}, {msg}"
        slow_debug(msg)

        if self.curr_time > self.target_time:  # might turn bruptly to catch up
            self.curr_hdg = self.target_hdg
            self.curr_speed = self.target_speed
            self.curr_last_speed = self.target_last_speed
            if not self._tick():
                self.cursor.move(lat=self.curr_pos.lat, lon=self.curr_pos.lon, hdg=self.curr_hdg, elev=ABOVE_GROUND)
                return
        self.curr_pos, hdg, finished = self.nextPosition()
        self.cursor.move(lat=self.curr_pos.lat, lon=self.curr_pos.lon, hdg=hdg, elev=ABOVE_GROUND)

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
        if self.route.departure_runway is not None:
            hdg = self.route.departure_runway.bearing()
            LEAVE_DIST_AHEAD = LEAVE_DIST_AHEAD * 2
            LEAVE_DIST_SIDE = LEAVE_DIST_SIDE * 2  # m
            if self.route.precise_start is not None:  # leaves towards departure area, like return to position
                rnd = self.route.departure_runway.side(self.route.precise_start)
        end = self.route.vertices[-1]
        d1 = destination(src=end, brngDeg=hdg, d=LEAVE_DIST_AHEAD)
        hdg = hdg + 90 * rnd
        dest = destination(src=d1, brngDeg=hdg, d=LEAVE_DIST_SIDE)
        line = Line(d1, dest)
        # Last point of route to "away"
        spd = self.detail.leave_speed
        td = LEAVE_DIST_AHEAD / spd
        t = ts() + LEAVE_WAIT_BEFORE + td
        tt = td
        logger.debug(f"carry forward {round(LEAVE_DIST_AHEAD, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=d1, hdg=line.bearing(), speed=spd, t=t, text=f"carry on forward ({message})")
        # "Away" to away and on the size
        spd = self.detail.leave_speed
        td = line.length() / spd
        t = t + td
        tt = tt + td
        logger.debug(f"carry sideway {round(LEAVE_DIST_SIDE, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=dest, hdg=hdg, speed=spd, t=t, text=f"leaving on the side ({message})")
        self.active = False
        logger.debug(f"cursor finish programmed ({message})")
