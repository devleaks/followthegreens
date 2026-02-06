# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
import os
import re
import math
import json
from typing import Tuple

from .geo import FeatureCollection, Point, Line, Polygon, destination, distance, pointInPolygon
from .graph import Graph, Edge, Vertex
from .globals import (
    logger,
    get_global,
    minsec,
    DISTANCE_TO_RAMPS,
    TAXIWAY_TYPE,
    RUNWAY_BUFFER_WIDTH,
    AIRPORT,
    MOVEMENT,
    RABBIT,
    TOO_FAR,
    ROUTING_ALGORITHM,
    ROUTING_ALGORITHMS,
)

SYSTEM_DIRECTORY = "."

TURN_LIMIT = 10.0  # °, below this, it is not considered a turn, just a small break in an almost straight line
SMALL_TURN_LIMIT = 15.0  # °, above this angle, it is recommended to slow down for the turn


class Runway(Line):
    # A place to be. But not too long.
    def __init__(self, name, width, lat, lon, dt, dbo, lat2, lon2, pol):
        Line.__init__(self, Point(lat, lon), Point(lat2, lon2))
        self.name = name
        self.width = width
        self.displaced_threshold = float(dt)
        self.overrun = float(dbo)
        if pol is None:
            if width is not None and width > 0:
                self.polygon = Polygon.mkPolygon(lat, lon, lat2, lon2, width)
        else:
            self.polygon = pol
        self.threshold = self.start
        self.first_exit = self.threshold
        self.mkThreshold()

    def onRunway(self, point):
        if self.polygon is None:
            return False
        return pointInPolygon(point, self.polygon)

    def mkThreshold(self):
        # If no displaced threshold, the threshold is the start
        move = self.displaced_threshold + self.overrun
        if move == 0:
            return
        self.threshold = destination(src=self.start, brngDeg=self.bearing(), d=move)
        self.first_exit = self.threshold
        logger.debug(f"displaced threshold at {round(move,1)}m")

    def runwayExits(self, graph: Graph) -> set:
        # return vertex that this on taxiway network, that is NOT a on a runway edge
        # and that is the closest to runway threshold
        # Select vertices from segments that are not runway
        # Select vertices that are "inside" a buffer around the runway
        # Select the vertex closest to the start or threshold
        buffer = Polygon.mkPolygon(self.start.lat, self.start.lon, self.end.lat, self.end.lon, RUNWAY_BUFFER_WIDTH)
        candidates = set()
        for e in graph.edges_arr:
            if e.usage == TAXIWAY_TYPE.TAXIWAY:
                if pointInPolygon(e.start, buffer):
                    candidates.add(e.start)
                if pointInPolygon(e.start, buffer):
                    candidates.add(e.end)
        logger.debug(f"runway has {len(candidates)} vertices in buffering zone (width={RUNWAY_BUFFER_WIDTH}m)")
        return candidates

    def firstEntry(self, graph: Graph, use_threshold: bool = False):
        # return vertex that this on taxiway network, that is NOT a on a runway edge
        # and that is the closest to runway threshold
        # Select vertices from segments that are not runway
        # Select vertices that are "inside" a buffer around the runway
        # Select the vertex closest to the start or threshold
        candidates2 = self.runwayExits(graph=graph)
        contact = self.threshold if use_threshold else self.start
        contact_str = "threshold" if use_threshold else "begining of runway"
        # 2. keep closest to threshold
        closest = None
        shortest = math.inf
        for v in candidates2:
            d = distance(v, contact)
            if d < shortest:
                shortest = d
                closest = v
        if closest is not None:
            self.first_exit = closest
            logger.debug(f"entry closest to {contact_str} {closest.id} at {round(shortest, 2)}m from {contact_str}")
            return [closest.id, shortest]
        self.first_exit = contact
        logger.debug(f"entry closest to {contact_str} not found, using {contact_str}")
        return None

    def nextExit(self, graph: Graph, position: Point, destination: Vertex) -> Tuple[str, float] | None:
        # return next vertex that this on taxiway network, that is NOT a on a runway edge
        # and that is the closest to position and "in front of" the position (i.e. close to end edge than position)
        # Aircraft landed, is rolling out, prompt for the greens.
        # What is the next exit in front of the aircraft suitable for routing?
        # Needs refining: left or right exit?
        # 𝑑=(𝑥−𝑥1)(𝑦2−𝑦1)−(𝑦−𝑦1)(𝑥2−𝑥1)
        candidates = self.runwayExits(graph=graph)
        pos_to_end = distance(position, self.end)
        side_needed = self.side(destination)

        closest = None
        shortest = math.inf
        for v in candidates:
            d = distance(v, self.end)
            if d > pos_to_end:  # point is not "in front of" position, i.e. not closer to end than position
                # logger.debug(f"entry {v.id} not in front of aircraft ({round(d,2)} > {round(pos_to_end,2)})")
                continue
            s = self.side(v)
            if s != 0 and s != side_needed:  # exit wrong side of taxiway, well it is just a GUESS, sometimes you have to exit right to get left...
                # logger.debug(f"entry {v.id} not on same side as destination")
                continue
            d = distance(v, position)
            if d < shortest:
                shortest = d
                closest = v
            #     logger.debug(f"closest entry {closest.id} at {round(shortest,2)}")
            # else:
            #     logger.debug(f"entry {v.id} not closer at {round(d,2)}")
        if closest is not None:
            d = distance(closest, self.end)
            logger.debug(
                f"entry {closest.id} closest and in front at {round(shortest, 0)}m from aircraft at {round(pos_to_end, 0)}m from runway end; vertext at {round(d, 0)}m from runway end"
            )
            return [closest.id, shortest]
        logger.debug("entry closest to current position in front of position not found")
        return None


class Hold(Point):
    # A parking area for plane
    def __init__(self, name, lat, lon):
        Point.__init__(self, lat, lon)
        self.name = name


class Ramp(Point):
    # A parking area for plane
    def __init__(self, name, heading, lat, lon):
        Point.__init__(self, lat, lon)
        self.name = name
        self.heading = heading


class AptLine:
    # APT.DAT line for this airport
    def __init__(self, line):
        self.arr = line.split()
        if len(self.arr) == 0:
            logger.debug(f"empty line? '{line}'")

    def linecode(self):
        if len(self.arr) > 0:
            return int(self.arr[0])
        return None

    def content(self):
        if len(self.arr) > 1:
            return " ".join(self.arr[1:])
        return None  # line has no content


class Airport:
    """Airport represetation (limited to FTG needs)"""

    # Should be split with generic non dependant airport and airport with routing, dependant on Graph

    def __init__(self, icao, prefs: dict = {}):
        self.icao = icao.upper()
        self.prefs = prefs
        self.name = ""
        self.atc_ground = None
        self.altitude = 0  # ASL, in meters
        self.loaded = False
        self.scenery_pack = False
        self.lines = []
        self.graph = Graph(name="taxiways")
        self.runways = {}
        self.holds = {}
        self.ramps = {}
        #
        self.smooth_line = 0
        self.smoothGraph = Graph(name="Smoothed taxiways")
        self.tempSmoothCurve = []

        # PREFERENCES - Fetched by LightString
        # Set sensible default value from global preferences
        self.use_threshold = get_global("USE_THRESHOLD", self.prefs)
        if self.use_threshold is None:
            self.use_threshold = True
        self.distance_between_taxiway_lights = get_global(AIRPORT.DISTANCE_BETWEEN_LIGHTS.value, self.prefs)  # meters, for show_taxiways()
        self.distance_between_green_lights = get_global(AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value, self.prefs)  # meters for follow_the_greens()
        self.rabbit_speed = get_global(RABBIT.SPEED.value, self.prefs)  # seconds
        # Info 4
        # Fine tune for specific airport(s)
        self.setPreferences()
        logger.debug(f"AIRPORT rabbit: btw greens={self.distance_between_green_lights}m, whole net={self.distance_between_taxiway_lights}m, speed={self.rabbit_speed}s")

    def prepare(self):
        status = self.load()
        if not status:
            return [False, f"We could not find airport named '{self.icao}'."]

        # status = self.load_smooth()
        # if not status:
        #     return [False, f"We could not find smooth taxiway lines for airport named '{self.icao}'."]

        # Info 5
        logger.debug(f"Has ATC {self.hasATC()}.")  # actually, we don't care.

        status = self.mkRoutingNetwork()
        if not status:
            return [False, f"We could not build taxiway network for {self.icao}."]

        status = self.ldRunways()
        if len(status) == 0:
            return [False, f"We could not find runways for {self.icao}."]
        # Info 7
        logger.debug(f"runways: {status.keys()}")

        status = self.ldHolds()
        logger.debug(f"holding positions: {status.keys()}")

        status = self.ldRamps()
        if len(status) == 0:
            return [False, f"We could not find ramps/parking for {self.icao}."]
        # Info 8
        logger.debug(f"ramps: {status.keys()}")

        return [True, "Airport ready"]

    def setPreferences(self):
        # Local airport preferences override global preferences
        apt = self.prefs.get("Airports", {})
        prefs = apt.get(self.icao)
        logger.debug(f"{self.icao} preferences: {prefs}")
        if prefs is not None:
            if AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value in prefs:
                self.distance_between_green_lights = prefs[AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value]
            return
        # Generic
        logger.debug(f"Airport preferences: {apt}")
        if AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value in apt:
            self.distance_between_green_lights = apt[AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value]

    def load(self):
        APT_FILES = {}

        # Add scenery packs, which include Global Airports scenery in XP11
        scenery_packs_file = os.path.join(SYSTEM_DIRECTORY, "Custom Scenery", "scenery_packs.ini")
        if os.path.exists(scenery_packs_file):
            scenery_packs = open(scenery_packs_file, "r", encoding="utf-8", errors="ignore")
            scenery = scenery_packs.readline()
            scenery = scenery.strip()
            while scenery:
                if re.match("^SCENERY_PACK", scenery, flags=0):
                    logger.debug(f"SCENERY_PACK {scenery.rstrip()}")
                    scenery_pack_dir = scenery[13:-1]
                    scenery_pack_apt = os.path.join(scenery_pack_dir, "Earth nav data", "apt.dat")
                    # logger.debug("APT.DAT {scenery_pack_apt}")
                    if os.path.exists(scenery_pack_apt) and os.path.isfile(scenery_pack_apt):
                        logger.debug(f"added apt.dat {scenery_pack_apt}")
                        APT_FILES[scenery] = scenery_pack_apt
                scenery = scenery_packs.readline()
            scenery_packs.close()

        # Add XP 12 location for Global Airports
        default_airports_file = os.path.join(
            SYSTEM_DIRECTORY,
            "Global Scenery",
            "Global Airports",
            "Earth nav data",
            "apt.dat",
        )
        if os.path.exists(default_airports_file) and os.path.isfile(default_airports_file):
            APT_FILES["default airports"] = default_airports_file
        # else:
        #     logger.warning(f"default airport file {DEFAULT_AIRPORTS} not found")
        # logger.debug(f"APT files: {APT_FILES}")

        for scenery, filename in APT_FILES.items():
            if self.loaded:
                return self.loaded

            logger.debug(f"scenery pack {scenery.strip()}..")
            apt_dat = open(filename, "r", encoding="utf-8", errors="ignore")
            line = apt_dat.readline()

            while not self.loaded and line:  # while we have not found our airport and there are more lines in this pack
                if re.match("^1 ", line, flags=0):  # if it is a "startOfAirport" line
                    newparam = line.split()  # if no characters supplied to split(), multiple space characters as one
                    # logger.debug(f"airport: {newparam[4]}")
                    if newparam[4] == self.icao:  # it is the airport we are looking for
                        self.name = " ".join(newparam[5:])
                        self.altitude = newparam[1]
                        # Info 4.a
                        logger.info(f"found airport {newparam[4]} '{self.name}' in '{filename}'.")
                        self.scenery_pack = filename  # remember where we found it
                        self.lines.append(AptLine(line.strip()))  # keep first line
                        line = apt_dat.readline()  # next line in apt.dat
                        while line and not re.match("^1 ", line, flags=0):  # while we do not encounter a line defining a new airport...
                            testline = AptLine(line.strip())
                            if testline.linecode() is not None:
                                self.lines.append(testline)
                            else:
                                logger.debug(f"did not load empty line '{line.strip()}'")
                            line = apt_dat.readline()  # next line in apt.dat
                        # Info 4.b
                        logger.info(f"read {len(self.lines)} lines for {self.name}")
                        self.loaded = True

                if line:  # otherwize we reached the end of file
                    line = apt_dat.readline()  # next line in apt.dat

            apt_dat.close()

        return self.loaded

    def dumpAptFile(self, filename):
        aptfile = open(filename, "w")
        for line in self.lines:
            aptfile.write(f"{line.linecode()} {line.content()}\n")
        aptfile.close()

    def loadSmoothedTaxiwayNetwork(self):
        fn = os.path.join(os.path.dirname(__file__), "..", f"{self.icao}.geojson")
        data = {}
        if not os.path.exists(fn):
            return False

        with open(fn, "r") as fp:
            data = json.load(fp)
        logger.debug(f"loaded {len(data['features'])} features")

        # Create vertices, list edges
        cnt = 1
        for f in data["features"]:
            g = f["geometry"]
            if g["type"] == "Point":  # there shouldn't be any
                self.smoothGraph.add_vertex(cnt, point=Point(lat=g["coordinates"][1], lon=g["coordinates"][0]), usage="taxiway")
                cnt = cnt + 1
            elif g["type"] == "LineString":
                last = None
                for p in g["coordinates"]:
                    self.smoothGraph.add_vertex(cnt, point=Point(lat=p[1], lon=p[0]), usage="taxiway")
                    if last is not None:
                        cost = distance(self.smoothGraph.vert_dict[cnt - 1], self.smoothGraph.vert_dict[cnt])
                        self.smoothGraph.add_edge(
                            edge=Edge(
                                src=self.smoothGraph.vert_dict[cnt - 1],
                                dst=self.smoothGraph.vert_dict[cnt],
                                cost=cost,
                                direction="both",
                                usage="taxiway",
                                name="",
                            )
                        )
                    last = self.smoothGraph.vert_dict[cnt]
                    cnt = cnt + 1
        # logger.debug(f"added {len(self.smoothGraph.vert_dict)} vertices, {len(self.smoothGraph.edges_arr)} edges")
        self.smoothGraph.stats()
        return True

    def stats(self):
        s = {}
        for l in self.lines:
            if l.linecode() not in s:
                s[l.linecode()] = 0
            s[l.linecode()] = s[l.linecode()] + 1
        logger.debug(f"airport apt.dat {len(self.lines)} lines: {dict(sorted(s.items()))}")

    # Collect 1201 and (102,1204) line codes and create routing network (graph) of taxiways
    def mkRoutingNetwork(self):
        # 1201  25.29549372  051.60759816 both 16 unnamed entity(split)
        def addVertex(aptline):
            args = aptline.content().split()
            return self.graph.add_vertex(args[3], Point(args[0], args[1]), args[2], " ".join(args[3:]))

        vertexlines = list(filter(lambda x: x.linecode() == 1201, self.lines))
        v = list(map(addVertex, vertexlines))
        logger.debug(f"added {len(v)} vertices")

        # 1202 20 21 twoway runway 16L/34R
        # 1204 departure 16L,34R
        # 1204 arrival 16L,34R
        # 1204 ils 16L,34R
        edgeCount = 0  # just for info
        edgeActiveCount = 0
        edge = None
        for aptline in self.lines:
            if aptline.linecode() == 1202:  # edge
                args = aptline.content().split()
                if len(args) >= 4:
                    src = self.graph.get_vertex(args[0])
                    dst = self.graph.get_vertex(args[1])
                    cost = distance(src, dst)
                    edge = None
                    if len(args) == 5:
                        edge = Edge(src, dst, cost, args[2], args[3], args[4])
                    else:
                        edge = Edge(src, dst, cost, args[2], args[3], "")
                    self.graph.add_edge(edge)
                    edgeCount += 1
                else:
                    logger.debug(f"not enough params {aptline.linecode()} {aptline.content()}.")
            elif aptline.linecode() == 1204 and edge is not None:
                args = aptline.content().split()
                if len(args) >= 2:
                    edge.add_active(args[0], args[1])
                    edgeActiveCount += 1
                else:
                    logger.debug(f"not enough params {aptline.linecode()} {aptline.content()}.")
            else:
                edge = None

        # Info 6
        self.stats()
        logger.info(f"added {len(vertexlines)} nodes, {edgeCount} edges ({edgeActiveCount} enhanced).")
        self.graph.stats()
        return True

    def ldRunways(self):
        #     0     1 2 3    4 5 6 7    8            9               10 11  1213141516   17           18              19 20  21222324
        # 100 60.00 1 1 0.25 1 3 0 16L  25.29609337  051.60889908    0  300 2 2 1 0 34R  25.25546269  051.62677745    0  306 3 2 1 0
        runways = {}

        for aptline in self.lines:
            if aptline.linecode() == 100:  # runway
                args = aptline.content().split()
                runway = Polygon.mkPolygon(lat1=args[8], lon1=args[9], lat2=args[17], lon2=args[18], width=float(args[0]))
                runways[args[7]] = Runway(name=args[7], width=args[0], lat=args[8], lon=args[9], dt=args[10], dbo=args[11], lat2=args[17], lon2=args[18], pol=runway)
                runways[args[16]] = Runway(name=args[16], width=args[0], lat=args[17], lon=args[18], dt=args[19], dbo=args[20], lat2=args[8], lon2=args[9], pol=runway)

        self.runways = runways
        logger.debug(f"added {len(runways.keys())} runways")
        return runways

    def ldHolds(self):
        holds = {}

        # if len(self.runways.keys()) > 0:
        #     rwy = self.runways[list(self.runways.keys())[0]]
        #     name = "Demo hold " + rwy.name
        #     holds[name] = Hold(name, rwy.start.lat, rwy.start.lon)

        self.holds = holds
        logger.debug(f"added {len(holds.keys())} holding positions")
        return holds

    def ldRamps(self):
        # 1300  25.26123160  051.61147754 155.90 gate heavy|jets|turboprops A1
        # 1301 E airline
        # 1202 ignored.
        ramps = {}

        ramp = False
        for aptline in self.lines:
            if aptline.linecode() == 1300:  # ramp
                args = aptline.content().split()
                if args[3] != "misc":
                    rampName = " ".join(args[5:])
                    ramp = Ramp(rampName, args[2], args[0], args[1])
                    ramp.locationType = args[3]
                    ramp.aircrafts = args[4].split("|")
                    ramps[rampName] = ramp
            elif ramp and aptline.linecode() == 1301:  # ramp details
                args = aptline.content().split()
                ramp.icaoType = args[0]
                ramp.operationType = args[1]
                if len(args) > 2 and args[2] != "":
                    ramp.airlines = args[2].split(",")
            else:
                ramp = False

        self.ramps = ramps
        logger.debug(f"added {len(ramps.keys())} ramps")
        return ramps

    # Find
    #
    def findClosestVertex(self, coord):
        return self.graph.findClosestVertex(Point(coord[0], coord[1]))

    def findClosestVertexAhead(self, coord, brng, speed):
        return self.graph.findClosestVertexAhead(Point(coord[0], coord[1]), brng, speed)

    def findClosestVertexAheadGuess(self, coord, brng, speed):
        return self.graph.findClosestVertexAheadGuess(Point(coord[0], coord[1]), brng, speed)

    def findClosestPointOnEdges(self, coord):
        return self.graph.findClosestPointOnEdges(Point(coord[0], coord[1]))

    def findClosestRamp(self, coord):
        closest = None
        shortest = math.inf
        point = Point(coord[0], coord[1])
        for name, ramp in self.ramps.items():
            d = distance(ramp, point)
            if d < shortest:
                shortest = d
                closest = name
        logger.debug(f"{closest} at {round(shortest, 1)}m")
        return [closest, shortest]

    def onRunway(self, position, width: float | None = None, heading: float | None = None):
        # Width is in meter
        logger.debug(f"onRunway? position={position}, width={width}, heading={heading}")
        point = Point(position[0], position[1])

        if heading is not None:
            for name, rwy in self.runways.items():
                polygon = None
                if width is None:
                    polygon = rwy.polygon
                else:  # make a larger area around/along runway (larger than runway width)
                    polygon = Polygon.mkPolygon(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
                if polygon is not None:
                    if pointInPolygon(point, polygon):
                        d = abs(heading - rwy.bearing())
                        # logger.debug(f"orientation (ac heading={round(heading, 1)}, rwy heading={round(rwy.bearing(), 1)}, delta={round(d, 2)}")
                        if d > 330:
                            d = abs(d - 360)
                        logger.debug(f"orientation (ac heading={round(heading, 1)}, rwy heading={round(rwy.bearing(), 1)}, delta={round(d, 2)}")
                        if d < 90:  # assume same heading
                            logger.debug(
                                f"on {name}, same orientation (rwy width={rwy.width}m, ac heading={round(heading, 1)}, rwy heading={round(rwy.bearing(), 1)}, delta={round(d, 2)})"
                            )
                            return [True, rwy]
                    else:
                        logger.debug(f"not on runway {name} (rwy width={rwy.width}m)")  # , {polygon.coords()}
                else:
                    logger.debug(f"no polygon for runway {name}")
            # 2nd attempt if not found above: ignore heading

        for name, rwy in self.runways.items():
            polygon = None
            if width is None:
                polygon = rwy.polygon
            else:  # make a larger area around/along runway (larger than runway width)
                polygon = Polygon.mkPolygon(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
            if polygon is not None:
                if pointInPolygon(point, polygon):
                    logger.debug(f"on {name}, no orientation (rwy width={rwy.width}m)")
                    return [True, rwy]
                else:
                    logger.debug(f"not on runway {name}")  # , {polygon.coords()}
            else:
                logger.debug(f"no polygon for runway {name}")

        return [False, None]

    def guessMove(self, coord) -> MOVEMENT:
        # Info 10
        onRwy, runway = self.onRunway(coord)
        if onRwy:
            logger.info("aircraft appears to be on runway, assuming arrival")
            return MOVEMENT.ARRIVAL
        ret = self.findClosestRamp(coord)
        if ret[1] < DISTANCE_TO_RAMPS:  # meters, we are close to a ramp.
            closest = ""
            if type(ret[0]) is str:
                closest = f" close to stand {ret[0]}"
            logger.info(f"aircraft appears to be on apron{closest}, assuming departure")
            return MOVEMENT.DEPARTURE
        return MOVEMENT.ARRIVAL

    def getRunways(self):
        if not self.runways:
            self.ldRunways()
        return self.runways.keys()

    def getRunway(self, name) -> Runway | None:
        if not self.runways:
            self.ldRunways()
        return self.runways.get(name)

    def getRamps(self):
        if not self.ramps:
            self.ldRamps()
        return self.ramps.keys()

    def getRamp(self, name) -> Ramp | None:
        if not self.ramps:
            self.ldRamps()
        return self.ramps.get(name)

    def getDestinations(self, mode: MOVEMENT) -> list:
        if mode == MOVEMENT.DEPARTURE:
            return list(list(self.runways.keys()) + list(self.holds.keys()))

        return list(self.ramps.keys())

    def mkRoute(self, aircraft, destination, move: MOVEMENT, use_strict_mode: bool) -> tuple:
        # Returns (True, route object) or (False, error message)
        # From aircraft position..
        arrival_runway = None
        if move == MOVEMENT.ARRIVAL:
            pos = aircraft.position()
            if not pos:
                logger.debug("plane could not be located")
                return (False, "We could not locate your plane.")
            hdg = aircraft.heading()
            onRwy, arrival_runway = self.onRunway(pos, width=RUNWAY_BUFFER_WIDTH, heading=hdg)

        # ..to destination
        dst_pos = None
        dst_type = ""
        if move == MOVEMENT.DEPARTURE:
            if destination in self.runways.keys():
                dst_pos = self.getRunway(destination)
                if dst_pos is None:  # we sure to find one because first test
                    return (False, f"We could not find runway {destination}.")
                dst_type = "runway"
            elif destination in self.holds.keys():
                dst_pos = self.holds[destination].coords()
                if dst_pos is None:  # we sure to find one because first test
                    return (False, f"We could not find hold position {destination}.")
                dst_type = "hold"
        else:
            dst_pos = self.getRamp(destination)
            if dst_pos is None:
                return (False, f"We could not find stand {destination}.")
            dst_type = "stand"

        route = Route.Find(self.graph, aircraft, arrival_runway, dst_pos, dst_type, move, use_strict_mode, self.use_threshold)

        if route.found():
            route.runway = arrival_runway
            logger.debug(f"route {route.text(destination=destination)}")

            route.mkEdges()  # compute segment distances
            route.mkTurns()  # compute turn angles at end of segment
            route.mkTiming(speed=aircraft.avgTaxiSpeed())  # compute total time left to reach destination
            route.mkDistToBrake()  # distance before significant turn
            if logger.level < 10:
                fn = os.path.join(os.path.dirname(__file__), "..", f"ftg_route.geojson")  # _{route.route[0]}-{route.route[-1]}
                fc = FeatureCollection(features=route.features())
                fc.save(fn)
                logger.debug(f"taxi route saved in {os.path.abspath(fn)}")
            return (True, route)

        return (False, "We could not find a route to your destination.")

    # def mkSmoothRoute(self, aircraft, destination, move: MOVEMENT, use_strict_mode: bool):
    #     def findClosestVertexSmooth(coord):
    #         return self.smoothGraph.findClosestVertex(Point(coord[0], coord[1]))

    #     pos = aircraft.position()
    #     src = findClosestVertexSmooth(pos)
    #     dst = src

    #     if move == MOVEMENT.DEPARTURE:
    #         if destination in self.runways.keys():
    #             runway = self.getRunway(destination)
    #             if runway is not None:  # we sure to find one because first test
    #                 dstpt = runway.end  # Last "nice" turn will towards runways' end.
    #                 # this is currently equivalent to searching vertex closest to threshold like done right after...
    #                 # entry = runway.firstEntry(graph=self.graph)
    #                 # ...so we do not do it now. We'll refine the firstEntry() later.
    #                 if self.use_threshold:
    #                     logger.debug("departure destination: using runway threshold")
    #                     dst = findClosestVertexSmooth(runway.threshold.coords())
    #                 else:
    #                     logger.debug("departure destination: using end of runway")
    #                     dst = findClosestVertexSmooth(runway.start.coords())
    #             else:
    #                 return (False, f"We could not find runway {destination}.")
    #         elif destination in self.holds.keys():
    #             dst = findClosestVertexSmooth(self.holds[destination].coords())
    #             # dstpt: We don't know which way for takeoff.
    #     else:
    #         ramp = self.getRamp(destination)
    #         if ramp is not None:
    #             dstpt = ramp
    #             dst = findClosestVertexSmooth(ramp.coords())
    #         else:
    #             return (False, f"We could not find parking or ramp {destination}.")

    #     route = Route(self.smoothGraph, src[0], dst[0], None, None, move, {})
    #     route.find()
    #     if not route.found():  # if there were options, we try to find a route without option
    #         return (False, "We could not find a smooth route to your destination.")
    #     return [True, route]

    def hasATC(self):
        # Returns ATC ground frequency if it exists
        self.atc_ground = None

        for line in self.lines:
            linecode = line.linecode()
            if linecode == "1053" and self.atc_ground is None:
                a = line.content().split()
                self.atc_ground = a[2] / 1000
            elif linecode == "53" and self.atc_ground is None:
                a = line.content().split()
                self.atc_ground = a[2] / 1000

        return self.atc_ground

    # Return boolean on taxiway network existence
    def hasTaxiwayRoutes(self):
        return len(self.graph.edges_arr) > 0  # weak but ok for now

    # Returns all lines with supplied linecode
    def getLines(self, code):
        return list(filter(lambda x: x.linecode() == code, self.lines))


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
        self.runway = None

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
            if abs(self.turns[i]) > TURN_LIMIT:
                f["properties"]["marker-color"] = "#006600"  # dark green
            else:
                f["properties"]["marker-color"] = "#00FF00"  # green
            features.append(f)
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            features.append(e.feature())
        return features

    def _find(self, src, dst) -> bool:
        # If requested to try AStar, try it first, if failed, try Dijkstra
        # If Dijstra fails, we really can't do anything about it.
        if self.algorithm == ROUTING_ALGORITHMS.ASTAR:
            self.route = self.graph.AStar(src, dst)
            logger.info(f"..failed to find route using algorithm {self.algorithm}, will try algorithm Dijkstra..")
            return self.found()
        self.route = self.graph.Dijkstra(src, dst)
        return self.found()

    def found(self) -> bool:
        return self.route is not None and len(self.route) > 2

    def baseline(self, idx: int = 0) -> tuple:
        # Returns distance and time left at route index
        if len(self.dleft) > 0 and len(self.tleft) > 0:
            return self.dleft[idx], self.tleft[idx]
        return 0, 0

    def mkEdges(self):
        # From liste of vertices, build list of edges
        # but also set the size of the taxiway in the vertex
        self.edges = []
        for i in range(len(self.route) - 1):
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            v = self.graph.get_vertex(self.route[i])
            v.setProp("taxiway-width", e.width_code.value if e.width_code is not None else "-")
            v.setProp("ls", i)
            self.edges.append(e)
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
        self.turns = [0]
        v0 = self.graph.get_vertex(self.route[0])
        v1 = self.graph.get_vertex(self.route[1])
        for i in range(1, len(self.route) - 1):
            v2 = self.graph.get_vertex(self.route[i + 1])
            self.turns.append(v1.turn(v0, v2))
            v0 = v1
            v1 = v2
        logger.debug(f"turns at vertex: {[round(t, 0) for t in self.turns]}")

    def mkDistToBrake(self):
        # for each vertex, write the distance to the next vertex
        # where there is a reason to slow down at that vertex: Either a sharp turn (> SMALL_TURN_LIMIT), or a stop bar (later).
        if self.turns is None or len(self.turns) == 0:
            return
        self.dtb = []
        self.dtb_at = []
        total = 0
        next_at = 0
        self.dtb.append(total)  # at last vertex, no distance to next turn
        for i in range(len(self.route) - 1, 0, -1):
            total = total + self.edges[i - 1].cost
            self.dtb.append(total)
            self.dtb_at.append(next_at)
            if abs(self.turns[i - 1]) > SMALL_TURN_LIMIT:
                next_at = i - 1
                total = 0
        self.dtb.reverse()
        # self.dtb_at.append(self.dtb_at[-1])
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
        for i in range(len(self.edges) - 1, 0, -1):
            self.tleft.append(total)
            total = total + self.edges[i].cost / speed
            if abs(self.turns[i]) > TURN_ANGLE:
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
        arrival_runway: Runway | None,
        dst_pos: Runway | Ramp | Hold,
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
                    logger.debug("runway can be used while taxiing, probably because we are on a runway...")

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

    def find(self, aircraft, arrival_runway: Runway | None, dst_pos: Runway | Ramp | Hold, dst_type: str, move: MOVEMENT, use_threshold: bool) -> bool:
        # From aircraft position..
        pos = aircraft.position()
        if not pos:
            logger.debug("plane could not be located")
            return self.found()
        pos_pt = Point(pos[0], pos[1])
        logger.debug(f"..got starting position {pos}..")

        src = None
        if move == MOVEMENT.DEPARTURE:
            src = self.graph.findClosestVertex(pos_pt)
        else:  # arrival
            brng = aircraft.heading()
            speed = aircraft.speed()
            logger.debug(f"arrival: trying vertex ahead {brng}, {speed}.")
            src = self.graph.findClosestVertexAheadGuess(pos_pt, brng, speed)
            if src is None or src[0] is None:  # tries a less constraining search...
                logger.debug("no vertex ahead.")
                src = self.graph.findClosestVertex(pos_pt)
            if arrival_runway is not None and dst_type == "stand":
                if dst_pos is not None:
                    nextexit = arrival_runway.nextExit(graph=self.graph, position=pos_pt, destination=dst_pos)
                    if nextexit is not None:
                        src = nextexit
                        logger.debug(f"Arrival: on runway {arrival_runway.name}, closest exit vertex in front is {nextexit[0]}.")
                logger.debug(f"Arrival: on runway {arrival_runway.name}.")
            else:
                logger.debug("Arrival: not on runway.")

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
                else:
                    logger.debug("departure destination: using end of runway")
                    dst = self.graph.findClosestVertex(dst_pos.start)
            elif dst_type == "hold":
                dst = self.graph.findClosestVertex(dst_pos)
            else:
                logger.warning("departure destination is not a runway or a hold position")
        else:  # arrival, dst_type == "stand"
            if dst_type != "stand":
                logger.warning("arrival destination is not a stand")
            dst = self.graph.findClosestVertex(dst_pos)

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
