# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
import os
import math

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import (
    logger,
    get_global,
    minsec,
    MOVEMENT,
    TOO_FAR,
    ROUTING_ALGORITHM,
    ROUTING_ALGORITHMS,
)
from .geo import FeatureCollection, Point, Line, destination, distance, bearing, turn

SYSTEM_DIRECTORY = "."

# Turn data
TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line
SMALL_TURN_LIMIT = 15.0  # °, above this angle, it is recommended to slow down for the turn
NUM_SEGMENTS = 36  # default number of segments for a smooth turn, will be adjusted for turn size, radius and speed


class Turn:

    SMALL_TURN_TANGENT = 10.0  # m
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


class Route:
    # Container for route from src to dst on graph
    def __init__(self, graph):
        self.graph = graph
        self.route = []
        self.vertices = None
        self.edges = None
        self.turns = None
        self.dtb = None  # Distance To Brake (distance before reason to brake)
        self.dtb_at = None
        self.dleft = []
        self.tleft = []
        self.smoothed = None
        self.algorithm = ROUTING_ALGORITHM  # default, unused
        self.departure_runway = None
        self.arrival_runway = None
        self.precise_start = None
        self.precise_end = None

        self.smoothRoute = []
        self.idxcache = 0  # progress on smooth route, cannot backup

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
            f["properties"]["marker-size"] = "medium"
            if abs(self.turns[i]) > TURN_LIMIT:
                f["properties"]["marker-color"] = "#006600"  # dark green
            else:
                f["properties"]["marker-color"] = "#00AA00"  # green
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

    def before_route(self):
        # Original point to first vertex
        return Line(start=self.precise_start, end=self.vertices[0])

    def after_route(self):
        # Last vertex to destination
        return Line(start=self.vertices[-1], end=self.precise_end)

    def from_edge(self, i: int, position: Point) -> float | None:
        if self.vertices is not None and len(self.vertices) > i:
            return distance(self.vertices[i], position)
        return None

    def on_edge(self, i: int, dist: float) -> Point | None:
        if self.vertices is not None and len(self.vertices) > i:
            return destination(self.vertices[i], self.edges_orient[i], dist)
        return None

    def mkEdges(self):
        # From liste of vertices, build list of edges
        # but also set the size of the taxiway in the vertex
        # note: edges[k] starts at vertices[k]
        self.edges = []
        self.edges_orient = []  # True: start->end, False: end->start
        for i in range(len(self.route) - 1):
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            v = self.graph.get_vertex(self.route[i])
            v.setProp("taxiway-width", e.width_code.value if e.width_code is not None else "-")
            v.setProp("ls", i)
            self.edges.append(e)
            self.edges_orient.append(e.bearing(orig=v))
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
        # for each vertex, write the distance to the next vertex
        # where there is a reason to slow down at that vertex: Either a sharp turn (> SMALL_TURN_LIMIT), or a stop bar (later).
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
                    logger.debug("departure destination: using end of runway")
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

        return self._find(src[0], dst[0])

    def mkSmoothRoute(self):
        def copy(v):
            return Point(v.lat, v.lon)

        vtx = self.vertices
        route = []
        v = copy(vtx[0])
        v.setProp("srRouteIndex", 0)  # tag with original route index
        v.setProp("srIndex", len(route))
        route.append(v)
        vtx[0].setProp("srRevRouteIndex", 0)  # in original route, remember index in smooth route
        for i in range(1, len(vtx) - 1):
            turn = Turn(vertex=vtx[i], l_in=self.edges_orient[i - 1], l_out=self.edges_orient[i], radius=22, segments=36)
            if turn.valid:
                pts = [p[0] for p in turn.points]
                mid = int(len(pts) / 2)
                idx = len(route)
                for p in pts[0:mid]:  # tag half turn with original route index
                    p.setProp("srRouteIndex", i - 1)
                    p.setProp("marker-color", "#DDDDDD")  # light grey
                    p.setProp("srIndex", idx)
                    idx += 1
                vtx[i].setProp("srRevRouteIndex", len(route) + mid)
                for p in pts[mid:]:  # tag second half turn with original next route index
                    p.setProp("srRouteIndex", i)
                    p.setProp("marker-color", "#DDDDDD")  # light grey
                    p.setProp("srIndex", idx)
                    idx += 1
                pts[mid].setProp("marker-color", "#FFDDDD")  # light grey different
                route += pts
            else:
                t = min(Turn.SMALL_TURN_TANGENT, self.edges[i - 1].cost, self.edges[i].cost)
                pt = turn.progressiveTurn(length=t, segments=min(max(int(2 * t), 7), 21))
                if len(pt) > 0:
                    pts = [p[0] for p in pt]
                    mid = int(len(pts) / 2)
                    idx = len(route)
                    for p in pts[0:mid]:
                        p.setProp("srRouteIndex", i - 1)
                        p.setProp("marker-color", "#AAAAAA")  # light grey
                        p.setProp("srIndex", idx)
                        idx += 1
                    vtx[i].setProp("srRevRouteIndex", len(route) + mid)
                    for p in pts[mid:]:
                        p.setProp("srRouteIndex", i)
                        p.setProp("marker-color", "#AAAAAA")  # light grey
                        p.setProp("srIndex", idx)
                        idx += 1
                    pts[mid].setProp("marker-color", "#FFAAAA")  # light grey different
                    route += pts
                else:
                    v = copy(vtx[i])
                    v.setProp("srRouteIndex", i)
                    v.setProp("marker-color", "#888888")  # medium grey
                    v.setProp("srIndex", len(route))
                    route.append(v)
                    vtx[i].setProp("srRevRouteIndex", len(route) - 1)  # to check
        v = copy(vtx[-1])
        v.setProp("srRouteIndex", len(vtx) - 1)
        v.setProp("srIndex", len(route))
        route.append(v)
        vtx[-1].setProp("srRevRouteIndex", len(route) - 1)
        # Add props: distance from start, heading
        dist = 0
        d = 0
        b = 0
        for i in range(len(route) - 1):  # [0] to [-2]
            d = distance(route[i], route[i + 1])
            b = bearing(route[i], route[i + 1])
            route[i].setProp("srDistance", d)  # length to next vertex
            route[i].setProp("srTotal", dist)  # total distance since start
            route[i].setProp("srBearing", b)  # bearing to next vertex
            dist += d
        route[-1].setProp("srDistance", 0)  # [-1]
        route[-1].setProp("srTotal", dist)  # total length or route
        route[-1].setProp("srBearing", b)  # repeat last
        self.smoothRoute = route
        logger.debug(f"smooth route is {round(dist, 1)}m, has {len(self.smoothRoute)} points")
        if logger.level <= 10:
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_smooth_route.geojson")  # _{route.route[0]}-{route.route[-1]}
            fc = FeatureCollection(features=[r.feature() for r in route])
            fc.save(fn)

    def closest(self, point: Point, cache: bool = True) -> tuple:
        closest = None
        shortest = math.inf
        for i in range(len(self.smoothRoute[self.idxcache :])):
            d = distance(self.smoothRoute[i], point)
            if d < shortest:
                shortest = d
                closest = i
        logger.debug(f"{closest} at {round(shortest, 1)}m")
        if cache:
            self.idxcache = i
        return [None if closest is None else self.smoothRoute[closest], shortest]

    def ahead(self, i: int, dist: float, start: float = 0):
        # move dist after start after self.smoothRoute[i]
        if i >= len(self.smoothRoute) - 1:  # end of route, end of recursion, return last point
            b = self.smoothRoute[-1].getProp("srBearing")
            return self.smoothRoute[-1], b, i, 0
        d = self.smoothRoute[i].getProp("srDistance")
        if start + dist < d:  # there is enough room on the current edge, recursion ends
            b = self.smoothRoute.getProp("srBearing")
            pt = destination(self.smoothRoute[i], b, start + dist)
            return pt, b, i, (start + dist)
        return self.ahead(i + 1, start + dist - d)

    def srFinished(self, position) -> bool:
        return self.smoothRoute[-1] == position

    def build(self, acf_speed: float):
        self.mkVertices()  # load vertex meta for route
        self.mkEdges()  # compute segment distances
        self.mkTurns()  # compute turn angles at end of segment
        self.mkTiming(speed=acf_speed)  # compute total time left to reach destination
        self.mkDistToBrake()  # distance before significant turn
        self.mkSmoothRoute()
        logger.debug(
            f"control: r={len(self.route)}, v={len(self.vertices)}, e={len(self.edges)}, turns={len(self.turns)}, brk={len(self.dtb)}, atbrk={len(self.dtb_at)}, d={len(self.dleft)}, t={len(self.tleft)}"
        )
        if logger.level <= 10:
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_route.geojson")  # _{self.route[0]}-{self.route[-1]}
            fc = FeatureCollection(features=self.features())
            fc.save(fn)
            logger.debug(f"taxi route saved in {os.path.abspath(fn)}")
