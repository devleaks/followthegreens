import os
import math
from dataclasses import dataclass
from datetime import datetime
from queue import Queue, Empty
from enum import StrEnum

from .ki import getTime, getDistance2

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import logger
from .geo import Point, Line, turn, destination
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


NUM_SEGMENTS = 36  # should be function of fps: high fps, make it smoother (> fps)


class Turn:

    VALID_RANGE = [30, 150]

    def __init__(self, vertex: Point, l_in: float, l_out: float, radius: float, segments: int = NUM_SEGMENTS):
        self.bearing_start = l_in
        self.bearing_end = l_out
        self.radius = radius
        self.vertex = vertex
        self.alpha = turn(l_in, l_out)
        self.direction = 1 if self.alpha > 0 else -1
        self.center = None
        self.points = []
        self.edges = []
        self._err = ""

        self.tangent_length = 0

        if abs(self.alpha) < self.VALID_RANGE[0]:
            self._err = f"turn is too shallow {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D, tangent_length={self.tangent_length}m"
            logger.debug(self._err)
            return
        if abs(self.alpha) > self.VALID_RANGE[1]:
            self._err = f"turn is too sharp {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D, tangent_length={self.tangent_length}m"
            logger.debug(self._err)
            return

        segments = NUM_SEGMENTS if segments < 1 else int(segments * radius / 10)
        opposite = 180 - self.alpha
        a2 = abs(opposite) / 2
        logger.debug(f"{round(l_in, 1)} -> {round(l_out, 1)}, alpha={round(self.alpha, 1)}, opposite={round(opposite, 1)}")
        bissec = (l_in + self.alpha / 2 + (self.direction * 90)) % 360
        a2r = math.radians(a2)
        a2sin = math.sin(a2r)
        if a2sin == 0:
            self._err = "turn is 0D (no turn) or 180D (U turn), ignored"
            logger.debug(self._err)
            return

        dist_center = radius / a2sin
        self.tangent_length = abs(dist_center * math.cos(a2r))  # cos may be < 0

        if self.tangent_length > (3 * radius):
            self._err = f"turn is too sharp {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D, tangent_length={round(self.tangent_length, 1)}m"
            logger.debug(self._err)
            return

        self.center = destination(vertex, bissec, dist_center)
        self.length = 2 * math.pi * radius * (abs(self.alpha) / 360)  # turn length

        step = self.alpha / segments
        last = None
        for i in range(segments + 1):
            pt = destination(self.center, l_in - (self.direction * 90) + i * step, radius)
            if last is not None:
                self.edges.append(Line(last, pt))
                last = pt
            self.points.append((pt, l_in + i * step))

        logger.debug(
            f"radius={round(radius, 1)}m, vtx to center={round(dist_center, 1)}m, tangent length={round(self.tangent_length, 1)}m, turn length={round(self.length, 1)}m, {len(self.points)} points"
        )
        # fc = FeatureCollection(features=[p[0].feature() for p in self.points])
        # fn = os.path.join(os.path.dirname(__file__), "..", f"turn.geojson")  # {randint(1000,9999)}
        # fc.save(fn)

    @property
    def valid(self) -> bool:
        return len(self.points) > 0

    @property
    def error(self) -> str:
        return self._err if type(self._err) is str else ""

    @property
    def start(self) -> Point:
        return self.points[0][0] if self.valid else None

    @property
    def end(self) -> Point:
        return self.points[-1][0] if self.valid else None

    def progress(self, dist: float) -> tuple:
        # dist from start of turn
        if dist > self.length:
            return self.points[-1][0], self.points[-1][1], True
        portion = dist / self.length
        idx = min(round(portion * len(self.points)), len(self.points) - 1)  # not int==math.floor
        # logger.debug(f"turn {round(dist, 1)}m -> index={idx}/{len(self.points)-1}")
        return self.points[idx][0], self.points[idx][1], False

    def progressiveTurn(self, length: float, segments: int = NUM_SEGMENTS, min_turn: float = 3.0) -> list:
        if abs(self.alpha) < min_turn:
            return []
        numsegs = int(NUM_SEGMENTS / 2)
        part = length / numsegs
        parta = self.alpha / numsegs
        points = []
        for i in range(numsegs):
            d = length - i * part
            pt = destination(self.vertex, self.bearing_start + 180, d)
            b = self.bearing_start + i * parta
            points.append((pt, b))
        mid = self.bearing_start + self.alpha / 2
        for i in range(numsegs):
            d = i * part
            pt = destination(self.vertex, self.bearing_end, d)
            b = mid + i * parta
            points.append((pt, b))
        pt = destination(self.vertex, self.bearing_end, length)
        points.append((pt, self.bearing_end))
        return points


STATIC_TURN_LIMIT = 10.0  # m


class PartialPath:

    def __init__(self, segment: Line, turn_end: Turn, v_start: float | None, v_end: float | None, t: float = 0.0) -> None:
        self._valid = True
        self.turn_end = turn_end
        self.segment = segment
        self.segment_bearing = segment.bearing()  # compute it once, cache it
        self.total_length = segment.length()
        logger.debug(f"segment length={round(self.total_length, 1)}m, bearing={round(self.segment_bearing, 0)}D")

        if v_start is None:
            logger.warning("starting speed of path should not be null, assuming 0.0m/s")
            v_start = 0.0
        self.v_start = v_start

        self.v_end = v_end
        if v_end is None:  # do not change speed
            self.v_end = self.v_start

        if self.v_end == 0:
            self.decelerate = -1

        self.time_start = t
        self.start = self.segment.start
        self.end = self.segment.end
        self.before_turn = self.total_length

        if self.turn_end_valid:
            if self.total_length < self.turn_end.tangent_length:
                self._valid = False
                logger.debug(f"segment length ({round(self.total_length, 1)}m) shorter than turn tangents ({round(self.turn_end.tangent_length, 1)}m)")
            else:
                self.total_length = self.total_length - self.turn_end.tangent_length
                self.before_turn = self.total_length
                logger.debug(f"effective length remove next turn start ({round(self.turn_end.tangent_length, 1)}m) -> {round(self.total_length, 1)}m")
                self.total_length = self.total_length + self.turn_end.length
                self.end = self.turn_end.end
                logger.debug(f"effective length add next turn length ({round(self.turn_end.length, 1)}m) -> {round(self.total_length, 1)}m")
        else:
            if self.before_turn > STATIC_TURN_LIMIT:
                self.before_turn = self.before_turn - STATIC_TURN_LIMIT
            logger.debug("no end turn")

        # CASES
        self.speed_max = CursorObject.DEFAULT_SPEED
        self.speed = v_start  # current speed of cursor at start of path

        self.accel_start = 0
        self.accel_end = 0
        self.total_time = -1

        # self.prepareSpeeds()

        # Fallback
        if self.v_start == 0:
            self.v_start = CursorObject.DEFAULT_SPEED
            logger.debug(f"fallback set initial speed to {self.v_start}")
        if self.v_end == 0:
            self.v_end = CursorObject.DEFAULT_SPEED
            logger.debug(f"fallback set final speed to {self.v_end}")

        if self.total_time == -1:
            self.total_time = getTime(displacement=self.total_length, initial_velocity=self.v_start, final_velocity=self.v_end)
            logger.debug(f"fallback set total time to {round(self.total_time, 1)}s")

        self.time_end = self.time_start + self.total_time
        logger.debug(self.desc())

    @property
    def valid(seft) -> bool:
        return self._valid

    @property
    def turn_end_valid(self):
        return self.turn_end is not None and self.turn_end.valid

    def desc(self) -> str:
        return f"length={round(self.total_length, 1)}m, time={round(self.total_time, 2)}secs, turn at end={self.turn_end_valid}, before turn={round(self.before_turn, 1)}m"

    # def prepareSpeeds(self):
    #     #
    #     # CURRENTLY UNUSED
    #     #
    #     if self.v_start > 0 and self.v_end > 0 and abs(self.v_start - self.v_end) < 2:  # approximate constant speed
    #         avg = (self.v_start + self.v_end) / 2
    #         self.v_start = avg
    #         self.v_end = avg
    #         self.accel_start = 0
    #         self.accel_dist = 0
    #         self.accel_end = 0
    #         self.total_time = getTime(displacement=self.total_length, initial_velocity=self.v_start, final_velocity=self.v_end)
    #         logger.debug(f"almost constant speed ({round(self.v_start, 1)}, {round(self.v_end, 1)}) v={avg}, d={round(self.total_length, 1)}, t={round(self.total_time, 1)}")

    #     elif self.v_start > 0 and self.v_end > 0:  # constant acceleration
    #         self.total_time = getTime(displacement=self.total_length, initial_velocity=self.v_start, final_velocity=self.v_end)
    #         logger.debug(f"constant acceleration {round(self.v_start, 1)} -> {round(self.v_end, 1)} d={round(self.total_length, 1)}, t={round(self.total_time, 1)}")

    #     elif self.v_start == 0 and self.v_end > 0:  # accelerate to v_end, then remain constant
    #         # 1. accelerate to final speed
    #         self.accel_dist = getDistance(initial_velocity=0.0, final_velocity=self.v_end, acceleration=CursorObject.DEFAULT_ACCELERATION)
    #         self.accel_start = getTime(displacement=self.accel_dist, initial_velocity=0.0, final_velocity=self.v_end)
    #         # 2. move at constant speed
    #         d_left = self.total_length - self.accel_dist
    #         if d_left > 0:
    #             logger.debug(f"eq2: displacement={round(d_left, 1)}m, initial_velocity={round(self.v_end, 1)}, final_velocity={round(self.v_end, 1)}, time=None")
    #             r = eq2(displacement=d_left, initial_velocity=self.v_end, final_velocity=self.v_end, time=None)
    #             logger.debug(f"eq2: {r}")
    #             self.total_time = r[3] + self.accel_start
    #             logger.debug(f"acceleration to {round(self.v_end, 1)} ta={round(self.accel_start, 1)} d={round(self.total_length, 1)}, t={round(self.total_time, 1)}")
    #         else:
    #             logger.debug(f"distance {round(self.total_length, 1)}m insufficiant to accelerate to {self.v_end} (need {round(d, 1)}m)")

    #     elif self.v_start > 0 and self.v_end == 0:  # remain constant as long as possible then decelerate to 0
    #         # 2. decelerate
    #         d = getDistance(initial_velocity=self.v_start, final_velocity=0.0, acceleration=-CursorObject.DEFAULT_ACCELERATION)
    #         self.accel_end = getTime(displacement=d, initial_velocity=self.v_start, final_velocity=0.0)
    #         # 1. move at constant speed
    #         d_left = self.total_length - d
    #         if d_left > 0:
    #             self.total_time = getTime(displacement=d_left, initial_velocity=self.v_start, final_velocity=self.v_start) + self.accel_end
    #             logger.debug(f"deceleration from {round(self.v_start, 1)} td={round(self.accel_end, 1)} d={round(self.total_length, 1)}, t={round(self.total_time, 1)}")
    #         else:
    #             logger.debug(f"distance {round(self.total_length, 1)}m insufficiant to decelerate from {self.v_start} (need {round(d, 1)}m)")

    #     else:  # self.v_start == 0 and self.v_end == 0:  # accelerate to max_speed, remain at max_speed as long as possible then decelerate to 0
    #         # 1. accelerate to final speed
    #         d1 = getDistance(initial_velocity=0.0, final_velocity=self.speed_max, acceleration=CursorObject.DEFAULT_ACCELERATION)
    #         self.accel_start = getTime(displacement=d1, initial_velocity=0.0, final_velocity=self.speed_max)
    #         # 3. decelerate
    #         # d2 = getDistance(initial_velocity=self.speed_max, final_velocity=0.0, acceleration=-CursorObject.DEFAULT_ACCELERATION)
    #         # self.accel_end = getTime(displacement=d2, initial_velocity=self.speed_max, final_velocity=0.0)
    #         d2 = d1  # symmetric
    #         self.accel_end = self.accel_start  # symmetric
    #         # 2. move at constant speed
    #         d_left = self.total_length - d1 - d2
    #         if d_left > 0:
    #             self.total_time = getTime(displacement=d_left, initial_velocity=self.speed_max, final_velocity=self.speed_max) + self.accel_start + self.accel_end
    #             logger.debug(f"acceleration to {round(self.speed_max, 1)} ta={round(self.accel_start, 1)} constant speed={round(self.speed_max, 1)}, dc={round(d_left, 1)}")
    #             logger.debug(f"deceleration from {round(self.speed_max, 1)} td={round(self.accel_end, 1)} d={round(self.total_length, 1)}, t={round(self.total_time, 1)}")
    #         else:
    #             logger.debug(f"distance {round(self.total_length, 1)}m insufficiant to accelerate and decelerate to/from {self.speed_max} (need {round(d1+d2, 1)}m)")

    # def progressAccel(self, t: float):
    #     if self.accel_start == 0 and self.accel_end == 0:  # constant speed
    #         return self.progress(t)
    #     d = 0
    #     dt = t - self.time_start
    #     if dt <= self.accel_start:  # need to accelerate
    #         d = getDistance3(initial_velocity=self.v_start, acceleration=CursorObject.DEFAULT_ACCELERATION, time=dt)
    #     elif self.accel_end > 0 and dt >= (self.total_time - self.accel_end):  # need to accelerate/decelerate at end
    #         d1 = self.v_start * (self.total_time - self.accel_end)
    #         dt2 = self.total_time - dt
    #         d2 = getDistance3(initial_velocity=self.v_start, acceleration=-CursorObject.DEFAULT_ACCELERATION, time=dt2)
    #         d = d1 + d2
    #     else:  # constant but with speed after accel_start
    #         if self.accel_start == 0:
    #             d = self.v_start * dt
    #         else:
    #             d1 = getDistance3(initial_velocity=self.v_start, acceleration=CursorObject.DEFAULT_ACCELERATION, time=self.accel_start)
    #             d2 = self.v_end * (dt - self.accel_start)
    #             d = d1 + d2
    #     h = self.segment_bearing  # not correct if turn at the end, will correct later, good for now
    #     p = destination(self.start, h, d)
    #     return p, h, False

    def progressBearing(self, before_turn, turn_limit: float = STATIC_TURN_LIMIT):
        # only turns towards the end or edge
        # logger.debug(
        #     f"{round(self.turn_end.bearing_start, 1)} -> {round(self.turn_end.bearing_end, 1)} ({round(self.turn_end.alpha, 1)}): {round(before_turn, 1)} => {round(self.turn_end.bearing_start + self.turn_end.alpha * before_turn / turn_limit, 1)}"
        # )
        return self.turn_end.bearing_start + self.turn_end.alpha * before_turn / turn_limit

    def progress(self, t: float) -> tuple:
        # return position and heading t seconds after started on path
        if not self.turn_end_valid:
            if t > self.time_end:  # this path is finished
                # logger.debug("finished (no turn)")
                return self.end, self.segment_bearing, True
            dt = t - self.time_start
            d = getDistance2(initial_velocity=self.v_start, final_velocity=self.v_end, time=dt)
            # logger.debug(f"eq2: {r}")
            h = self.segment_bearing
            p = destination(self.start, h, d)
            if d > self.before_turn and d <= self.total_length:
                h = self.progressBearing(before_turn=d - self.before_turn)
            # logger.debug(f"path {round(dt, 3)}s -> {round(d, 1)}m, {round(h, 0)}D")
            return p, h, False
        # has a turn at the end
        if t > self.time_end:  # this path is finished
            # logger.debug("finished (with turn)")
            return self.end, self.turn_end.bearing_end, True
        dt = t - self.time_start
        d = getDistance2(initial_velocity=self.v_start, final_velocity=self.v_end, time=dt)
        if d < self.before_turn:
            h = self.segment_bearing
            p = destination(self.start, h, d)
            # logger.debug(f"path {round(dt, 3)}s -> {round(d, 1)}m, {round(h, 0)}D")
            return p, h, False
        d0 = d
        d = d - self.before_turn
        # logger.debug(f"path {round(dt, 3)}s -> {round(d0, 1)}m, -> turn {round(d, 1)}m")
        return self.turn_end.progress(dist=d)


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
        self._future = Queue()  # Queue element: tuple(lat: float, lon: float, hdg: float, speed: float, t: float, last_speed: float, text: str)
        self.last_future_speed = 0

        self.last_time = 0
        self.curr_pos = None
        self.curr_hdg = 0
        self.curr_speed = 0
        self.curr_last_speed = 0
        self.curr_time = ts()
        self.curr_text = ""
        self.curr_turn = None
        self.curr_index = 0  # where we are now
        self.curr_dist = 0

        self.target_pos = None
        self.target_hdg = 0
        self.target_speed = 0
        self.target_last_speed = 0
        self.target_time = 0
        self.target_text = ""
        self.target_turn = None
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

        acf_speed = ftg.aircraft.speed()
        closestLight, dist = ftg.lights.closest(ftg.aircraft.position())
        if closestLight is None:
            logger.debug("no close light to start")
            closestLight = 0

        # if route changed we assume aircraft is moving and this.inited
        ahead = ftg.flightLoop.adjustAhead(acf_speed=acf_speed, ahead_range=ftg.flightLoop.ahead_range)
        join_time = 20  # secs, reasonable time from spawn position to ahead of acf
        acf_ahead = min(acf_speed, self.cursor_object.FAST_SPEED) * join_time
        ahead_at_join = acf_ahead + ahead
        light_ahead, light_index, dist_left = ftg.lights.lightAhead(index_from=closestLight, ahead=ahead_at_join)
        join_route = Line(start=self.curr_pos, end=light_ahead.position)
        initial_speed = join_route.length() / join_time
        self.curr_speed = initial_speed
        self.curr_hdg = join_route.bearing()
        dt = ts() + join_time
        # we will move the car well ahead, the car should not backup
        # aircraft will move acf_ahead ahead of closestLight, or acf_ahead/lights.distance_between_green_lights lights
        logger.debug(
            f"..move on route at {round(ahead_at_join, 1)}m ahead, heading={round(join_route.bearing(), 0)}, in {round(join_time, 1)}s (aircraft will be at light index {self.light_progress}).."
        )
        self.light_progress = closestLight + int(ahead / ftg.lights.distance_between_green_lights)
        # we move the car in front of acf, and progress at same speed as acf.
        self.future(position=join_route.end, hdg=light_ahead.heading, speed=acf_speed, t=dt, tick=True, text="go on route ahead of aircraft after new route")
        # finally, we have to tell future_index() where car is when it join route
        # so that when move() catches up with future_index() it will start from there
        # (after above future)
        self.set_target_index(edge=light_ahead.edgeIndex, dist=light_ahead.distFromEdgeStart)
        logger.debug("..route changed, already taxiing")

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

    def _tick(self) -> bool:
        # returns whether it ticked
        if self._future.empty():
            if self.status == CURSOR_STATUS.FINISHING:
                self.status = CURSOR_STATUS.FINISHED
                logger.debug("cursor finished")
            return False
        try:
            f = self._future.get(block=False)  # (lat: float, lon: float, hdg: float, speed: float, t: float, edge: int, last_speed: float, text: str)
            self._qout += 1  #                    0           1           2           3             4         5          6                  7
            logger.debug(f"tick future ({self._qout}, q={self._future.qsize()}) at {st(self.curr_time)}: {f[-1]} (h={round(f[2], 0)}D, s={f[3]}, (ls={f[6]}) t={st(f[4])})")
            if self._set_target(*f):
                self._mkPathToTarget()
                if self.status == CURSOR_STATUS.READY:
                    self.status = CURSOR_STATUS.ACTIVE
                return True
        except Empty:
            pass
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
        displaced_start = self.curr_pos
        if self.path is not None:  # only first time
            displaced_start = self.path.end
            if self.path.turn_end_valid:
                self.curr_dist = self.path.turn_end.tangent_length  # moved at least at end of turn
            logger.debug(f"displaced start at end of path, {round(self.curr_dist, 1)}m ahead of start vertex of edge {self.curr_index}")
            d = self.route.from_edge(i=self.curr_index, position=self.target_pos)
            logger.debug(f"target position {round(self.curr_dist, 1)}m ahead start vertex of edge {self.curr_index}")
            if d < self.curr_dist:
                logger.debug(f"cannot backup on current edge ({round(d, 1)}m < {round(self.curr_dist, 1)}m)")
                return
        else:
            logger.debug("first path, start from initial position")
        segment = Line(start=displaced_start, end=self.target_pos)
        self.curr_turn = self.target_turn
        # if isintance(self.target_pos, Vertex):
        #   self.target_turn = self.route.smoothTurn[self.target_pos.id]  # precomputed
        r = self.detail.turn_radius
        if self.curr_speed > self.detail.normal_speed:
            r = 1.5 * r
        self.target_turn = Turn(vertex=self.target_pos, l_in=self.curr_hdg, l_out=self.target_hdg, radius=r)
        self.path = PartialPath(segment=segment, turn_end=self.target_turn, v_start=self.curr_speed, v_end=self.target_speed, t=self.curr_time)  # movement
        if self.target_time < self.path.time_end:
            t = self.path.time_end - self.target_time
            self.target_time = self.path.time_end
            logger.debug(f"new target time {st(self.target_time)} ({round(t, 1)}s later)")
        else:
            t = self.target_time - self.path.time_end
            self.target_time = self.path.time_end
            logger.debug(f"target time is ahead, would wait {round(t, 1)}s.. adjusted, will not wait")

    def nextPosition(self):
        if self.path is not None:
            return self.path.progress(self.curr_time)
        return self.curr_pos, self.curr_hdg, True

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
        spd = self.cursor_object.LEAVE_SPEED
        td = LEAVE_DIST_AHEAD / spd
        t = ts() + LEAVE_WAIT_BEFORE + td
        tt = td
        logger.debug(f"carry forward {round(LEAVE_DIST_AHEAD, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=d1, hdg=line.bearing(), speed=spd, t=t, text=f"carry on forward ({message})")
        # "Away" to away and on the size
        spd = self.cursor_object.LEAVE_SPEED
        td = line.length() / spd
        t = t + td
        tt = tt + td
        logger.debug(f"carry sideway {round(LEAVE_DIST_SIDE, 1)}m in {round(td, 1)}s heading {round(hdg, 0)}D")
        self.future(position=dest, hdg=hdg, speed=spd, t=t, text=f"leaving on the side ({message})")
        self.active = False
        logger.debug(f"cursor finish programmed ({message})")
