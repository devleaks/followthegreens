# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
import os.path
import re
import math

from .geo import Point, Line, Polygon, distance, pointInPolygon
from .graph import Graph, Edge
from .globals import (
    TAXIWAY_WIDTH_CODE,
    TAXIWAY_WIDTH,
    logger,
    DISTANCE_TO_RAMPS,
    MOVEMENT,
    TOO_FAR,
    ROUTING_ALGORITHM,
    ROUTING_ALGORITHMS,
    USE_STRICT_MODE,
)

SYSTEM_DIRECTORY = "."


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


class Runway(Line):
    # A place to be. But not too long.
    def __init__(self, name, width, lat, lon, lat2, lon2, pol):
        Line.__init__(self, Point(lat, lon), Point(lat2, lon2))
        self.name = name
        self.width = width
        self.polygon = pol  # avoid multiple inheritence from Line,Polygon.


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


class Route:
    # Container for route from src to dst on graph
    def __init__(self, graph, src, dst, move, options):
        self.graph = graph
        self.src = src
        self.dst = dst
        self.move = move
        self.options = options
        self.route = []
        self.vertices = None
        self.edges = None
        self.smoothed = None
        self.algorithm = ROUTING_ALGORITHM  # default, unused

    def __str__(self):
        if self.found():
            return "-".join(self.route)
        return ""

    def _find(
        self,
        algorithm: ROUTING_ALGORITHMS,
        width_code: TAXIWAY_WIDTH_CODE,
        move: MOVEMENT,
        respect_width: bool = False,
        respect_inner: bool = False,
        use_runway: bool = True,
        respect_oneway: bool = True,
    ):
        # Preselect edge set with supplied constraints
        logger.debug("_find clone")
        graph = self.graph.clone(
            width_code=width_code,
            move=self.move,
            respect_width=respect_width,
            respect_inner=respect_inner,
            use_runway=use_runway,
            respect_oneway=respect_oneway,
        )

        logger.debug(f"_find route {algorithm}")
        if algorithm == ROUTING_ALGORITHMS.ASTAR:
            return graph.AStar(self.src, self.dst)

        return graph.Dijkstra(self.src, self.dst)  # no option

    def findExtended(self, width_code: TAXIWAY_WIDTH_CODE, move: MOVEMENT):
        # Clone orignal graph as collected from apt.dat file
        # while relaxing some constraints during the cloning
        # Starts with original graph, then relax constraints until route is found
        logger.debug("findExtended started")
        for algorithm in ROUTING_ALGORITHMS:
            logger.debug(f"findExtended {algorithm}")
            for respect_width_code in [True, False]:
                # Strict
                self.route = self._find(
                    algorithm=algorithm,
                    width_code=width_code,
                    move=move,
                    respect_width=respect_width_code,
                    respect_inner=True,
                    use_runway=False,
                    respect_oneway=True,
                )
                if self.found():
                    logger.debug(f"found algorithm={algorithm}, respect_width={respect_width_code}, respect_inner=True, use_runway=False, respect_oneway=True")
                    logger.debug("all constraints satisfied")
                    return self
                # Use runway
                self.route = self._find(
                    algorithm=algorithm,
                    width_code=width_code,
                    move=move,
                    respect_width=respect_width_code,
                    respect_inner=False,  # unsued anyway
                    use_runway=True,
                    respect_oneway=True,
                )
                if self.found():
                    logger.debug(f"found algorithm={algorithm}, respect_width={respect_width_code}, respect_inner=False, use_runway=True, respect_oneway=True")
                    return self
                # Do not respect one ways
                self.route = self._find(
                    algorithm=algorithm,
                    width_code=width_code,
                    move=move,
                    respect_width=respect_width_code,
                    respect_inner=False,  # unsued anyway
                    use_runway=True,
                    respect_oneway=False,
                )
                if self.found():
                    logger.debug(f"found algorithm={algorithm}, respect_width={respect_width_code}, respect_inner=False, use_runway=True, respect_oneway=False")
                    return self
        # We're desperate
        logger.debug(f"findExtended found not restricted route, returning default wide search using algorith {self.algorithm}")
        self.options = {}
        logger.debug("all constraints relaxed")
        # self.route = self._find(algorithm=ROUTING_ALGORITHM, width_code=width_code, move=move) # no other restriction
        # logger.debug(f"find extended return {self.route}, {self.graph.Dijkstra(self.src, self.dst)}")
        return self.find()

    def find(self):
        if self.algorithm == ROUTING_ALGORITHMS.ASTAR:
            self.route = self.graph.AStar(self.src, self.dst)
            return self
        self.route = self.graph.Dijkstra(self.src, self.dst, self.options)
        return self

    def found(self):
        return self.route is not None and len(self.route) > 2

    def mkEdges(self):
        # From liste of vertices, build list of edges
        # but also set the size of the taxiway in the vertex
        self.edges = []
        for i in range(len(self.route) - 1):
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            v = self.graph.get_vertex(self.route[i])
            v.setProp("taxiway-width", e.width_code)
            v.setProp("ls", i)
            self.edges.append(e)

    def mkVertices(self):
        self.vertices = list(map(lambda x: self.graph.get_vertex(x), self.route))


class Airport:
    """Airport represetation (limited to FTG needs)"""

    # Should be split with generic non dependant airport and airport with routing, dependant on Graph

    def __init__(self, icao):
        self.icao = icao
        self.name = ""
        self.atc_ground = None
        self.altitude = 0  # ASL, in meters
        self.loaded = False
        self.scenery_pack = False
        self.lines = []
        self.graph = Graph()
        self.runways = {}
        self.holds = {}
        self.ramps = {}

    def prepare(self):
        status = self.load()
        if not status:
            return [False, "We could not find airport named '%s'." % self.icao]

        # Info 5
        logger.debug("Has ATC %s." % (self.hasATC()))  # actually, we don't care.

        status = self.mkRoutingNetwork()
        if not status:
            return [False, "We could not build taxiway network for %s." % self.icao]

        status = self.ldRunways()
        if len(status) == 0:
            return [False, "We could not find runways for %s." % self.icao]
        # Info 7
        logger.debug("runways: %s" % (status.keys()))

        status = self.ldHolds()
        logger.debug("holding positions: %s" % (status.keys()))

        status = self.ldRamps()
        if len(status) == 0:
            return [False, "We could not find ramps/parking for %s." % self.icao]
        # Info 8
        logger.debug("ramps: %s" % (status.keys()))

        return [True, "Airport ready"]

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
                        logger.debug(f"Added apt.dat {scenery_pack_apt}")
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
        logger.debug(f"APT files: {APT_FILES}")

        for scenery, filename in APT_FILES.items():
            if self.loaded:
                return self.loaded

            logger.debug(f"scenery pack {scenery}..")
            apt_dat = open(filename, "r", encoding="utf-8", errors="ignore")
            line = apt_dat.readline()

            while not self.loaded and line:  # while we have not found our airport and there are more lines in this pack
                if re.match("^1 ", line, flags=0):  # if it is a "startOfAirport" line
                    newparam = line.split()  # if no characters supplied to split(), multiple space characters as one
                    # logger.debug("airport: %s" % newparam[4])
                    if newparam[4] == self.icao:  # it is the airport we are looking for
                        self.name = " ".join(newparam[5:])
                        self.altitude = newparam[1]
                        # Info 4.a
                        logger.info(f"Found airport {newparam[4]} '{self.name}' in '{filename}'.")
                        self.scenery_pack = filename  # remember where we found it
                        self.lines.append(AptLine(line))  # keep first line
                        line = apt_dat.readline()  # next line in apt.dat
                        while line and not re.match("^1 ", line, flags=0):  # while we do not encounter a line defining a new airport...
                            testline = AptLine(line)
                            if testline.linecode() is not None:
                                self.lines.append(testline)
                            else:
                                logger.debug(f"did not load empty line '{line}'")
                            line = apt_dat.readline()  # next line in apt.dat
                        # Info 4.b
                        logger.info(f"Read {len(self.lines)} lines for {self.name}")
                        self.loaded = True

                if line:  # otherwize we reached the end of file
                    line = apt_dat.readline()  # next line in apt.dat

            apt_dat.close()

        return self.loaded

    def dump(self, filename):
        aptfile = open(filename, "w")
        for line in self.lines:
            aptfile.write("%d %s\n" % (line.linecode(), line.content()))
        aptfile.close()

    # Collect 1201 and (102,1204) line codes and create routing network (graph) of taxiways
    def mkRoutingNetwork(self):
        # 1201  25.29549372  051.60759816 both 16 unnamed entity(split)
        def addVertex(aptline):
            args = aptline.content().split()
            return self.graph.add_vertex(args[3], Point(args[0], args[1]), args[2], " ".join(args[3:]))

        vertexlines = list(filter(lambda x: x.linecode() == 1201, self.lines))
        v = list(map(addVertex, vertexlines))
        logger.debug("added %d vertices" % len(v))

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
        logger.info(f"added {len(vertexlines)} nodes, {edgeCount} edges ({edgeActiveCount} enhanced).")
        return True

    def ldRunways(self):
        #     0     1 2 3    4 5 6 7    8            9               10 11  1213141516   17           18              19 20  21222324
        # 100 60.00 1 1 0.25 1 3 0 16L  25.29609337  051.60889908    0  300 2 2 1 0 34R  25.25546269  051.62677745    0  306 3 2 1 0
        runways = {}

        for aptline in self.lines:
            if aptline.linecode() == 100:  # runway
                args = aptline.content().split()
                runway = Polygon.mkPolygon(args[8], args[9], args[17], args[18], float(args[0]))
                runways[args[7]] = Runway(args[7], args[0], args[8], args[9], args[17], args[18], runway)
                runways[args[16]] = Runway(args[16], args[0], args[17], args[18], args[8], args[9], runway)

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
        logger.debug(f"{closest} at {shortest}")
        return [closest, shortest]

    def onRunway(self, coord, width=None):
        # Width is in meter
        logger.debug(f"onRunway? {coord}")
        point = Point(coord[0], coord[1])
        for name, rwy in self.runways.items():
            polygon = None
            if width is None:
                polygon = rwy.polygon
            else:  # make a larger area around/along runway (larger than runway width)
                polygon = Polygon.mkPolygon(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
            if pointInPolygon(point, polygon):
                if width:
                    logger.debug(f"on {name} (buffer={width}m)")
                else:
                    logger.debug(f"on {name}")
                return [True, rwy]
            logger.debug(f"not on {name}")

        return [False, None]

    def guessMove(self, coord) -> MOVEMENT:
        onRwy, runway = self.onRunway(coord)
        if onRwy:
            return MOVEMENT.ARRIVAL
        ret = self.findClosestRamp(coord)
        if ret[1] < DISTANCE_TO_RAMPS:  # meters, we are close to a ramp.
            return MOVEMENT.DEPARTURE
        return MOVEMENT.ARRIVAL

    def getRunways(self):
        if not self.runways:
            self.ldRunways()
        return self.runways.keys()

    def getRamp(self, name):
        if not self.ramps:
            self.ldRamps()
        if name in self.ramps:
            return self.ramps[name]
        return None

    def getRunway(self, name):
        if not self.runways:
            self.ldRunways()
        if name in self.runways:
            return self.runways[name]
        return None

    def getRamps(self):
        if not self.ramps:
            self.ldRamps()
        return self.ramps.keys()

    def getDestinations(self, mode: MOVEMENT):
        if mode == MOVEMENT.DEPARTURE:
            return list(list(self.runways.keys()) + list(self.holds.keys()))

        return list(self.ramps.keys())

    def mkRoute(self, aircraft, destination, move):
        # Returns (True, route object) or (False, error message)
        # From aircraft position..
        pos = aircraft.position()
        dstpt = None
        runway = None
        if not pos:
            logger.debug("plane could not be located")
            return (False, "We could not locate your plane.")
        logger.debug(f"got starting position {pos}")

        if move == MOVEMENT.DEPARTURE:
            src = self.findClosestVertex(pos)
        else:  # arrival
            brng = aircraft.heading()
            speed = aircraft.speed()
            logger.debug(f"arrival: trying vertex ahead {brng}, {speed}.")
            src = self.findClosestVertexAheadGuess(pos, brng, speed)
            if src is None or src[0] is None:  # tries a less constraining search...
                logger.debug("no vertex ahead.")
                src = self.findClosestVertex(pos)
            onRwy, runway = self.onRunway(pos)
            if onRwy:
                logger.debug(f"Arrival: on runway {runway.name}.")
            else:
                logger.debug("Arrival: not on runway.")

        if src is None:
            logger.debug("no return from findClosestVertex")
            return (False, "Your plane is too far from the taxiways.")

        if src[0] is None:
            logger.debug("no close vertex")
            return (False, "Your plane is too far from the taxiways.")

        if src[1] > TOO_FAR:
            logger.debug("plane too far from taxiways")
            return (False, "Your plane is too far from the taxiways.")

        logger.debug("got starting vertex %s", src)

        # ..to destination
        dst = None
        dstpt = None  # heading after destination reached (heading of runway/takeoff or heading of parking)
        if move == MOVEMENT.DEPARTURE:
            if destination in self.runways.keys():
                runway = self.getRunway(destination)
                if runway:  # we sure to find one because first test
                    dstpt = runway.end  # Last "nice" turn will towards runways' end.
                    dst = self.findClosestVertex(runway.start.coords())
                else:
                    return (False, "We could not find runway %s." % destination)
            elif destination in self.holds.keys():
                dst = self.findClosestVertex(self.holds[destination].coords())
                # dstpt: We don't know which way for takeoff.
        else:
            ramp = self.getRamp(destination)
            if ramp:
                dstpt = ramp
                dst = self.findClosestVertex(ramp.coords())
            else:
                return (False, "We could not find parking or ramp %s." % destination)

        if dst is None:
            logger.debug("no return from findClosestVertex")
            return (False, "We could not find parking or ramp %s." % destination)

        if dst[0] is None:
            logger.debug("no close vertex")
            return (
                False,
                "We could not find a taxiway near parking or ramp %s." % destination,
            )

        if dst[1] > TOO_FAR:
            logger.debug("plane too far from taxiways")
            return (False, "Your destination is too far from the taxiways.")

        logger.debug(f"got destination vertex {dst}")

        # Try to find route (src and dst are vertex ids)
        opts = {"taxiwayOnly": True}
        route = Route(self.graph, src[0], dst[0], move, opts)
        if USE_STRICT_MODE:
            logger.debug("searching with all constraints..")
            route.findExtended(width_code=aircraft.width_code, move=move)
            logger.debug("..done")
        else:
            # use specified algorithm
            route.find()
            if not route.found() and len(opts.keys()) > 0:  # if there were options, we try to find a route without option
                # only relax oneway/twoway constraint
                logger.debug("route not found with options, trying without option.")
                route.options = {}
                route.find()
        if route.found():  # second attempt may have worked
            return (True, route)

        return (False, "We could not find a route to your destination.")

    # Returns ATC ground frequency if it exists
    def hasATC(self):
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
