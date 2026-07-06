# Airport Utility Class
# Airport information container: name, taxi routes, runways, ramps, holding positions, etc.
#
import os
import re
import math
from io import StringIO
from typing import Tuple
from importlib.metadata import version

from followthegreens import graph

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

has_xplane_airports = False
try:
    from xplane_airports.AptDat import AptDat, Airport
    from xplane_airports.AptDetail import DetailedAirport

    has_xplane_airports = True
except ImportError:
    print("xplane_airports not loaded")


from .globals import (
    TAXIWAY_DIRECTION,
    logger,
    get_global,
    Status,
    Error,
    NoError,
    DISTANCE_TO_RAMPS,
    TAXIWAY_TYPE,
    RUNWAY_BUFFER_WIDTH,
    AIRPORT,
    MOVEMENT,
    RABBIT,
    LIGHTS_AHEAD,  # for default values if no fmcar
    RABBIT_LENGTH,
    RABBIT_SPEED,
    TAXIWAY_WIDTH_CODE,
)
from .geo import Point, Line, Polygon, destination, distance, pointInPolygon
from .graph import Graph, Edge, Vertex
from .cursor import CursorType, Cursor, FOLLOW_ME_CARS, FM_CAR_PREFERENCE
from .route import Route

SYSTEM_DIRECTORY = "."

REQUIRED_XPLANE_AIRPORTS = "5.2.2"
INSTALL_WITH_XPLANE_AIRPORTS = False


# Add XP 12 location for Global Airports
DEFAULT_AIRPORTS_FILE = os.path.join(
    SYSTEM_DIRECTORY,
    "Global Scenery",
    "Global Airports",
    "Earth nav data",
    "apt.dat",
)


class Runway(Line):

    INSIDE = 50  # m

    # A place to be. But not too long.
    def __init__(self, name, width, lat, lon, dt, dbo, lat2, lon2, pol):
        Line.__init__(self, Point(lat, lon), Point(lat2, lon2))
        self.name = name
        self.width = width
        self.displaced_threshold = float(dt)
        self.overrun = float(dbo)
        if pol is None:
            if width is not None and width > 0:
                self.polygon = Polygon.new(lat, lon, lat2, lon2, width)
        else:
            self.polygon = pol
        self.threshold = self.start
        self.threshold_alt = self.start
        self.first_exit = self.threshold
        self.mkThreshold()
        self.mkThresholdAlt()

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

    def mkThresholdAlt(self):
        # If no displaced threshold, the threshold is the start
        self.threshold_alt = destination(src=self.start, brngDeg=self.bearing(), d=self.INSIDE)
        logger.debug(f"inside alternate threshold at {round(self.INSIDE,1)}m")

    def runwayExits(self, graph: Graph) -> set:
        # return vertex that this on taxiway network, that is NOT a on a runway edge
        # and that is the closest to runway threshold
        # Select vertices from segments that are not runway
        # Select vertices that are "inside" a buffer around the runway
        # Select the vertex closest to the start or threshold
        buffer = Polygon.new(self.start.lat, self.start.lon, self.end.lat, self.end.lon, RUNWAY_BUFFER_WIDTH)
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
    """Airport represetation (limited to FTG needs)

    Note: Should be split with generic non dependant airport and airport with routing, dependant on Graph
    """

    MTWYLDWC = 10  # count

    def __init__(self, icao, prefs: dict = {}):
        self.icao = icao.upper()
        self.prefs = prefs
        self.name = ""
        self.apt_data = None
        self.cursor_type = None  # keep track of meta data of current cursor (turn radius, speeds, etc.)
        self.atc_ground = None
        self.latitude = 0
        self.longitude = 0
        self.altitude = 0  # ASL, in meters
        self.loaded = False
        self.installed = False
        self.scenery_pack = False
        self.lines = []
        self.graph = Graph(name="taxiways")
        self.roads = Graph(name="service roads")
        self.runways = {}
        self.holds = {}
        self.ramps = {}

        self.status = False

        #
        # PREFERENCES - Fetched by LightString
        # Set sensible default value from global preferences
        self.use_threshold = get_global("USE_THRESHOLD", self.prefs)
        if self.use_threshold is None:
            self.use_threshold = False
        self.use_threshold_pref = False

        self.use_car = get_global("USE_CAR", self.prefs)
        if self.use_car is None:
            self.use_car = False

        self.distance_between_green_lights = get_global(AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value, self.prefs)  # meters for follow_the_greens()
        self.distance_between_taxiway_lights = get_global(AIRPORT.DISTANCE_BETWEEN_LIGHTS.value, self.prefs)  # meters, for show_taxiways()

        self.lights_ahead_pref = False
        self.rabbit_length_pref = False
        self.rabbit_speed_pref = False
        self.distance_between_green_lights_pref = False
        self.distance_between_taxiway_lights_pref = False
        self.lights_ahead = get_global(RABBIT.LIGHTS_AHEAD.value, self.prefs)
        self.rabbit_length = get_global(RABBIT.LENGTH.value, self.prefs)
        self.rabbit_speed = get_global(RABBIT.SPEED.value, self.prefs)
        # Info 4
        # Fine tune for specific airport(s)
        self.setPreferences()
        logger.debug(f"airport rabbit: length={self.rabbit_length}L, speed={self.rabbit_speed}s, ahead={self.lights_ahead}L")
        logger.debug(f"airport rabbit: btw greens={self.distance_between_green_lights}m, whole net={self.distance_between_taxiway_lights}m")

    def position(self) -> tuple:
        if self.apt_data is not None:
            return (self.apt_data.latitude, self.apt_data.longitude, self.altitude)
        return (self.latitude, self.longitude, self.altitude)

    def prepare(self, filename: str | None = None) -> Status:
        if filename is None:
            status = self.load()
        else:
            logger.debug(f"loading from file {filename}")
            status = self.loadFile(filename)
        if not status:
            return Error(f"We could not find airport named '{self.icao}'.")

        # status = self.load_smooth()
        # if not status:
        #     return Error(f"We could not find smooth taxiway lines for airport named '{self.icao}'.")

        # Info 5
        # logger.debug(f"has ATC {self.hasATC()}")  # actually, we don't care.

        if not self.installed:
            status = self.mkRoutingNetwork()
            if not status:
                return Error(f"We could not build taxiway network for {self.icao}.")

            status = self.ldRunways()
            if len(status) == 0:
                return Error(f"We could not find runways for {self.icao}.")
            # Info 7
            logger.debug(f"runways: {status.keys()}")

            status = self.ldHolds()
            logger.debug(f"holding positions: {status.keys()}")

            status = self.ldRamps()
            if len(status) == 0:
                return Error(f"We could not find ramps/parking for {self.icao}.")
            # Info 8
            logger.debug(f"ramps: {status.keys()}")

        self.status = True
        return NoError("Airport ready")

    def usable(self, move: MOVEMENT | None = None) -> bool:
        # should check has taxiways, has runway, has at least one ramp?
        if not self.graph.usable():
            logger.debug("graph not usable")
            return False
        ok = False
        if move is not None:
            if move == MOVEMENT.DEPARTURE:
                ok = len(self.runways) > 0
            else:
                ok = len(self.ramps) > 0
        else:
            ok = True
        return ok and self.status

    def hasPreferences(self) -> bool:
        return self.icao in self.prefs.get("Airports", {})

    def setPreferences(self):
        # Local airport preferences override global preferences
        if not self.hasPreferences():
            logger.debug("airport has no preference")
            return
        apt = self.prefs.get("Airports", {})
        prefs = apt.get(self.icao, {})
        if len(prefs) > 0:
            logger.debug(f"airport {self.icao} preferences: {prefs}")
            if prefs is not None:
                self.use_car = prefs.get("USE_CAR", self.use_car)
                if AIRPORT.USE_THRESHOLD in prefs:
                    self.use_threshold = prefs.get(AIRPORT.USE_THRESHOLD)
                    self.use_threshold_pref = True
                if AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value in prefs:
                    self.distance_between_green_lights = prefs[AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value]
                    self.distance_between_green_lights_pref = True
                if AIRPORT.DISTANCE_BETWEEN_LIGHTS.value in prefs:
                    self.distance_between_taxiway_lights = prefs[AIRPORT.DISTANCE_BETWEEN_LIGHTS.value]
                    self.distance_between_taxiway_lights_pref = True
                if RABBIT.LIGHTS_AHEAD.value in prefs:
                    self.lights_ahead = prefs[RABBIT.LIGHTS_AHEAD.value]
                    self.lights_ahead_pref = True
                if RABBIT.LENGTH.value in prefs:
                    self.rabbit_length = prefs[RABBIT.LENGTH.value]
                    self.rabbit_length_pref = True
                if RABBIT.SPEED.value in prefs:
                    self.rabbit_speed = prefs[RABBIT.SPEED.value]
                    self.rabbit_speed_pref = True
                return
        # Generic
        if len(apt) > 0:
            logger.debug(f"airport preferences: {apt}")
            if AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value in apt:
                self.distance_between_green_lights = apt[AIRPORT.DISTANCE_BETWEEN_GREEN_LIGHTS.value]

    def resetPreferences(self):
        self.lights_ahead_pref = False
        self.rabbit_length_pref = False
        self.rabbit_speed_pref = False
        self.distance_between_green_lights_pref = False
        self.distance_between_taxiway_lights_pref = False
        self.setPreferences()

    def fmcar(self, ftg) -> Cursor | None:
        # fmcar should be **created** before lights are placed because
        # if fmcar, distance_between_green_lights will be hardcoded to convenient value (~10m)
        #
        # did we ask for fmcar?
        if not ftg.use_car:
            logger.info("no follow me car")
            return None
        # get car definition
        uifmcar = ftg.ui.fmcar
        fmcar = FOLLOW_ME_CARS.get(uifmcar)
        logger.debug(f"UI FM car {uifmcar}")
        if fmcar is None or len(fmcar) == 0 or uifmcar == FM_CAR_PREFERENCE:  # none provided through UI
            fmcar = self.prefs.get("FollowMeCar", {})
            logger.debug(f"follow me car from preferences: {fmcar}")
        if len(fmcar) == 0:
            logger.info("no follow me car found")
            return None
        adj = ""
        if self.distance_between_green_lights > self.MTWYLDWC:  # min twy light distance with/when fmcar
            adj = f", distance between taxiway lights reduced from {self.distance_between_green_lights}m to {self.MTWYLDWC}m"
            self.distance_between_green_lights = self.MTWYLDWC
            self.distance_between_green_lights_pref = True
        logger.info(f"using fmcar {fmcar}{adj}")
        # If developer mode, show lights as well
        self.cursor_type = CursorType(**fmcar)
        self.cursor_type.indicator = ftg.ui.use_indicator  # transfert from UI
        return Cursor(self.cursor_type, ftg)

    def ensureDev(self) -> bool:
        # returns has_light if follow me car in use
        if self.prefs.get("DEVELOPER_PREFERENCE_ONLY", False):
            self.lights_ahead = 0
            self.lights_ahead_pref = True
            self.rabbit_length = 10
            self.rabbit_length_pref = True
            self.rabbit_speed = 0.166
            self.rabbit_speed_pref = True
            logger.debug(f"and lights for development (forced rabbit_speed={self.rabbit_speed} != 0)")
            return True
        return False

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

        if os.path.exists(DEFAULT_AIRPORTS_FILE) and os.path.isfile(DEFAULT_AIRPORTS_FILE):
            APT_FILES["default airports"] = DEFAULT_AIRPORTS_FILE
        # else:
        #     logger.warning(f"default airport file {DEFAULT_AIRPORTS} not found")
        # logger.debug(f"APT files: {APT_FILES}")

        for scenery, filename in APT_FILES.items():
            if self.loaded:
                return self.loaded
            logger.debug(f"scenery pack {scenery.strip()}..")
            self.loadFile(filename=filename)

        return self.loaded

    def loadXplaneAirportFromLines(self) -> bool:
        # See https://gateway.x-plane.com/api
        if has_xplane_airports:
            if len(self.lines) > 0:
                try:
                    logger.warning(f"xplane_airports not loading from default file {DEFAULT_AIRPORTS_FILE} for performance reason")
                    logger.warning(f"xplane_airports loading from {len(self.lines)} target lines read")
                    lines = [f"{l.linecode()} {l.content()}" for l in self.lines]
                    apt_data = DetailedAirport.from_lines(dat_lines=lines, from_file_name=DEFAULT_AIRPORTS_FILE)
                    logger.info(f"xplane_airports read {self.icao}: {apt_data.from_file} {apt_data.name} {apt_data.id}")
                    logger.info(f"xplane_airports {self.icao}: has taxi routes: {apt_data.has_taxi_route}")  #  {dir(apt_data)}
                    self.apt_data = apt_data
                    return self.mkAirport()
                except:
                    logger.error(f"could not load {self.icao} from lines", exc_info=True)
                    return False

    def loadXplaneAirport(self, filename) -> bool:
        # See https://gateway.x-plane.com/api
        if has_xplane_airports and filename != DEFAULT_AIRPORTS_FILE:
            self.apt_data = None
            logger.info(f"xplane_airports version {version('xplane_airports')}")
            try:
                apt_dat = AptDat(path_to_file=filename)
                logger.debug(f"AptDat: {len(apt_dat.airports)}")
                apt_data = DetailedAirport.from_airport(airport=apt_dat[self.icao])
                logger.info(f"xplane_airports read {self.icao}: {apt_data.from_file} {apt_data.name} {apt_data.id}")
                logger.info(f"xplane_airports {self.icao}: has taxi routes: {apt_data.has_taxi_route}")  #  {dir(apt_data)}
                if hasattr(apt_data, "taxi_network"):
                    if apt_data.taxi_network is not None:
                        logger.debug(f"taxi network: {len(apt_data.taxi_network.nodes)} nodes, {len(apt_data.taxi_network.edges)} edges")
                if hasattr(apt_data, "road_network"):
                    if apt_data.road_network is not None:
                        logger.debug(f"road network: {len(apt_data.road_network.nodes)} nodes, {len(apt_data.road_network.edges)} edges")
                self.apt_data = apt_data
                return self.mkAirport()
            except:
                logger.error(f"could not load {self.icao} from {filename}", exc_info=True)
        else:
            logger.warning("xplane_airports not installed")
        return False

    def mkAirport(self) -> bool:

        # service roads
        roads = Graph("roads from xplane_airports")
        if self.apt_data is not None:
            for k, v in self.apt_data.road_network.nodes.items():
                roads.add_vertex(node=str(k), point=Point(float(v.lat), float(v.lon)), usage="road", name=str(k))
            for e in self.apt_data.road_network.edges:
                src = roads.get_vertex(str(e.node_begin))
                dst = roads.get_vertex(str(e.node_end))
                if src is not None and dst is not None:
                    cost = distance(src, dst)
                    edge = Edge(src=src, dst=dst, cost=0.0, direction="oneway" if e.one_way else "twoway", usage="road", name=e.name)
                    roads.add_edge(edge)
                else:
                    logger.warning(f"{e.node_begin} or {e.node_end} not found ({src}, {dst})")
        roads.stats()

        # Truck parkings
        parkings = {}
        for p in self.apt_data.truck_parkings:
            parkings[p.name] = p
        logger.debug(f"xplane_airports added {len(parkings)} truck parkings")

        # Destination
        destinations = {}
        for p in self.apt_data.truck_destinations:
            destinations[p.name] = p
        logger.debug(f"xplane_airports added {len(destinations)} truck destinations")

        # taxiways
        graph = Graph("taxiways from xplane_airports")
        if self.apt_data is not None:
            for k, v in self.apt_data.taxi_network.nodes.items():
                graph.add_vertex(node=str(k), point=Point(float(v.lat), float(v.lon)), usage=v.usage, name=str(k))
            for e in self.apt_data.taxi_network.edges:
                src = graph.get_vertex(str(e.node_begin))
                dst = graph.get_vertex(str(e.node_end))
                if src is not None and dst is not None:
                    cost = distance(src, dst)
                    edge = Edge(src=src, dst=dst, cost=0.0, direction="oneway" if e.one_way else "twoway", usage="road", name=e.name)
                    edge.width_code = TAXIWAY_WIDTH_CODE(e.icao_width.value) if e.icao_width else "C"
                    # Add active
                    if e.active_zones is not None:
                        for z in e.active_zones:
                            edge.add_active(z.zone, z.runways)
                    graph.add_edge(edge)
                else:
                    logger.warning(f"{e.node_begin} or {e.node_end} not found ({src}, {dst})")
        graph.stats()

        # Ramps
        ramps = {}
        for r in self.apt_data.startup_locations:
            ramp = Ramp(name=r.name, heading=r.heading, lat=r.lat, lon=r.lon)
            ramp.locationType = r.type_str
            ramp.aircrafts = r.aircraft_types
            ramp.icaoType = r.icao_code
            ramp.operationType = r.oper_type
            ramp.airlines = r.airline
            ramps[r.name] = ramp
        logger.debug(f"xplane_airports added {len(ramps)} ramps")

        # Runways
        runways = {}
        for r in self.apt_data.land_runways:
            runway = Polygon.new(lat1=r.lat, lon1=r.lon, lat2=r.end_lat, lon2=r.end_lon, width=r.width)
            runways[r.name] = Runway(name=r.name, width=r.width, lat=r.lat, lon=r.lon, dt=r.threshold, dbo=r.overrun, lat2=r.end_lat, lon2=r.end_lon, pol=runway)
        logger.debug(f"xplane_airports added {len(runways)} runways")

        # Holding position
        holds = {}
        logger.debug(f"xplane_airports added {len(holds)} holding positions")

        if INSTALL_WITH_XPLANE_AIRPORTS and not self.installed:
            self.graph = graph
            self.roads = roads
            self.runways = runways
            self.ramps = ramps
            self.holds = holds
            self.installed = True
        return self.installed

    def loadFile(self, filename) -> bool:
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
                    logger.info(f"found airport {newparam[4]} '{self.name}' in '{filename}'")
                    self.scenery_pack = filename  # remember where we found it
                    if self.loadXplaneAirport(filename=filename):
                        logger.info(f"{self.icao} installed with xplane_airports {version('xplane_airports')}")
                        # self.loaded = True
                        # return self.loaded
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

        if filename == DEFAULT_AIRPORTS_FILE:
            if self.loadXplaneAirportFromLines():
                logger.info(f"{self.icao} installed with xplane_airports {version('xplane_airports')}")

        return self.loaded

    def dumpAptFile(self, filename):
        aptfile = open(filename, "w")
        # note: need to write file header
        # I
        # 1200 ...
        #
        for line in self.lines:
            aptfile.write(f"{line.linecode()} {line.content()}\n")
        # note: need to write file footer
        # 99
        aptfile.close()

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
        def addVertex(aptline):  # same for both taxiways and service roads
            args = aptline.content().split()
            return self.graph.add_vertex(node=args[3], point=Point(args[0], args[1]), usage=args[2], name=" ".join(args[3:]))

        def addRoads(aptline):  # same for both taxiways and service roads
            args = aptline.content().split()
            return self.roads.add_vertex(node=args[3], point=Point(args[0], args[1]), usage=args[2], name=" ".join(args[3:]))

        vertexlines = list(filter(lambda x: x.linecode() == 1201, self.lines))
        v = list(map(addVertex, vertexlines))
        logger.debug(f"added {len(v)} vertices")

        vr = list(map(addRoads, vertexlines))
        logger.debug(f"added {len(vr)} service road vertices")

        truckparkings = list(filter(lambda x: x.linecode() == 1400, self.lines))
        vp = list(map(addRoads, truckparkings))
        logger.debug(f"added {len(vp)} truck parkings")

        truckdestinations = list(filter(lambda x: x.linecode() == 1401, self.lines))
        vd = list(map(addRoads, truckdestinations))
        logger.debug(f"added {len(vd)} truck destinations")

        # 1202 20 21 twoway runway 16L/34R
        # 1204 departure 16L,34R
        # 1204 arrival 16L,34R
        # 1204 ils 16L,34R
        # 1206 20 21 twoway
        edgeCount = 0  # just for info
        roadEdgeCount = 0
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
                    logger.debug(f"not enough params {aptline.linecode()} {aptline.content()}")
            elif aptline.linecode() == 1204 and edge is not None:
                args = aptline.content().split()
                if len(args) >= 2:
                    edge.add_active(args[0], args[1])
                    edgeActiveCount += 1
                else:
                    logger.debug(f"not enough params {aptline.linecode()} {aptline.content()}")
            elif aptline.linecode() == 1206:  # edge
                args = aptline.content().split()
                if len(args) >= 3:
                    src = self.roads.get_vertex(args[0])
                    dst = self.roads.get_vertex(args[1])
                    cost = distance(src, dst)
                    # src, dst, cost, direction, usage, name
                    edge = Edge(src=src, dst=dst, cost=cost, direction=args[2], usage="road", name="")
                    self.roads.add_edge(edge)
                    if len(args) > 3:
                        logger.debug(f"line code {aptline.linecode()}: extra params: {args[3:]}, ignored")
                    roadEdgeCount += 1
                else:
                    logger.debug(f"not enough params {aptline.linecode()} {aptline.content()}")
            else:
                edge = None

        # Info 6
        self.stats()
        logger.info(f"added {len(vertexlines)} nodes, {edgeCount} edges ({edgeActiveCount} enhanced), {roadEdgeCount} road edges")
        self.graph.stats()
        self.roads.stats()
        return True

    def ldRunways(self):
        #     0     1 2 3    4 5 6 7    8            9               10 11  1213141516   17           18              19 20  21222324
        # 100 60.00 1 1 0.25 1 3 0 16L  25.29609337  051.60889908    0  300 2 2 1 0 34R  25.25546269  051.62677745    0  306 3 2 1 0
        runways = {}

        for aptline in self.lines:
            if aptline.linecode() == 100:  # runway
                args = aptline.content().split()
                runway = Polygon.new(lat1=args[8], lon1=args[9], lat2=args[17], lon2=args[18], width=float(args[0]))
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

    def onRunway(self, position, width: float | None = None, heading: float | None = None) -> Runway | None:
        # Width is in meter
        logger.debug(f"onRunway? position={position}, width={width}, heading={heading}")
        point = Point(position[0], position[1])

        if heading is not None:
            for name, rwy in self.runways.items():
                polygon = None
                if width is None:
                    polygon = rwy.polygon
                else:  # make a larger area around/along runway (larger than runway width)
                    polygon = Polygon.new(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
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
                            return rwy
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
                polygon = Polygon.new(rwy.start.lat, rwy.start.lon, rwy.end.lat, rwy.end.lon, float(width))
            if polygon is not None:
                if pointInPolygon(point, polygon):
                    logger.debug(f"on {name}, no orientation (rwy width={rwy.width}m)")
                    return rwy
                else:
                    logger.debug(f"not on runway {name}")  # , {polygon.coords()}
            else:
                logger.debug(f"no polygon for runway {name}")

        logger.debug("does not appear to be on any runway")
        return None

    def guessMove(self, coord) -> MOVEMENT:
        # Info 10
        runway = self.onRunway(coord)
        if runway is not None:
            logger.info("aircraft appears to be on runway, assuming arrival")
            return MOVEMENT.ARRIVAL
        res = self.findClosestRamp(coord)
        if res[1] < DISTANCE_TO_RAMPS:  # meters, we are close to a ramp.
            closest = ""
            if type(res[0]) is str:
                closest = f" close to stand {res[0]}"
            logger.info(f"aircraft appears to be on apron{closest}, assuming departure")
            return MOVEMENT.DEPARTURE
        logger.info("aircraft is far from known ramps, assuming arrival")
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

    def getDestinations(self, move: MOVEMENT) -> list:
        if move == MOVEMENT.DEPARTURE:
            return list(list(self.runways.keys()) + list(self.holds.keys()))

        return list(self.ramps.keys())

    def mkRoute(self, aircraft, destination, move: MOVEMENT, use_strict_mode: bool) -> Status:
        # Returns NoError(route object) or Error(error message)
        # From aircraft position..
        arrival_runway = None
        if move == MOVEMENT.ARRIVAL:
            pos = aircraft.position()
            if not pos:
                logger.debug("plane could not be located")
                return Error("We could not locate your aircraft.")
            hdg = aircraft.heading()
            arrival_runway = self.onRunway(pos, width=RUNWAY_BUFFER_WIDTH, heading=hdg)

        # ..to destination
        dst_pos = None
        dst_type = ""
        if move == MOVEMENT.DEPARTURE:
            if destination in self.runways.keys():
                dst_pos = self.getRunway(destination)
                if dst_pos is None:  # we sure to find one because first test
                    return Error(f"We could not find runway {destination}.")
                dst_type = "runway"
            elif destination in self.holds.keys():
                dst_pos = self.holds[destination].coords()
                if dst_pos is None:  # we sure to find one because first test
                    return Error(f"We could not find hold position {destination}.")
                dst_type = "hold"
        else:
            dst_pos = self.getRamp(destination)
            if dst_pos is None:
                return Error(f"We could not find stand {destination}.")
            dst_type = "stand"

        route = Route.Find(self.graph, aircraft, arrival_runway, dst_pos, dst_type, move, use_strict_mode, self.use_threshold)

        if route.found():
            route.arrival_runway = arrival_runway
            if dst_pos is not None and dst_type == "runway":
                route.departure_runway = dst_pos
            logger.debug(f"route {route.text(destination=destination)}")
            r = None if self.cursor_type is None else self.cursor_type.turn_radius
            route.build(acf_speed=aircraft.avgTaxiSpeed(), radius=r)
            return NoError(route)

        return Error("We could not find a route to your destination.")

    def mkRouteExternal(self, aircraft, start, destination, route: list, move: MOVEMENT) -> Status:
        route = [str(i) for i in route]

        route_ext = Route(graph=self.graph)
        route_ext.route = route  # todo: check all vertices are known
        route_ext.move = move

        vext = [i for i in route if i not in self.graph.vert_dict]
        logger.debug(f"unknown vertices: {vext}")
        if len(vext) > 0:
            return Error(f"unknown vertices in route: {vext}")

        if move == MOVEMENT.DEPARTURE:
            # From stand..
            src_pos = None
            src_type = ""
            if start in self.ramps.keys():
                src_pos = self.ramps[start]
                if src_pos is None:  # we sure to find one because first test
                    return Error(f"We could not find stand {start}.")
                src_type = "stand"
            route_ext.precise_start = src_pos

            # ..to runway
            dst_pos = None
            dst_type = ""
            if destination in self.runways.keys():
                rwy = self.getRunway(destination)
                if rwy is None:  # we sure to find one because first test
                    return Error(f"We could not find runway {rwy}.")
                dst_pos = rwy.threshold if self.use_threshold else rwy.start
                route_ext.precise_end = dst_pos
                route_ext.departure_runway = rwy
            elif destination in self.holds.keys():
                dst_pos = self.holds[destination].coords()
                if dst_pos is None:  # we sure to find one because first test
                    return Error(f"We could not find hold position {destination}.")
                route_ext.precise_end = dst_pos
            else:
                return Error(f"We could not find destination {destination}.")
        else:  # ARRIVAL
            # From runway..
            src_pos = aircraft.position_point()
            src_type = "aircraft"
            if start in self.runways.keys():
                rwy = self.runways[start]
                if rwy is None:  # we sure to find one because first test
                    return Error(f"We could not find runway {start}.")
                route_ext.arrival_runway = rwy
                # src_pos = rwy.end
                # src_type = "runway"
            route_ext.precise_start = src_pos

            # ..to stand
            dst_pos = None
            dst_type = ""
            if destination in self.ramps.keys():
                dst_pos = self.ramps[destination]
                if dst_pos is None:  # we sure to find one because first test
                    return Error(f"We could not find stand {destination}.")
                route_ext.precise_end = dst_pos
                dst_type = "stand"

        r = None if self.cursor_type is None else self.cursor_type.turn_radius
        route_ext.build(acf_speed=aircraft.avgTaxiSpeed(), radius=r)

        logger.info(f"external route built from {start} to {destination}")
        return NoError(route_ext)

    def mkAdhocRouteExternal(self, aircraft, start, destination, route: list | dict, move: MOVEMENT) -> Status:
        #
        g = Graph(name="adhoc")
        # Make vertices
        local_route = []
        if type(route) is dict:  # route is either a linestring feature (expanded into its points) or a collection of point features
            i = 0
            for f in route["features"]:
                if f["geometry"]["type"] == "Point":
                    c = f["geometry"]["coordinates"]
                    g.add_vertex(node=str(i), point=Point(lat=c[1], lon=c[0]), usage="", name="")
                    local_route.append(str(i))
                    i += 1
                elif f["geometry"]["type"] == "LineString":
                    last = None
                    for c in f["geometry"]["coordinates"]:
                        this = g.add_vertex(node=str(i), point=Point(lat=c[1], lon=c[0]), usage="", name="")
                        local_route.append(str(i))
                        i += 1
                        if last is not None:
                            d = distance(last, this)
                            e = Edge(src=last, dst=this, cost=d, direction=TAXIWAY_DIRECTION.BOTH, usage="taxiway_C", name="T")
                            g.add_edge(e)
                        last = this
                else:
                    logger.info(f"geojson feature {f} ignored")
        else:
            i = 0
            for c in route:
                g.add_vertex(node=str(i), point=Point(lat=c[0], lon=c[1]), usage="", name="")
                i += 1
            # Make edges
            last = g.get_vertex(n="0")
            for c in g.vert_dict.values():
                d = distance(last, c)
                e = Edge(src=last, dst=c, cost=d, direction=TAXIWAY_DIRECTION.BOTH, usage="taxiway_C", name="T")
                g.add_edge(e)
                last = c
            # Make route
            local_route = [str(i) for i in range(len(g.vert_dict))]

        g.stats()
        logger.debug(f"route {local_route}")

        # Check
        logger.debug("free route proximity to taxiways..")
        STICK_TO_TAXIWAYS = True
        STICKING_DISTANCE = 20.0  # meters
        for k, v in g.vert_dict.items():
            n, d, l = self.graph.findClosestPointOnEdges(v)
            if n is not None:
                logger.debug(f"point {k} at {round(d, 1)}m from taxiway {l.name}")
                if STICK_TO_TAXIWAYS and d < STICKING_DISTANCE:
                    logger.debug("sticking")
                    v.lat = n.lat
                    v.lon = n.lon
            else:
                logger.debug(f"point {k} not close to taxiway")
        logger.debug("..done")

        # Create Adhoc Route
        route_ext = Route(graph=g)
        route_ext.route = local_route
        route_ext.move = move
        # Add meta-data
        route_ext.precise_start = g.get_vertex(n="0")
        route_ext.precise_end = g.get_vertex(n=str(len(g.vert_dict) - 1))
        #
        r = None if self.cursor_type is None else self.cursor_type.turn_radius
        route_ext.build(acf_speed=aircraft.avgTaxiSpeed(), radius=r)

        logger.info(f"external adhoc route built from {start} to {destination}")
        return NoError(route_ext)

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

    def hasTaxiwayRoutes(self):
        # Return boolean on taxiway network existence
        return len(self.graph.edges_arr) > 0  # weak but ok for now

    def getLines(self, code):
        # Returns all lines with supplied linecode
        return list(filter(lambda x: x.linecode() == code, self.lines))
