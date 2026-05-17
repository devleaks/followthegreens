# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
from __future__ import annotations
from abc import ABC, abstractmethod
import os
import math
from enum import StrEnum
from datetime import datetime
from dataclasses import dataclass, fields

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import (
    logger,
    minsec,
    MOVEMENT,
    TOO_FAR,
    ROUTING_ALGORITHM,  # not open as a preference "yet"
    ROUTING_ALGORITHMS,
)
from .geo import GEOJSON, FeatureCollection, Point, Line, destination, distance, bearing, turn

SYSTEM_DIRECTORY = "."

# Turn data
TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line, no slow down
SMALL_TURN_LIMIT = 15.0  # °, above this angle, it is recommended to slow down for the turn
NUM_SEGMENTS = 36  # default number of segments for a smooth turn, will be adjusted for turn size, radius and speed
TURN_RADIUS = 25.0
TURN_SPEED = 10.0


class SMOOTH_ROUTE(StrEnum):
    INDEX = "srIndex"  # smooth route index
    ROUTE_INDEX = "srRouteIndex"  # corresponding route index
    DISTANCE = "srDistance"
    BEARING = "srBearing"
    TOTAL = "srTotal"  # accumulator of distance on smooth route
    REVERSE_INDEX = "srRevRouteIndex"  # on *route*, index of smooth route corresponding vertex
    REFERENCE_VERTEX = "srRefVtxIdx"  # Original vertex of route index (vertex id in graph)
    SEGMENT_LENGTH = "srSegLen"  # length of route segment on smooth route
    TURN_START = "srTurnStart"
    TURN_MIDDLE = "srTurnMid"
    TURN_TYPE = "turn-type"  # smooth, progressive, or immediate
    TURN_END = "srTurnEnd"
    TURN_ALPHA = "turn-alpha"
    TURN_TANGENT = "turn-tangent"
    TURN_VALID = "turn-valid"


class TURN_TYPE(StrEnum):
    SMOOTH = "smooth"  # smooth route index
    PROGRESSIVE = "progressive"  # corresponding route index
    IMMEDIATE = "immediate"


NOT_ON_ROUTE = -1


@dataclass
class OnRoute:
    """Position on route, expressed as vertex and distance AFTER that vertex on route"""

    index: int = NOT_ON_ROUTE  # vertex index on route
    distance: float = 0.0  # distance "forward" from above index
    route: tuple = tuple()  # pointer to route
    name: str = ""  # for debugging

    def __str__(self):
        """Returns a string containing only the non-default field values."""
        # https://stackoverflow.com/questions/71344648/how-to-define-str-for-dataclass-that-omits-default-values

        def f(i):
            if type(i) in [list, tuple] and len(i) > 0 and isinstance(i[0], Point):
                return f"[ route[{len(i)}] ]"
            return f"{round(i, 1)}m" if type(i) is float else i

        s = ", ".join(f"{field.name}={f(getattr(self, field.name))!r}" for field in fields(self))
        return f"{type(self).__name__}({s})"

    @staticmethod
    def fromLight(light, route, name: str = ""):
        return OnRoute(index=light.srIndex, distance=light.distFromsrIndex, route=route, name=name)

    @property
    def has_route(self) -> bool:
        return self.route is not None and len(self.route) > 0

    @property
    def on_route(self) -> bool:
        return self.index != NOT_ON_ROUTE

    @property
    def vertex(self) -> Point:
        return self.route[self.index]

    @property
    def bearing(self) -> float:
        return self.vertex.getProp(SMOOTH_ROUTE.BEARING.value)

    @property
    def edge_length(self) -> float:
        l = self.vertex.getProp(SMOOTH_ROUTE.DISTANCE.value)
        if self.distance > l:
            logger.warning(f"distance larger than edge length {self}")
        return l

    @property
    def to_next(self) -> float:
        return self.edge_length - self.distance

    @property
    def point(self) -> Point:
        # Point at position
        if self.distance > self.edge_length:
            logger.warning(f"distance larger than edge length {self}")
        return destination(src=self.vertex, brngDeg=self.bearing, d=self.distance)

    def after(self, target: OnRoute) -> bool:
        return self.reached(target=target)

    def before(self, target: OnRoute) -> bool:
        return not self.reached(target=target)

    def at(self, target: OnRoute, margin: float = 1.0) -> bool:
        # margin, distances, in meter
        return self.distanceTo(target=target) < margin

    def reached(self, target: OnRoute, dist: float = 0.0) -> bool:
        # Means self is at or after target, could be called .after(target)
        if not self.has_route:
            logger.warning("no route")
            return False

        if not target.has_route:
            logger.warning("no target route")
            return False

        if not self.on_route:
            logger.warning("not on route")
            return False

        if self.route != target.route:
            logger.warning(f"not on same route {self.name} vs {len(target.name)}")
            return False

        t2 = target
        if dist > 0:
            t2 = self.forward(dist=dist)
        elif dist < 0:
            t2 = self.backward(dist=dist)
        # logger.debug(f"{target} - {dist} = {t2}")

        r = False
        if self.index > t2.index:
            r = True
        elif self.index == t2.index and self.distance >= t2.distance:
            r = True
        # logger.debug(f"{r}: {self} {'>=' if r else '<'} {t2}")
        return r

    def distanceTo(self, target: OnRoute) -> float:
        # always positive
        if self.route is None or target.route is None:
            logger.debug("no route")
            return 0.0
        if self.index == target.index:
            return abs(self.distance - target.distance)
        if self.index > target.index:
            return target.distanceTo(self)
        # self is "before" target
        total = self.to_next  # left on current segment
        i = self.index + 1
        while i < target.index and i < len(self.route):
            total += self.route[i].getProp(SMOOTH_ROUTE.DISTANCE.value)
            i += 1
        total += target.distance  # left on i2
        return total

    def forward(self, dist: float) -> OnRoute:
        t = self.distance + dist
        if t < self.edge_length:
            return OnRoute(index=self.index, distance=t, route=self.route)
        i = self.index + 1
        if i >= len(self.route):  # end reached
            logger.debug("at end of route")
            return OnRoute(index=len(self.route) - 1, distance=0.0, route=self.route)
        left = self.edge_length - self.distance
        next_or = OnRoute(index=i, distance=0.0, route=self.route)
        return next_or.forward(dist=dist - left)

    def backward(self, dist: float) -> OnRoute:
        if dist <= self.distance:
            return OnRoute(index=self.index, distance=self.distance - dist, route=self.route)
        if self.index <= 0:  # begining of route since dist > distance
            logger.debug("at begining of route")
            return OnRoute(index=0, distance=0.0, route=self.route)
        i = self.index - 1
        d = self.route[i].getProp(SMOOTH_ROUTE.DISTANCE)
        next_or = OnRoute(index=i, distance=d, route=self.route)  # == OnRoute(index=self.index, distance=0.0, route=self.route)
        return next_or.backward(dist=dist - self.distance)


class Vehicle(ABC):
    # ABC for Aircraft and Follow Me car since they share/face common properties and tasks
    #
    # - Position, heading, speed,
    # - Started, stopped, moving,
    # - Next (mandatory) stop, status of stop
    # - Info like: closest light
    # - Properties of vehicle: sizes, distance to brake to stop, "warning distance", acceleration, deceleration
    #

    @abstractmethod
    def position(self) -> tuple:
        raise NotImplementedError

    def position_point(self) -> Point:
        return Point(*self.position())

    @abstractmethod
    def speed(self) -> float:
        raise NotImplementedError

    @abstractmethod
    def warningDistance(self, target: float = 0.0) -> float:
        raise NotImplementedError

    def closestLight(self, lights) -> tuple:
        return lights.closest(self.position())

    def nextTurn(self, ftg, closestLight: int) -> tuple:
        # Returns distance, turn angle
        # 1. next vertex
        route = ftg.lights.route
        light = ftg.lights.lights[closestLight]
        next_vertex = light.edgeIndex + 1
        if next_vertex >= len(route.route):  # end of route
            next_vertex = len(route.route) - 1
            logger.debug("end of route")
        nextvtxid = route.route[next_vertex]
        nextvtx = route.graph.get_vertex(nextvtxid)

        # 2. distance to that next vertex and turn at that vertex
        pos = self.position()
        dist_from_vehicle_to_next_vtx = distance(Point(lat=pos[0], lon=pos[1]), nextvtx)
        turn_angle = route.turns[light.edgeIndex]

        TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line
        idx = next_vertex
        while abs(turn_angle) < TURN_LIMIT and idx < len(route.turns):
            turn_angle = route.turns[idx]
            idx = idx + 1
        if idx >= len(route.route):  # end of route
            idx = len(route.route) - 1
            logger.debug("end of route")
        dist_from_next_vtx_to_next_turn = 0 if abs(route.turns[next_vertex]) > TURN_LIMIT else route.dtb[next_vertex]

        # 3. packing summary
        dist_before_turn = dist_from_vehicle_to_next_vtx + dist_from_next_vtx_to_next_turn
        return dist_before_turn, turn_angle

    def nextStop(self, ftg, closestLight: int) -> tuple:
        # Returns light index, distance, whether next stop cleared
        light_index, distance_to_stop = ftg.lights.toNextStop(self.position())
        return light_index, distance_to_stop, ftg.lights.stopCleared(nextStop=light_index)


class Turn:

    SMALL_TURN_TANGENT = 10.0  # m
    VALID_RANGE = [15, 140]  # for a smooth turn
    MAX_TANGENT = 35.0  # m

    def __init__(self, vertex: Point, l_in: float, l_out: float, radius: float = TURN_RADIUS, segments: int = NUM_SEGMENTS):
        self.bearing_start = l_in
        self.bearing_end = l_out
        self.radius = radius
        self.vertex = vertex
        self.alpha = turn(l_in, l_out)
        self.direction = 1 if self.alpha > 0 else -1
        self.center = None
        self.points = []
        self.edges = []

        self.tangent_length = 0

        if abs(self.alpha) < self.VALID_RANGE[0]:
            logger.debug(f"turn is too shallow {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D, tangent_length={self.tangent_length}m")
            return

        numsegs = NUM_SEGMENTS if segments < 2 else int(segments * radius / 10)
        opposite = 180 - self.alpha
        a2 = abs(opposite) / 2
        # logger.debug(f"{round(l_in, 1)} -> {round(l_out, 1)}, alpha={round(self.alpha, 1)}, opposite={round(opposite, 1)}")
        bissec = (l_in + self.alpha / 2 + (self.direction * 90)) % 360
        a2r = math.radians(a2)
        a2sin = math.sin(a2r)
        if a2sin == 0:
            logger.debug("turn is 0D (no turn) or 180D (U turn), ignored")
            return

        exception = False
        if abs(self.alpha) > self.VALID_RANGE[1]:
            logger.debug(f"turn is sharp {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D")
            r = abs(self.MAX_TANGENT * a2sin / math.cos(a2r))
            logger.debug(f"max tangent={round(self.MAX_TANGENT,1)}m requires radius={round(r,1)}m")
            radius = r
            exception = True

        dist_center = radius / a2sin
        self.tangent_length = abs(dist_center * math.cos(a2r))  # cos may be < 0
        if not exception and self.tangent_length > (2 * radius):  # or self.tangent_length > MAX_TANGENT
            logger.debug(
                f"turn is too sharp {round(l_in, 1)} -> {round(l_out, 1)} : {round(self.alpha, 1)}D, tangent_length={round(self.tangent_length, 1)}m, radius={round(radius,1)}m"
            )
            # Try to reduce radius
            radius = abs(self.MAX_TANGENT * a2sin / math.cos(a2r))
            dist_center = radius / a2sin
            self.tangent_length = self.MAX_TANGENT
            logger.debug(f"turn is too sharp attempt to reduce to tangent_length={round(self.tangent_length, 1)}m, radius={round(radius,1)}m")

        self.radius = radius
        self.center = destination(vertex, bissec, dist_center)
        self.length = 2 * math.pi * radius * (abs(self.alpha) / 360)  # turn length

        step = self.alpha / numsegs
        last = None
        for i in range(numsegs + 1):
            pt = destination(self.center, l_in - (self.direction * 90) + i * step, radius)
            if last is not None:
                self.edges.append(Line(last, pt))
                last = pt
            self.points.append((pt, l_in + i * step))

        logger.debug(
            f"alpha={round(self.alpha, 1)}, radius={round(radius, 1)}m, vtx to center={round(dist_center, 1)}m, tangent length={round(self.tangent_length, 1)}m, turn length={round(self.length, 1)}m, {len(self.points)} points"
        )

    @property
    def valid(self) -> bool:
        return len(self.points) > 0

    @property
    def start(self) -> Point:
        return self.points[0][0] if self.valid else None

    @property
    def end(self) -> Point:
        return self.points[-1][0] if self.valid else None

    # def progress(self, dist: float) -> tuple:
    #     # dist from start of turn
    #     if dist > self.length:
    #         return self.points[-1][0], self.points[-1][1], True
    #     portion = dist / self.length
    #     idx = min(round(portion * len(self.points)), len(self.points) - 1)  # not int==math.floor
    #     # logger.debug(f"turn {round(dist, 1)}m -> index={idx}/{len(self.points)-1}")
    #     return self.points[idx][0], self.points[idx][1], False

    def progressiveTurn(self, length: float, segments: int = NUM_SEGMENTS, min_turn: float = 3.0) -> list:
        # Build alternate list of (points, heading) without a turn (stay on edge(s), progressive heading changes, appears to be turning)
        if abs(self.alpha) < min_turn:
            logger.debug(f"turn {round(self.alpha, 1)}D too small")
            return []
        numsegs = int(segments / 2)
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
        logger.debug(f"length={round(length, 1)}m, turn={round(self.alpha, 1)}D, {len(points)} points")
        return points


class Route:
    # Container for route from src to dst on graph
    def __init__(self, graph):
        self.graph = graph
        self.route = []
        self.algorithm = ROUTING_ALGORITHM  # default, unused

        self.precise_start = None
        self.precise_end = None

        self.departure_runway = None
        self.arrival_runway = None

        # working vars
        self.move = None
        self.vertices = None
        self.edges = None
        self.turns = None
        self.dtb = None  # Distance To Brake (distance before reason to brake)
        self.dtb_at = None
        self.dleft = []
        self.tleft = []

        self.smoothRoute = []  # === vertices
        # smooth route equivalents: fetch with getProp()
        # edges === no equivalent, but distance to next = DISTANCE, bearing to next = BEARING
        # turns ===
        # dtb ===
        # dtb_at ===
        # dleft ===
        # tleft ===

        self.idxcache = 0  # progress on smooth route, cannot backup
        self._srcnt = 0
        self._srscan = 0
        self._srrecurr = 0

    def __str__(self):
        if self.found():
            return "-".join(self.route)
        return ""

    def features(self) -> list:
        features = []
        for i in range(len(self.route) - 1):
            v = self.graph.get_vertex(self.route[i])
            v.setProp("index", i)
            v.setProp("turn", self.turns[i])
            v.setProp("remaining", self.dleft[i])
            v.setProp("remaining_time", self.tleft[i])
            v.setProp("tobrake", self.dtb[i])
            v.setProp("tobrake_index", self.dtb_at[i])
            f = v.feature()
            f["properties"][GEOJSON.MARKER_SIZE.value] = "medium"
            if abs(self.turns[i]) > TURN_LIMIT:
                f["properties"][GEOJSON.MARKER_COLOR.value] = "#006600"  # dark green
            else:
                f["properties"][GEOJSON.MARKER_COLOR.value] = "#00AA00"  # green
            features.append(f)
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            e.setProp("index", i)
            features.append(e.feature())
        return features

    def _find(self, src, dst) -> bool:
        # If requested to try AStar, try it first, if failed, try Dijkstra
        # If Dijstra fails, we really can't do anything about it.
        if self.algorithm == ROUTING_ALGORITHMS.ASTAR:
            self.route = self.graph.AStar(src, dst)
            if self.found():
                return True
            logger.info(f"..failed to find route using algorithm {self.algorithm}, will try algorithm Dijkstra..")
        self.route = self.graph.Dijkstra(src, dst)
        return self.found()

    def found(self) -> bool:
        return self.route is not None and len(self.route) > 2

    def baseline(self, idx: int = 0) -> tuple:
        # Returns distance and time left at route index
        if len(self.dleft) > 0 and len(self.tleft) > 0:
            return self.dleft[idx], self.tleft[idx]
        return 0, 0

    def beforeRoute(self):
        # Original point to first vertex
        return Line(start=self.precise_start, end=self.vertices[0])

    def afterRoute(self):
        # Last vertex to destination
        return Line(start=self.vertices[-1], end=self.precise_end)

    def orientLastVertex(self) -> float:
        return self.departure_runway.bearing() if self.move == MOVEMENT.DEPARTURE and self.departure_runway is not None else self.edges_orient[-1]

    def mkEdges(self):
        # From liste of vertices, build list of edges
        # but also set the size of the taxiway in the vertex
        # note: edges[k] starts at vertices[k]
        self.edges = []
        self.edges_orient = []  # True: start->end, False: end->start
        for i in range(len(self.route) - 1):
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            v = self.graph.get_vertex(self.route[i])
            if v is None:
                logger.debug(f"{self.route[i]} not in {self.graph.vert_dict.keys()}")
            v.setProp("taxiway-width", e.width_code.value if e.width_code is not None else "-")
            v.setProp("ls", i)
            self.edges.append(e)
            self.edges_orient.append(e.bearing(orig=v))
        # self.edges_orient.append(self.orientLastVertex())  # ??
        logger.debug(f"route (vtx): {self}.")
        logger.debug("route (edg): " + "-".join([e.name for e in self.edges]))
        logger.debug("route: " + self.text())
        logger.debug(f"segment lengths: {[round(e.cost, 1) for e in self.edges]}")
        # Cumulative distance left to taxi
        # at vertex i, there is dleft[i] meter left to taxi
        total = 0
        self.dleft = []
        for i in range(len(self.route) - 1, 0, -1):
            self.dleft.append(total)
            e = self.graph.get_edge(self.route[i - 1], self.route[i])
            total = total + e.cost
        self.dleft.append(total)
        self.dleft.reverse()
        logger.debug(f"distance left to destination at vertex: {[round(e, 1) for e in self.dleft]}")

    def mkVertices(self):
        self.vertices = list(map(lambda x: self.graph.get_vertex(x), self.route))

    def mkTurns(self):
        # At end of edge x, turn will be turns[x] degrees
        # Idea: while walking the lights, determine how far is next turn (position to vertex) and how much it will turn.
        #       when closing to edge, invide to slow down if turn is important
        #       if turn is unimportant, anticipate to next vertex
        # note: at vertices[k], there is a turn from vertices[k-1] to vertices[k+1]
        # origin to first vertex
        b1 = bearing(self.precise_start, self.vertices[0])
        b2 = bearing(self.vertices[0], self.vertices[1])
        self.turns = [turn(b1, b2)]
        v0 = self.graph.get_vertex(self.route[0])
        v1 = self.graph.get_vertex(self.route[1])
        for i in range(1, len(self.route) - 1):
            v2 = self.graph.get_vertex(self.route[i + 1])
            self.turns.append(v1.turn(v0, v2))
            v0 = v1
            v1 = v2
        # last vertex to destination
        b1 = bearing(self.vertices[-2], self.vertices[-1])
        b2 = bearing(self.vertices[-1], self.precise_end)
        self.turns.append(turn(b1, b2))
        logger.debug(f"turns at vertex: {[round(t, 0) for t in self.turns]}")

    def mkDistToBrake(self):
        # for each vertex, write the distance to the next vertex where there is a reason to slow down at that vertex:
        # Either a sharp turn (> SMALL_TURN_LIMIT), or a stop bar (later).
        # note: at vertices[k], there is self.dtb[k] distance left to turn at self.dtb_at[k]
        #       (there may be a turn at vertices[k] itself, in turns[k])
        if self.turns is None or len(self.turns) == 0:
            return
        self.dtb = []
        self.dtb_at = []
        total = 0
        next_at = len(self.route) - 1
        self.dtb.append(total)  # at last vertex, no distance to next turn
        self.dtb_at.append(next_at)  # at last vertex, next turn is at last vertex
        # for i in range(len(self.route) - 1, 0, -1):
        #     total = total + self.edges[i - 1].cost
        #     self.dtb.append(total)
        #     self.dtb_at.append(next_at)
        #     if abs(self.turns[i - 1]) > SMALL_TURN_LIMIT:
        #         next_at = i - 1
        #         total = 0
        for i in range(len(self.edges), 0, -1):
            total = total + self.edges[i - 1].cost
            self.dtb.append(total)
            self.dtb_at.append(next_at)
            if abs(self.turns[i - 1]) > SMALL_TURN_LIMIT:
                next_at = i - 1
                total = 0
        self.dtb.reverse()
        self.dtb_at.reverse()
        logger.debug(f"distance before turn brake at vertex: {[round(e, 1) for e in self.dtb]}")
        logger.debug(f"next turn brake at vertex: {[e for e in self.dtb_at]}")

    def mkTiming(self, speed: float):
        if speed <= 0:
            logger.debug(f"invalid speed {speed}")
            return
        TURN_ANGLE = 45  # degree
        TURN_PENALTY = 30  # seconds
        self.tleft = []
        total = 0
        penalty = 0
        for i in range(len(self.edges), 0, -1):
            self.tleft.append(total)
            total = total + self.edges[i - 1].cost / speed
            if abs(self.turns[i - 1]) > TURN_ANGLE:
                total = total + TURN_PENALTY
                penalty = penalty + 1
        self.tleft.append(total)
        self.tleft.reverse()
        logger.debug(f"time left to destination at vertex (speed={round(speed, 1)}m/s, {penalty} turns): {', '.join([minsec(e) for e in self.tleft])}")

    def text(self, destination: str = "destination") -> str:
        if self.edges is None or len(self.edges) == 0:
            self.mkEdges()
        route_str = ""
        last = ""
        for e in self.edges:
            if e.name != "" and e.name != last:
                route_str = route_str + " " + e.name
                last = e.name
        route_str = route_str.strip().upper()
        # logger.debug(f"route to {destination} via {route_str}")
        # if destination != "":
        #     logger.debug(f"route to {destination} via {route_str}")
        # else:
        #     logger.debug(f"taxi route {route_str}")
        return route_str

    @classmethod
    def Find(
        cls,
        graph,
        aircraft,
        arrival_runway,
        dst_pos,
        dst_type: str,
        move: MOVEMENT,
        use_strict_mode: bool,
        use_threshold: bool,
    ):
        # Returns first route that works, or a route that does not work
        if use_strict_mode:
            logger.info("searching restricted route..")
            width_code = aircraft.width_code
            for respect_width_code in [True, False]:
                wc = "Y" if respect_width_code else "N"
                # WY/IY/RY/OY = respect_width/respect_inner/user_runway/respect_one_way

                cannot_use_runway = True  # forced, otherwise wierd things happen
                # cannot_use_runway = arrival_runway is None

                if cannot_use_runway:
                    # Strict, do not use runways, respect oneway, respect inner/outer
                    # subgraph = graph.clone(
                    #     width_code=width_code,
                    #     move=move,
                    #     respect_width=respect_width_code,
                    #     respect_inner=True
                    #     use_runway=False,
                    #     respect_oneway=True,
                    # )
                    # route = cls(subgraph)
                    # if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold=use_threshold):
                    #     logger.info(f"..found/W{wc}IYRNOY")
                    #     return route
                    # logger.debug("..failed..")

                    # do not use runways, respect oneway
                    subgraph = graph.clone(
                        width_code=width_code,
                        move=move,
                        respect_width=respect_width_code,
                        respect_inner=False,  # unused anyway
                        use_runway=False,
                        respect_oneway=True,
                    )
                    route = cls(subgraph)
                    if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold=use_threshold):
                        logger.info(f"..found/W{wc}INRNOY")
                        return route
                    logger.debug("..failed..")
                    # Alternative:
                    # route = Route.Find(subgraph, aircraft, arrival_runway, dst_pos, dst_type, move, use_strict_mode=False, use_threshold=use_threshold)
                    # if route.found():
                    #     logger.info(f"..found/W{wc}INRNOY")
                    #     return route
                    # logger.debug("..failed..")

                    # do not respect one ways
                    subgraph = graph.clone(
                        width_code=width_code,
                        move=move,
                        respect_width=respect_width_code,
                        respect_inner=False,  # unused anyway
                        use_runway=False,
                        respect_oneway=False,
                    )
                    route = cls(subgraph)
                    if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold=use_threshold):
                        logger.info(f"..found/W{wc}INRNON")
                        return route
                    logger.debug("..failed..")
                else:
                    logger.debug("runway can be used while taxiing, probably because we are on a runway")

                # use runway
                subgraph = graph.clone(
                    width_code=width_code,
                    move=move,
                    respect_width=respect_width_code,
                    respect_inner=False,  # unused anyway
                    use_runway=True,
                    respect_oneway=True,
                )
                route = cls(subgraph)
                if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold=use_threshold):
                    logger.info(f"..found/W{wc}INRYOY")
                    return route
                logger.debug("..failed..")

                # do not respect one ways
                subgraph = graph.clone(
                    width_code=width_code,
                    move=move,
                    respect_width=respect_width_code,
                    respect_inner=False,  # unused anyway
                    use_runway=True,
                    respect_oneway=False,
                )
                route = cls(subgraph)
                if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold=use_threshold):
                    logger.info(f"..found/W{wc}INRYON")
                    return route

            # We're desperate
            logger.info("..failed to find restricted route, trying wide search..")
        else:
            logger.info("searching route without restriction..")

        # else, default on whole graph
        route = cls(graph)
        if route.find(aircraft, arrival_runway, dst_pos, dst_type, move, use_threshold):
            logger.info("..found")
        else:
            logger.info("..failed (definitively)")
        return route

    def find(self, aircraft, arrival_runway, dst_pos, dst_type: str, move: MOVEMENT, use_threshold: bool) -> bool:
        # From aircraft position..
        pos = aircraft.position()
        if not pos:
            logger.debug("plane could not be located")
            return self.found()
        pos_pt = Point(pos[0], pos[1])
        self.precise_start = pos_pt
        logger.debug(f"..got starting position {pos}..")

        src = None
        if move == MOVEMENT.DEPARTURE:
            src = self.graph.findClosestVertex(pos_pt)
        else:  # arrival
            if arrival_runway is not None and dst_type == "stand":
                if dst_pos is not None:
                    nextexit = arrival_runway.nextExit(graph=self.graph, position=pos_pt, destination=dst_pos)
                    if nextexit is not None:
                        src = nextexit
                        logger.debug(f"arrival: on runway {arrival_runway.name}, closest exit vertex in front is {nextexit[0]}")
                logger.debug(f"arrival: on runway {arrival_runway.name}")
            else:
                brng = aircraft.heading()
                speed = aircraft.speed()
                logger.debug(f"arrival: not on runway, trying vertex ahead {brng}, {speed}")
                src = self.graph.findClosestVertexAheadGuess(pos_pt, brng, speed)
                if src is None or src[0] is None:  # tries a less constraining search...
                    logger.debug("no vertex ahead, fallback on closest vertex, not necessarily ahead")
                    src = self.graph.findClosestVertex(pos_pt)

        if src is None:
            logger.debug("no return from findClosestVertex")
            return self.found()
        if src[0] is None:
            logger.debug("no close vertex")
            return self.found()
        if src[1] > TOO_FAR:
            logger.debug(f"aircraft too far from taxiways ({round(src[1], 2)}m)")
            return self.found()
        logger.debug("..got starting vertex..")

        # ..to destination
        dst = None
        if move == MOVEMENT.DEPARTURE:
            if dst_type == "runway":
                if use_threshold:
                    logger.debug("departure destination: using runway threshold")
                    dst = self.graph.findClosestVertex(dst_pos.threshold)
                    self.precise_end = dst_pos.threshold
                else:
                    logger.debug(f"departure destination: using end of runway {dst_pos.start.coords()}")
                    dst = self.graph.findClosestVertex(dst_pos.start)
                    self.precise_end = dst_pos.start
            elif dst_type == "hold":
                dst = self.graph.findClosestVertex(dst_pos)
                self.precise_end = dst_pos
            else:
                logger.warning("departure destination is not a runway or a hold position")
        else:  # arrival, dst_type == "stand"
            if dst_type != "stand":
                logger.warning("arrival destination is not a stand")
            dst = self.graph.findClosestVertex(dst_pos)
            self.precise_end = dst_pos

        if dst is None:
            logger.debug("no return from findClosestVertex")
            return self.found()
        if dst[0] is None:
            logger.debug("no close vertex")
            return self.found()
        if dst[1] > TOO_FAR:
            logger.debug(f"aircraft too far from taxiways ({round(dst[1], 2)}m)")
            return self.found()
        logger.debug("..got destination vertex..")

        self.move = move

        return self._find(src[0], dst[0])

    def build(self, acf_speed: float, radius: float | None):
        # When route is selected, build a series of handy variables
        # to speedup calculations later
        # distance between edges, headings, distance remaning, etc.
        # also build timing information.
        self.mkVertices()  # load vertex meta for route
        self.mkEdges()  # compute segment distances
        self.mkTurns()  # compute turn angles at end of segment
        self.mkTiming(speed=acf_speed)  # compute total time left to reach destination
        self.mkDistToBrake()  # distance before significant turn
        if radius is None:
            radius = TURN_RADIUS
        self.mkSmoothRoute(radius=radius)
        # logger.debug(
        #     f"control: r={len(self.route)}, v={len(self.vertices)}, e={len(self.edges)}, turns={len(self.turns)}, brk={len(self.dtb)}, atbrk={len(self.dtb_at)}, d={len(self.dleft)}, t={len(self.tleft)}"
        # )
        # self.test()
        if logger.level <= 10:
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_route.geojson")  # _{self.route[0]}-{self.route[-1]}
            fc = FeatureCollection(features=self.features())
            fc.save(fn)
            logger.debug(f"taxi route saved in {os.path.abspath(fn)}")

    # SMOOTH ROUTE
    # Adds turns at vertices.
    #
    def mkSmoothRoute(self, radius: float):
        # Idea for later: turn radius depends on vehicle speed, whether aircraft or car
        def copy(v):
            return Point(v.lat, v.lon)

        vtx = self.vertices
        route = []
        v = copy(vtx[0])
        v.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, 0)  # tag with original route index
        v.setProp(SMOOTH_ROUTE.INDEX.value, len(route))
        v.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[0])
        route.append(v)
        vtx[0].setProp(SMOOTH_ROUTE.REVERSE_INDEX.value, 0)  # in original route, remember index in smooth route
        for i in range(1, len(vtx) - 1):
            turn = Turn(vertex=vtx[i], l_in=self.edges_orient[i - 1], l_out=self.edges_orient[i], radius=radius)
            if turn.valid:
                pts = [p[0] for p in turn.points]
                mid = int(len(pts) / 2)
                idx = len(route)
                for p in pts[0:mid]:  # tag half turn with original route index
                    p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.SMOOTH.value)
                    p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, i - 1)
                    p.setProp(GEOJSON.MARKER_COLOR.value, "#DDDDDD")  # light grey
                    p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                    p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[i])
                    idx += 1
                vtx[i].setProp(SMOOTH_ROUTE.REVERSE_INDEX.value, len(route) + mid)
                for p in pts[mid:]:  # tag second half turn with original next route index
                    p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.SMOOTH.value)
                    p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, i)
                    p.setProp(GEOJSON.MARKER_COLOR.value, "#DDDDDD")  # light grey
                    p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                    p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                    p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[i])
                    idx += 1
                pts[mid].setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
                pts[mid].setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
                pts[mid].setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
                pts[mid].setProp(GEOJSON.MARKER_COLOR.value, "#FFDDDD")  # light grey different
                route += pts
            else:
                t = min(Turn.SMALL_TURN_TANGENT, self.edges[i - 1].cost, self.edges[i].cost)
                pt = turn.progressiveTurn(length=t, segments=min(max(int(2 * t), 7), 21))
                if len(pt) > 0:
                    for p in pt:
                        p[0].setProp(SMOOTH_ROUTE.BEARING.value, p[1])
                    pts = [p[0] for p in pt]
                    mid = int(len(pts) / 2)
                    idx = len(route)
                    for p in pts[0:mid]:
                        p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.PROGRESSIVE.value)
                        p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, i - 1)
                        p.setProp(GEOJSON.MARKER_COLOR.value, "#AAAAAA")  # light grey
                        p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                        p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                        p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                        p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                        p.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[i])
                        idx += 1
                    vtx[i].setProp(SMOOTH_ROUTE.REVERSE_INDEX.value, len(route) + mid)
                    for p in pts[mid:]:
                        p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.PROGRESSIVE.value)
                        p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, i)
                        p.setProp(GEOJSON.MARKER_COLOR.value, "#AAAAAA")  # light grey
                        p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                        p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                        p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                        p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                        p.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[i])
                        idx += 1
                    pts[mid].setProp(GEOJSON.MARKER_COLOR.value, "#FFAAAA")  # light grey different
                    pts[mid].setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
                    pts[mid].setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
                    pts[mid].setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
                    route += pts
                else:
                    v = copy(vtx[i])
                    v.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.IMMEDIATE.value)
                    v.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, i)
                    v.setProp(GEOJSON.MARKER_COLOR.value, "#888888")  # medium grey
                    v.setProp(SMOOTH_ROUTE.INDEX.value, len(route))
                    v.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[i])
                    v.setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
                    v.setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
                    v.setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
                    route.append(v)
                    vtx[i].setProp(SMOOTH_ROUTE.REVERSE_INDEX.value, len(route) - 1)  # to check
        v = copy(vtx[-1])
        v.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, len(vtx) - 1)
        v.setProp(SMOOTH_ROUTE.INDEX.value, len(route))
        v.setProp(SMOOTH_ROUTE.REFERENCE_VERTEX.value, self.route[-1])
        route.append(v)
        vtx[-1].setProp(SMOOTH_ROUTE.REVERSE_INDEX.value, len(route) - 1)

        srVertices = [route[v.getProp(SMOOTH_ROUTE.REVERSE_INDEX.value)] for v in self.vertices]

        # Add props: distance from start, heading
        dist = 0
        seglen = 0  # current segment length
        last_idx = 0  # where to write length of next route segment (previous start of segment)
        rtidx = 0  # current route segment
        last_rtidx = 0  # previous route segment
        d = 0
        b = 0
        for i in range(len(route) - 1):  # [0] to [-2]
            d = distance(route[i], route[i + 1])
            b = bearing(route[i], route[i + 1])
            route[i].setProp(SMOOTH_ROUTE.DISTANCE.value, d)  # length to next vertex
            route[i].setProp(SMOOTH_ROUTE.TOTAL.value, dist)  # total distance since start
            ty = route[i].getProp(SMOOTH_ROUTE.TURN_TYPE.value)
            if ty is None or ty != TURN_TYPE.PROGRESSIVE.value:
                route[i].setProp(SMOOTH_ROUTE.BEARING.value, b)  # bearing to next vertex
            # else: bearing has been set in progressive turn
            rtidx = route[i].getProp(SMOOTH_ROUTE.ROUTE_INDEX.value)
            if rtidx != last_rtidx:  # write previous route segment length for smooth route
                route[last_idx].setProp(SMOOTH_ROUTE.SEGMENT_LENGTH.value, seglen)
                last_idx = i
                seglen = 0
            last_rtidx = rtidx
            dist += d
            seglen += d
        route[-1].setProp(SMOOTH_ROUTE.DISTANCE.value, 0)  # [-1]
        route[-1].setProp(SMOOTH_ROUTE.TOTAL.value, dist)  # total length or route
        route[-1].setProp(SMOOTH_ROUTE.BEARING.value, b)  # repeat last
        self.smoothRoute = route
        logger.debug(f"smooth route is {round(dist, 1)}m, has {len(self.smoothRoute)} points")
        if logger.level <= 10:
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_smooth_route.geojson")  # _{route.route[0]}-{route.route[-1]}, {datetime.now().strftime('%M%S%f')}
            fc = FeatureCollection(features=[r.feature() for r in route])
            fc.save(fn)
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_srvertices.geojson")  # _{route.route[0]}-{route.route[-1]}
            fc = FeatureCollection(features=[r.feature() for r in srVertices])
            fc.save(fn)

    def srMetaRouteVertex(self, sr_vertex) -> Point:
        i = sr_vertex.getProp(SMOOTH_ROUTE.ROUTE_INDEX.value)
        return self.vertices[i]

    def srMetaRouteEdge(self, sr_vertex) -> Line:
        i = sr_vertex.getProp(SMOOTH_ROUTE.ROUTE_INDEX.value)
        return self.edges[i]

    def srClosest(self, route: tuple, point: Point, cache: bool = False) -> tuple:
        closest = None
        shortest = math.inf
        i = 0
        start = self.idxcache if cache else 0
        for i in range(len(route[start:])):
            d = distance(route[i], point)
            if d < shortest:
                shortest = d
                closest = i
        logger.log(8, f"{closest} at {round(shortest, 1)}m")
        if cache:
            self.idxcache = closest.getProp(SMOOTH_ROUTE.INDEX)
        return None if closest is None else route[closest], shortest

    def srClosestOnRoute(self, route: tuple, point: Point) -> OnRoute:
        # 360 – maximum angle + minimum angle
        closest, dist = self.srClosest(route=route, point=point)
        if closest is None:
            logger.log(8, "not found")
            return OnRoute(index=NOT_ON_ROUTE, distance=dist, route=route)
        idx = closest.getProp(SMOOTH_ROUTE.INDEX)
        if idx == 0:  # first
            logger.log(8, "first segment")
            return OnRoute(index=idx, distance=dist, route=route)
        if idx == (len(route) - 1):  # last
            logger.log(8, "last segment")
            return OnRoute(index=len(route) - 2, distance=distance(route[-2], point), route=route)
        b1 = bearing(closest, point)
        b2 = bearing(closest, route[idx + 1])
        trn = turn(b1, b2)
        logger.log(8, f"turn: {trn}")
        if abs(trn) > 175:  # opposite
            logger.log(8, "previous")
            return OnRoute(index=idx - 1, distance=distance(route[idx - 1], point), route=route)
        logger.log(8, "current")
        return OnRoute(index=idx, distance=dist, route=route)

    def srAheadRoute(self, route, i: int, dist: float, start: float = 0) -> tuple:
        # move dist after start after route[i]
        # return point, bearing, index, distance on edge(index) from start of edge(index)
        if i >= len(route) - 1:  # end of route, end of recursion, return last point
            b = route[-1].getProp(SMOOTH_ROUTE.BEARING.value)
            return route[-1], b, i, 0
        if (start + dist) == 0:
            b = route[i].getProp(SMOOTH_ROUTE.BEARING.value)
            return route[i], b, i, 0
        self._srrecurr += 1
        d = route[i].getProp(SMOOTH_ROUTE.DISTANCE.value)
        if start + dist < d:  # there is enough room on the current edge, recursion ends
            b = route[i].getProp(SMOOTH_ROUTE.BEARING.value)
            pt = destination(route[i], b, start + dist)
            return pt, b, i, (start + dist)
        return self.srAheadRoute(route=route, i=i + 1, dist=start + dist - d)

    def srBackRoute(self, route, i: int, dist: float, back: float = 0.0) -> tuple:
        b = route[i].getProp(SMOOTH_ROUTE.BEARING.value)
        if back == 0.0:
            return route[i], b, i, dist
        if back <= dist:
            return route[i], b, i, dist - back
        if i == 0 or back < 0.0:  # security
            return route[0], b, 0, 0.0
        d = route[i - 1].getProp(SMOOTH_ROUTE.DISTANCE.value)
        return self.srBackRoute(route=route, i=i - 1, dist=d, back=back - dist)

    def srAhead(self, i: int, dist: float, start: float = 0) -> tuple:
        # move dist after start after self.smoothRoute[i]
        # return point, bearing, index, distance on edge(index) from start of edge(index)
        return self.srAheadRoute(route=self.smoothRoute, i=i, dist=dist, start=start)

    def srDestination(self, i: int, dist: float) -> Point:
        # point at dist of start of edge i on smoothRoute
        r = self.srAhead(i=i, dist=dist)
        return r[0]

    def srDestinationRoute(self, route, i: int, dist: float) -> Point:
        # point at dist of start of edge i on smoothRoute
        r = self.srAheadRoute(route=route, i=i, dist=dist)
        return r[0]

    def srDistanceRoute(self, route, i1: int, dist1: float, i2: int, dist2: float) -> float:
        # distance between two points on smoothRoute
        if i1 == i2:
            return dist2 - dist1
        total = route[i1].getProp(SMOOTH_ROUTE.DISTANCE) - dist1  # left on i1
        for i in range(i1 + 1, i2):
            total += route[i].getProp(SMOOTH_ROUTE.DISTANCE)  # length of followings (if any)
        total += dist2  # left on i2
        return total

    def srDistance(self, i1: int, dist1: float, i2: int, dist2: float) -> float:
        # distance between two points on smoothRoute
        return self.srDistanceRoute(self.smoothRoute, i1=i1, dist1=dist1, i2=i2, dist2=dist2)

    def mkSmoothJoinRoute(self, start: Point, end: Point, heading: float, text: str = ""):  # should pass fmcam.detail? to get radius, speed...
        # Direct segment to join route with turn at the end towards heading
        # To Do: Add initial turn from a starting heading towards end point
        route = []
        v = Point(start.lat, start.lon)
        v.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
        v.setProp(GEOJSON.MARKER_COLOR.value, "#888888")  # medium grey
        v.setProp(SMOOTH_ROUTE.INDEX.value, len(route))
        route.append(v)

        line = Line(start, end)
        turn = Turn(vertex=end, l_in=line.bearing(), l_out=heading)
        if turn.valid:
            pts = [p[0] for p in turn.points]
            mid = int(len(pts) / 2)
            idx = len(route)
            for p in pts[0:mid]:  # tag half turn with original route index
                p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.SMOOTH.value)
                p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
                p.setProp(GEOJSON.MARKER_COLOR.value, "#DDDDDD")  # light grey
                p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))  # also an indication that this point is part of the turn
                p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                idx += 1
            for p in pts[mid:]:  # tag second half turn with original next route index
                p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.SMOOTH.value)
                p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
                p.setProp(GEOJSON.MARKER_COLOR.value, "#DDDDDD")  # light grey
                p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                idx += 1
            pts[mid].setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
            pts[mid].setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
            pts[mid].setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
            pts[mid].setProp(GEOJSON.MARKER_COLOR.value, "#FFDDDD")  # light grey different
            route += pts
        else:
            t = min(Turn.SMALL_TURN_TANGENT, line.length())
            pt = turn.progressiveTurn(length=t, segments=min(max(int(2 * t), 7), 21))
            if len(pt) > 0:
                logger.debug(f"adding progressive turn ({len(pt)})")
                for p in pt:
                    p[0].setProp(SMOOTH_ROUTE.BEARING.value, p[1])
                pts = [p[0] for p in pt]
                mid = int(len(pts) / 2)
                idx = len(route)
                for p in pts[0:mid]:
                    p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.PROGRESSIVE.value)
                    p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
                    p.setProp(GEOJSON.MARKER_COLOR.value, "#AAAAAA")  # light grey
                    p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                    p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                    p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                    idx += 1
                for p in pts[mid:]:
                    p.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.PROGRESSIVE.value)
                    p.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
                    p.setProp(GEOJSON.MARKER_COLOR.value, "#AAAAAA")  # light grey
                    p.setProp(SMOOTH_ROUTE.INDEX.value, idx)
                    p.setProp(SMOOTH_ROUTE.TURN_START.value, len(route))
                    p.setProp(SMOOTH_ROUTE.TURN_MIDDLE.value, len(route) + mid)  # also an indication that this point is part of the turn
                    p.setProp(SMOOTH_ROUTE.TURN_END.value, len(route) + len(pts))  # also an indication that this point is part of the turn
                    idx += 1
                pts[mid].setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
                pts[mid].setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
                pts[mid].setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
                pts[mid].setProp(GEOJSON.MARKER_COLOR.value, "#FFAAAA")  # light grey different
                route += pts
            else:  # no turn
                logger.debug(f"no turn (l_in={line.bearing()}, l_out={heading})")
                v = end
                v.setProp(SMOOTH_ROUTE.TURN_TYPE.value, TURN_TYPE.IMMEDIATE.value)
                v.setProp(SMOOTH_ROUTE.ROUTE_INDEX.value, -1)
                v.setProp(GEOJSON.MARKER_COLOR.value, "#888888")  # medium grey
                v.setProp(SMOOTH_ROUTE.INDEX.value, len(route))
                v.setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
                v.setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
                v.setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)
                route.append(v)

        # Add props: distance from start, heading
        dist = 0
        seglen = 0  # current segment length
        last_idx = 0  # where to write length of next route segment (previous start of segment)
        rtidx = 0  # current route segment
        last_rtidx = 0  # previous route segment
        d = 0
        b = 0
        for i in range(len(route) - 1):  # [0] to [-2]
            d = distance(route[i], route[i + 1])
            b = bearing(route[i], route[i + 1])
            route[i].setProp(SMOOTH_ROUTE.DISTANCE.value, d)  # length to next vertex
            route[i].setProp(SMOOTH_ROUTE.TOTAL.value, dist)  # total distance since start
            ty = route[i].getProp(SMOOTH_ROUTE.TURN_TYPE.value)
            if ty is None or ty != TURN_TYPE.PROGRESSIVE.value:
                route[i].setProp(SMOOTH_ROUTE.BEARING.value, b)  # bearing to next vertex
            # else: bearing has been set in progressive turn
            rtidx = route[i].getProp(SMOOTH_ROUTE.ROUTE_INDEX.value)
            if rtidx != last_rtidx:  # write previous route segment length for smooth route
                route[last_idx].setProp(SMOOTH_ROUTE.SEGMENT_LENGTH.value, seglen)
                last_idx = i
                seglen = 0
            last_rtidx = rtidx
            dist += d
            seglen += d
        route[-1].setProp(SMOOTH_ROUTE.DISTANCE.value, 0)  # [-1]
        route[-1].setProp(SMOOTH_ROUTE.TOTAL.value, dist)  # total length or route
        route[-1].setProp(SMOOTH_ROUTE.BEARING.value, b)  # repeat last
        # Convention: On Straight line, we indicate key turn data at the end in these three variables
        # This allows to set turn indicator at the end of Straight lines
        route[-1].setProp(SMOOTH_ROUTE.TURN_VALID.value, turn.valid)
        route[-1].setProp(SMOOTH_ROUTE.TURN_ALPHA.value, turn.alpha)
        route[-1].setProp(SMOOTH_ROUTE.TURN_TANGENT.value, turn.tangent_length)

        if logger.level < 10:
            fn = os.path.join(os.path.dirname(__file__), "..", f"ftg_straight{datetime.now().strftime('%M%S%f')}.geojson")  # _{self.route[0]}-{self.route[-1]}
            fc = FeatureCollection(features=[r.feature() for r in route])
            fc.save(fn)
            logger.debug(f"straight line to route saved in {os.path.abspath(fn)}")
        logger.info(f"straight route {len(route)} points, turn at end {round(turn.alpha)}D")

        return route

    # TESTS / DEBUG
    #
    def stats(self):
        logger.debug(f"equiv {self._srcnt}, scan={self._srscan}, ahead recur={self._srrecurr}")

    def test(self):
        # can we trust OnRoute?
        try:
            dl = self.srDistance(i1=0, dist1=0.0, i2=len(self.smoothRoute) - 1, dist2=0.0)
            center = OnRoute(index=int(len(self.smoothRoute) / 2), distance=0.0, route=self.smoothRoute)
            d0 = self.srDistance(i1=0, dist1=0, i2=center.index, dist2=center.distance)
            logger.debug(f"center at {d0} {center}, total={dl}")

            for d in [0, 10, 100, 1000, 2000]:
                df = center.forward(dist=d)
                df0 = self.srDistance(i1=0, dist1=0, i2=df.index, dist2=df.distance)
                df1 = self.srDistance(i1=center.index, dist1=center.distance, i2=df.index, dist2=df.distance)
                df2 = df.distanceTo(center)
                logger.debug(f"forward {d} {df0} {df1} {df2} {df}")
                db = center.backward(dist=d)
                db0 = self.srDistance(i1=0, dist1=0, i2=db.index, dist2=db.distance)
                db1 = self.srDistance(i1=center.index, dist1=center.distance, i2=df.index, dist2=df.distance)
                db2 = db.distanceTo(center)
                logger.debug(f"backward {d} {db0} {db1} {db2} {db}")
        except:
            logger.debug("error", exc_info=True)
