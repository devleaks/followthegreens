import os
import math
from datetime import datetime

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import logger
from .geo import Point, Line, distance, destination, turn
from .lightstring import XPObject


def ts() -> float:
    return datetime.now().timestamp()


class CarType:

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
            logger.debug("unloaded")

    @property
    def has_obj(self) -> bool:
        return self.obj is not None


class Cursor:
    # Linear interpolator

    def __init__(self, filename) -> None:
        self.cursor_type = CarType(filename)
        self.cursor = XPObject(None, 0, 0, 0)

        self.acceleration = 1.0  # m/s^2

        self._future = []

        self.last_time = 0
        self.curr_pos = None
        self.curr_hdg = 0
        self.curr_speed = 0
        self.curr_time = ts()

        self.target_pos = None
        self.target_hdg = 0
        self.target_speed = 0
        self.target_time = 0

        # working var for interpolation
        self.segment: Line | None = None

        self.delta_tim = 0.0
        self.delta_hdg = 0.0
        self.delta_spd = 0.0
        self.half_heading = False

        self._future_cnt = 0
        self._tick_cnt = 0
        self._total_distance = 0
        self.cnt = -1
        self.turn_limit = 1
        self.msg = ""

    def usable(self) -> bool:
        return self.cursor_type.has_obj

    def inited(self) -> bool:
        return self.curr_pos is not None

    def init(self, lat: float, lon: float, hdg: float, speed: float = 0.0):
        if not self.inited:  # only init once
            return
        self.curr_pos = Point(lat=lat, lon=lon)
        self.curr_hdg = hdg
        self.curr_speed = speed
        self.curr_time = ts()

        self.cursor.position = self.curr_pos
        self.cursor.heading = self.curr_hdg
        self.cursor.place(lightType=self.cursor_type)
        self.cursor.on()
        logger.debug(f"initialized at {round(self.curr_time, 2)}")

    def destroy(self):
        self.cursor.destroy()  # calls off()
        del self.cursor_type  # unloads object
        logger.debug("destroyed")

    def set_route(self, route):
        self.route = route

    def future(self, lat: float, lon: float, hdg: float, speed: float, t: float, tick: bool = False):
        self._future.append((lat, lon, hdg, speed, t))
        self._future_cnt += 1
        logger.debug(f"added future ({len(self._future)}): {(lat, lon, hdg, speed, t)}")
        if tick:
            ignore = self._tick()

    # def future(self, lat: float, lon: float, hdg: float, speed: float, t: float = ts()):
    #     self._set_start(self.elat, self.elon, self.ehdg, self.espd, self.et)
    #     self._set_end(lat, lon, hdg, speed, t)
    #     self._mkLine()

    def _tick(self):
        if len(self._future) == 0:
            return False
        self._tick_cnt += 1
        f = self._future[0]
        self._set_target(*f)
        del self._future[0]
        self._mkLine()
        return True

    def _set_target(self, lat: float, lon: float, hdg: float, speed: float, t: float):
        self.last_time = self.curr_time
        logger.debug(f"last time is {round(self.last_time, 2)}")
        self.target_pos = Point(lat=lat, lon=lon)
        self.target_hdg = hdg
        self.target_speed = speed
        self.target_time = t
        logger.debug(f"target time is {round(self.target_time, 2)} ({round(self.target_time-self.last_time, 2)} ahead)")

    def _mkLine(self):
        self.segment = Line(start=self.curr_pos, end=self.target_pos)
        self.delta_tim = self.target_time - self.last_time
        self.delta_hdg = turn(self.curr_hdg, self.target_hdg)  # self.curr_hdg - self.target_hdg
        self.turn_limit = 10 if abs(self.delta_hdg) < 90 else 15
        self.delta_spd = self.curr_speed - self.target_speed
        acc = 0
        if self.delta_tim != 0:
            acc = self.delta_spd / self.delta_tim
        logger.debug(f"tick {round(self.segment.length(), 1)}m in {round(self.delta_tim, 2)}s")
        logger.debug(f"heading {round(self.curr_hdg, 1)} -> {round(self.target_hdg, 1)}s (delta={round(self.delta_hdg, 1)})")
        logger.debug(f"speed {round(self.curr_speed, 1)} -> {round(self.target_speed, 1)}s (delta={round(self.delta_spd, 1)}, acc={acc})")

    def _bearing(self, ratio):
        # only turns towards the end or edge
        before_turn = distance(self.curr_pos, self.target_pos)
        if before_turn > self.turn_limit:
            return self.curr_hdg
        turn_dir = -self.delta_hdg if self.curr_hdg > self.target_hdg else abs(self.delta_hdg)
        # logger.debug(f"d={round(before_turn, 1)}, ratio={round(ratio, 1)}, rot={round(rot, 2)} (s={s}, l={limit}) => {round(ret, 1)}")
        return self.curr_hdg + (1 - before_turn / self.turn_limit) * turn_dir

    def _speed(self, ratio):
        return self.curr_speed + ratio * self.delta_spd

    def go(self, max_speed: float):
        # Go between 2 points, start from rest, end to rest, with smooth constant acceleration and deceleration
        #
        if self.curr_speed != 0 or self.target_speed != 0:
            logger.debug(f"has speed {round(self.curr_speed, 1)}, cannot go")
            return
        self.acceleration = 1.0  # m/s^2, reasonable
        time_to_maxspd = max_speed / self.acceleration
        dist_to_accell = self.acceleration * time_to_maxspd * time_to_maxspd  # m
        if 2 * dist_to_accell < self.segment.length():  # time to reach max_speed
            # Accel
            # Cruise
            dist_to_cruise = self.segment.length() - 2 * dist_to_accell
            # Decel
        else:
            maxdist = self.segment.length() / 2
            timetospeed = math.sqrt(maxdist / self.acceleration)
            # Accel
            # Decel

    def _go(self, t: float):
        self.curr_time = self.curr_time + t
        tdiff = self.curr_time - self.last_time
        speed = self.acceleration * tdiff
        self.curr_pos = destination(self.curr_pos, hdg, speed * tdiff)

    def move(self, t: float):
        # Currently: only linear interposition
        # between start and end
        # Future: d += speed * t with avg(speed) for acceleration
        def slow_debug(s):
            if self.cnt % 100 == 0:
                logger.debug(s)

        self.cnt += 1

        if self.curr_pos is None or self.target_pos is None:  # not initialized yet, no target
            slow_debug(f"not moving curr={self.curr_pos}, target={self.target_pos}")
            return
        slow_debug(f"curr_time={round(self.curr_time, 3)}, now={round(ts(), 3)}, target={round(self.target_time, 3)}")
        slow_debug(f"segment={round(self.segment.length(), 1)}m, {round(self.segment.bearing(), 0)}DEG")
        # if self.curr_speed == 0 and self.target_speed == 0:
        #     return self._go(t=t)

        if self.curr_time > self.target_time:
            self.curr_hdg = self.target_hdg
            self.curr_speed = self.target_speed
            if not self._tick():
                self.cursor.move(lat=self.curr_pos.lat, lon=self.curr_pos.lon, hdg=self.curr_hdg, elev=0.25)
                return

        self.curr_time = self.curr_time + t
        r = (self.curr_time - self.last_time) / self.delta_tim
        self.curr_pos = self.segment.middle(ratio=r)
        hdg = self._bearing(ratio=r)
        self.cursor.move(lat=self.curr_pos.lat, lon=self.curr_pos.lon, hdg=hdg, elev=0.25)

    def move_current_position(self, lat: float, lon: float, hdg: float):
        if self.curr_pos is None:
            return
        self.curr_pos.move(lat, lon, hdg)
