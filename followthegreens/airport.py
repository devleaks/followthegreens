# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
import os.path
import re
import math
import logging

from .geo import Point, Line, Polygon, distance, pointInPolygon
from .graph import Graph, Edge
from .globals import SYSTEM_DIRECTORY, DISTANCE_TO_RAMPS, DEPARTURE, ARRIVAL, TOO_FAR
from .globals import AIRCRAFT_TYPES as TAXIWAY_WIDTH
from .mp_functions import MultiProcessLoader


class AptLine:
    # APT.DAT line for this airport
    def __init__(self, line):
        self.arr = line.split()
        if len(self.arr) == 0:
            logging.debug("AptLine::linecode: empty line? '%s'", line)

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
        logging.debug("Airport::route:: {}".format(self.options))

    def __str__(self):
        if self.found():
            return "-".join(self.route)
        return ""

    def find(self):
        self.route = self.graph.Dijkstra(self.src, self.dst, self.options)
        return self

    def found(self):
        return self.route and len(self.route) > 2

    def mkEdges(self):
        # From liste of vertices, build list of edges
        # but also set the size of the taxiway in the vertex
        self.edges = []
        for i in range(len(self.route) - 1):
            e = self.graph.get_edge(self.route[i], self.route[i + 1])
            v = self.graph.get_vertex(self.route[i])
            v.setProp("taxiway-width", TAXIWAY_WIDTH[e.widthCode("D")])  # default to D if not given
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

    def prepare_new(self, ui):
        logging.debug("Airport::prepare_new: started")
        # Multiprocessing insert
        mpl = MultiProcessLoader(self, ui)
        status = mpl.start()
        return status

    def prepare_old(self):
        logging.debug("Airport::prepare_old: started")
        status = self.load()
        if not status:
            return [False, "We could not find airport named '%s'." % self.icao]
        return self.prepare()

    def prepare(self):
        logging.debug("Airport::prepare: started")
        # status = self.load()
        # if not status:
        #     return [False, "We could not find airport named '%s'." % self.icao]

        # Info 5
        logging.debug("Airport::prepare: Has ATC %s." % (self.hasATC()))  # actually, we don't care.
        logging.debug("Airport::prepare: mkRountingNetwork started")
        status = self.mkRoutingNetwork()
        if not status:
            return [False, "We could not build taxiway network for %s." % self.icao]
        logging.debug("Airport::prepare: mkRountingNetwork finished")
        logging.debug("Airport::prepare: ldRunways started")
        status = self.ldRunways()
        if len(status) == 0:
            return [False, "We could not find runways for %s." % self.icao]
        # Info 7
        logging.debug("Airport::prepare: ldRunways finished")
        logging.debug("Airport::prepare: runways: %s" % (status.keys()))

        logging.debug("Airport::prepare: ldHolds started")
        status = self.ldHolds()
        logging.debug("Airport::prepare: ldHolds finished")
        logging.debug("Airport::prepare: holding positions: %s" % (status.keys()))

        logging.debug("Airport::prepare: ldRamps started")
        status = self.ldRamps()
        if len(status) == 0:
            return [False, "We could not find ramps/parking for %s." % self.icao]
        # Info 8
        logging.debug("Airport::prepare: ldRamps finished")
        logging.debug("Airport::prepare: ramps: %s" % (status.keys()))

        logging.debug("Airport::prepare: finished")
        return [True, "Airport ready"]


    def load(self):
        logging.debug("Airport::load: started")
        SCENERY_PACKS = os.path.join(SYSTEM_DIRECTORY, "Custom Scenery", "scenery_packs.ini")
        scenery_packs = open(SCENERY_PACKS, "r")
        scenery = scenery_packs.readline()
        scenery = scenery.strip()
        logging.debug("Airport::load: scenery_packs.ini read finished")
        while not self.loaded and scenery:  # while we have not found our airport and there are more scenery packs
            if re.match("^SCENERY_PACK", scenery, flags=0):
                logging.debug("SCENERY_PACK %s", scenery.rstrip())
                scenery_pack_dir = scenery[13:-1]
                if scenery_pack_dir == "*GLOBAL_AIRPORTS*":
                    scenery_pack_dir = os.path.join(SYSTEM_DIRECTORY, "Global Scenery", "Global Airports")
                scenery_pack_apt = os.path.join(scenery_pack_dir, "Earth nav data", "apt.dat")
                logging.debug("APT.DAT %s", scenery_pack_apt)

                if os.path.isfile(scenery_pack_apt):
                    apt_dat = open(scenery_pack_apt, "r", encoding="utf-8", errors="ignore")
                    line = apt_dat.readline()

                    while not self.loaded and line:  # while we have not found our airport and there are more lines in this pack
                        if re.match("^1 ", line, flags=0):  # if it is a "startOfAirport" line
                            newparam = line.split()  # if no characters supplied to split(), multiple space characters as one
                            # logging.debug("airport: %s" % newparam[4])
                            if newparam[4] == self.icao:  # it is the airport we are looking for
                                self.name = " ".join(newparam[5:])
                                self.altitude = newparam[1]
                                # Info 4.a
                                logging.info("Airport::load: Found airport %s '%s' in '%s'.", newparam[4], self.name, scenery_pack_apt)
                                self.scenery_pack = scenery_pack_apt  # remember where we found it
                                self.lines.append(AptLine(line))  # keep first line
                                line = apt_dat.readline()  # next line in apt.dat
                                while line and not re.match("^1 ", line, flags=0):  # while we do not encounter a line defining a new airport...
                                    testline = AptLine(line)
                                    if testline.linecode() is not None:
                                        self.lines.append(testline)
                                    else:
                                        logging.debug("Airport::load: did not load empty line '%s'" % line)
                                    line = apt_dat.readline()  # next line in apt.dat
                                # Info 4.b
                                logging.info("Airport::load: Read %d lines for %s." % (len(self.lines), self.name))
                                self.loaded = True

                        if line:  # otherwize we reached the end of file
                            line = apt_dat.readline()  # next line in apt.dat
                    logging.debug("Airport::load: apt.dat loading finished")
                    apt_dat.close()

            scenery = scenery_packs.readline()

        scenery_packs.close()
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
        logging.debug("Airport::mkRoutingNetwork: added %d vertices" % len(v))

        # 1202 20 21 twoway runway 16L/34R
        # 1204 departure 16L,34R
        # 1204 arrival 16L,34R
        # 1204 ils 16L,34R
        edgeCount = 0   # just for info
        edgeActiveCount = 0
        edge = False
        taxiways = []
        for aptline in self.lines:
            if aptline.linecode() == 1202: # edge
                args = aptline.content().split()
                if len(args) >= 4:
                    src = self.graph.get_vertex(args[0])
                    dst = self.graph.get_vertex(args[1])
                    cost = distance(src, dst)
                    edge = None
                    if len(args) == 5:
                        edge = Edge(src, dst, cost, args[2], args[3], args[4])
                        if "taxiway" in args[3]:
                            taxiways.append(args[4])
                    else:
                        edge = Edge(src, dst, cost, args[2], args[3], "")
                    self.graph.add_edge(edge)
                    edgeCount += 1
                else:
                    logging.debug("Airport::mkRoutingNetwork: not enough params %d %s.", aptline.linecode(), aptline.content())
            elif aptline.linecode() == 1204 and edge:
                args = aptline.content().split()
                if len(args) >= 2:
                    edge.add_active(args[0], args[1])
                    edgeActiveCount += 1
                else:
                    logging.debug("Airport::mkRoutingNetwork: not enough params %d %s.", aptline.linecode(), aptline.content())
            else:
                edge = False

        # Info 6
        logging.info("Airport::mkRoutingNetwork: added %d nodes, %d edges (%d enhanced).", len(vertexlines), edgeCount, edgeActiveCount)
        taxiways2 = sorted(list(set(taxiways)))
        logging.debug("Airport::mkRoutingNetwork: {}".format(str(taxiways2)))
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
        logging.debug("Airport::ldRunways: added %d runways", len(runways.keys()))
        return runways


    def ldHolds(self):
        holds = {}

        if len(self.runways.keys()) > 0:
            rwy = self.runways[list(self.runways.keys())[0]]
            name = "Demo hold " + rwy.name
            holds[name] = Hold(name, rwy.start.lat, rwy.start.lon)

        self.holds = holds
        logging.debug("Airport::ldHolds: added %d holding positions", len(holds.keys()))
        return holds


    def ldRamps(self):
        # 1300  25.26123160  051.61147754 155.90 gate heavy|jets|turboprops A1
        # 1301 E airline
        # 1202 ignored.
        ramps = {}

        ramp = False
        for aptline in self.lines:
            if aptline.linecode() == 1300: # ramp
                args = aptline.content().split()
                if args[3] != "misc":
                    rampName = " ".join(args[5:])
                    ramp = Ramp(rampName, args[2], args[0], args[1])
                    ramp.locationType = args[3]
                    ramp.aircrafts = args[4].split("|")
                    ramps[rampName] = ramp
            elif ramp and aptline.linecode() == 1301: # ramp details
                args = aptline.content().split()
                ramp.icaoType = args[0]
                ramp.operationType = args[1]
                if len(args) > 2 and args[2] != "":
                    ramp.airlines = args[2].split(",")
            else:
                ramp = False

        self.ramps = ramps
        logging.debug("Airport::ldRamps: added %d ramps", len(ramps.keys()))
        return ramps


    # Find
    #
    def findClosestVertex(self, coord):
        return self.graph.findClosestVertex(Point(coord[0],coord[1]))


    def findClosestVertexAhead(self, coord, brng, speed):
        return self.graph.findClosestVertexAhead(Point(coord[0],coord[1]), brng, speed)


    def findClosestVertexAheadGuess(self, coord, brng, speed):
        return self.graph.findClosestVertexAheadGuess(Point(coord[0],coord[1]), brng, speed)


    def findClosestPointOnEdges(self, coord):
        return self.graph.findClosestPointOnEdges(Point(coord[0],coord[1]))


    def findClosestRamp(self, coord):
        closest = None
        shortest = math.inf
        point = Point(coord[0], coord[1])
        for name,ramp in self.ramps.items():
            d = distance(ramp, point)
            if d < shortest:
                shortest = d
                closest = name
        logging.debug("Airport::findClosestRamp: %s at %f", closest, shortest)
        return [closest, shortest]


    def onRunway(self, coord, width=None):
        # Width is in meter
        logging.debug("Airport::onRunway? %s", coord)
        point = Point(coord[0],coord[1])
        for name, rwy in self.runways.items():
            polygon = None
            if width is None:
                polygon = rwy.polygon
            else:  # make a larger area around/along runway (larger than runway width)
                polygon = Polygon.mkPolygon(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
            if pointInPolygon(point, polygon):
                if width:
                    logging.debug("Airport::onRunway: on %s (buffer=%dm)", name, width)
                else:
                    logging.debug("Airport::onRunway: on %s", name)
                return [True, rwy]
            logging.debug("Airport::onRunway: not on %s", name)

        return [False, None]

    def guessMove(self, coord):
        # Return DEPARTURE|ARRIVAL
        onRwy, runway = self.onRunway(coord)
        if onRwy:
            return ARRIVAL
        ret = self.findClosestRamp(coord)
        if ret[1] < DISTANCE_TO_RAMPS:  # meters, we are close to a ramp.
            return DEPARTURE
        return ARRIVAL


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


    def getDestinations(self, mode):
        if mode == DEPARTURE:
            return list( list(self.runways.keys()) + list(self.holds.keys()) )

        return list(self.ramps.keys())


    def mkRoute(self, aircraft, destination, move):
        # Returns (True, route object) or (False, error message)
        # From aircraft position..
        pos = aircraft.position()
        dstpt = None
        runway = None
        if not pos:
            logging.debug("Airport::mkRoute: plane could not be located")
            return (False, "We could not locate your plane.")
        logging.debug("Airport::mkRoute: got starting position %s", pos)

        if move == DEPARTURE:
            src = self.findClosestVertex(pos)
        else:  # arrival
            brng = aircraft.heading()
            speed = aircraft.speed()
            logging.debug("Airport::mkRoute: arrival: trying vertex ahead %f, %f.", brng, speed)
            src = self.findClosestVertexAheadGuess(pos, brng, speed)
            if src is None or src[0] is None:  # tries a less constraining search...
                logging.debug("Airport::mkRoute: no vertex ahead.")
                src = self.findClosestVertex(pos)
            onRwy, runway = self.onRunway(pos)
            if onRwy:
                logging.debug("Airport::mkRoute: Arrival: on runway %s.", runway.name)
            else:
                logging.debug("Airport::mkRoute: Arrival: not on runway.")

        if src is None:
            logging.debug("Airport::mkRoute: no return from findClosestVertex")
            return (False, "Your plane is too far from the taxiways.")

        if src[0] is None:
            logging.debug("Airport::mkRoute: no close vertex")
            return (False, "Your plane is too far from the taxiways.")

        if src[1] > TOO_FAR:
            logging.debug("Airport::mkRoute: plane too far from taxiways")
            return (False, "Your plane is too far from the taxiways.")

        logging.debug("Airport::mkRoute: got starting vertex %s", src)

        # ..to destination
        dst = None
        dstpt = None  # heading after destination reached (heading of runway/takeoff or heading of parking)
        if move == DEPARTURE:
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
            logging.debug("Airport::mkRoute: no return from findClosestVertex")
            return (False, "We could not find parking or ramp %s." % destination)

        if dst[0] is None:
            logging.debug("Airport::mkRoute: no close vertex")
            return (False, "We could not find a taxiway near parking or ramp %s." % destination)

        if dst[1] > TOO_FAR:
            logging.debug("Airport::mkRoute: plane too far from taxiways")
            return (False, "Your destination is too far from the taxiways.")

        logging.debug("Airport::mkRoute: got destination vertex %s", dst)

        # Try to find route (src and dst are vertex ids)
        opts = {"taxiwayOnly": True, "minSizeCode": aircraft.icaocat}
        route = Route(self.graph, src[0], dst[0], move, opts)
        logging.debug("Airport::mkRoute: route options {}".format(route.options))
        route.find()
        if not route.found() and len(opts.keys()) > 0:  # if there were options, we try to find a route without option
            logging.debug("Airport::mkRoute: route not found with options, trying without taxiway option.")
            route.options = {"minSizeCode": aircraft.icaocat}
            logging.debug("Airport::mkRoute: route options {}".format(route.options))
            route.find()

        if not route.found() and len(opts.keys()) > 0:
            # if there were options, we try to find a route without option
            # @todo implement warning that the taxiway is to small!
            logging.debug("Airport::mkRoute: route not found with options, trying without any option.")
            route.options = {}
            logging.debug("Airport::mkRoute: route options {}".format(route.options))
            route.find()

        if route.found():  # third attempt may have worked
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
