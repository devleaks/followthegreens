# Light setup utility Class
# Keep track of all lights set for FTG, their status, etc. Manipulate them as well.
#
import math
import json
import os.path
from random import randint

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .geo import Point, distance, bearing, destination, convertAngleTo360, pointInPolygon
from .globals import (
    logger,
    get_global,
    DISTANCE_BETWEEN_STOPLIGHTS,
    FTG_SPEED_PARAMS,
    LIGHT_TYPE,
    LIGHT_TYPE_OBJFILES,
    MOVEMENT,
    RABBIT_MODE,
    TAXIWAY_ACTIVE,
    TAXIWAY_DIRECTION,
    TAXIWAY_WIDTH,
    TAXIWAY_WIDTH_CODE,
)

HARDCODED_MIN_DISTANCE = 50  # meters
HARDCODED_MIN_TIME = 0.1  # secs
HARDCODED_MIN_RABBIT_LENGTH = 6  # lights

SPECIAL_DEBUG = False


class LightType:
    # A light to follow, or a stopbar light
    # Holds a referece to its instance

    DEFAULT_TEXTURE_CODE = 3
    TEXTURES = [
        "0.5  1.0  1.0  0.5",  # 0: TOP RIGHT
        "0.0  1.0  0.5  0.5",  # 1: TOP LEFT
        "0.5  0.5  1.0  0.0",  # 2: BOT RIGHT
        "0.0  0.5  0.5  0.0",  # 3: BOT LEFT
    ]

    def __init__(self, name, filename):
        self.name = name
        self.filename = filename
        self.obj = None

    def load(self):
        if not self.obj:
            curr_dir = os.path.dirname(os.path.realpath(__file__))
            real_path = os.path.join(curr_dir, "lights", self.filename)
            self.obj = xp.loadObject(real_path)
            logger.debug(f"loadObject {self.filename} loaded")

    def unload(self):
        if self.obj:
            xp.unloadObject(self.obj)
            self.obj = None
            logger.debug(f"unloadObject {self.name} unloaded")

    @staticmethod
    def create(name: str, color: tuple, size: int, intensity: int, texture: int | list | tuple, texture_file: str = "lights.png") -> str:
        """Creates a light object file with content derived from parameters.

        Args:
            name (str): file name of light object
            color (tuple): RGB colors, each value between 0 and 1.
            size (int): relative size of light, 10 to 100.
            intensity (int): number of times the lihgt unit is releated. The more the brighter and the less natural...
            texture| list | tuple ([type]): Texture region code for normal texture file (0, 1, 2 or 3) or formal tuple pointing at texture area in texture file
            texture_file (str): Texture file (default: `"lights.png"`), ideally a PNG file.

        returns:
            str: file name of ligght object
        """
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        fn = os.path.join(curr_dir, "lights", name)
        fsize = round(size / 100, 2)
        alpha = 1
        with open(fn, "w") as fp:
            print(
                f"""I
800
OBJ

TEXTURE {texture_file}
TEXTURE_LIT {texture_file}

POINT_COUNTS    0 0 0 0

""",
                file=fp,
            )
            ltext = LightType.TEXTURES[LightType.DEFAULT_TEXTURE_CODE]  # default
            if type(texture) in [list, tuple]:
                ltext = texture
            elif type(texture) is int:
                ltext = LightType.TEXTURES[texture]
            ls = f"LIGHT_CUSTOM 0 1 0 {round(color[0],2)} {round(color[1],2)} {round(color[2],2)} {alpha} {fsize} {ltext} UNUSED"
            logger.debug(f"create LIGHT_CUSTOM {name} ({size}, {intensity}): {ls}")
            for i in range(intensity):
                print(ls, file=fp)
        return name


class Light:
    # A light to follow, or a stopbar light
    # Holds a referece to its instance
    def __init__(self, lightType, position, heading, index):
        self.lightType = lightType
        self.index = index
        self.position = position
        self.heading = heading  # this should be the heading to the previous light
        self.params = []  # LIGHT_PARAM_DEF       full_custom_halo        9   R   G   B   A   S       X   Y   Z   F
        self.drefs = []
        self.lightObject = None
        self.xyz = None
        self.instance = None
        self.instanceOff = None

    def groundXYZ(self, latstr, lonstr, altstr):
        lat, lon, alt = (float(latstr), float(lonstr), float(altstr))
        (x, y, z) = xp.worldToLocal(lat, lon, alt)  # this return proper altitude
        probe = xp.createProbe(xp.ProbeY)
        info = xp.probeTerrainXYZ(probe, x, y, z)
        if info.result == xp.ProbeError:
            logger.debug("Terrain error")
            (x, y, z) = xp.worldToLocal(lat, lon, alt)
        elif info.result == xp.ProbeMissed:
            logger.debug("Terrain Missed")
            (x, y, z) = xp.worldToLocal(lat, lon, alt)
        elif info.result == xp.ProbeHitTerrain:
            # logger.debug("Terrain info is [{}] {}".format(info.result, info))
            (x, y, z) = (info.locationX, info.locationY, info.locationZ)
            # (lat, lng, alt) = xp.localToWorld(info.locationX, info.locationY, info.locationZ)
            # logger.debug('lat, lng, alt is {} feet'.format((lat, lng, alt * 3.28)))
        xp.destroyProbe(probe)
        # (x, y, z) = xp.worldToLocal(float(light.position.lat), float(light.position.lon), alt)
        return (x, y, z)

    def place(self, lightType, lightTypeOff=None):
        self.lightObject = lightType.obj
        pitch, roll, alt = (0, 0, 0)
        (x, y, z) = self.groundXYZ(self.position.lat, self.position.lon, alt)
        self.xyz = (x, y, z, pitch, self.heading, roll)
        if lightTypeOff and not self.instanceOff:
            self.instanceOff = xp.createInstance(lightTypeOff.obj, self.drefs)
            xp.instanceSetPosition(self.instanceOff, self.xyz, self.params)
            # logger.debug("LightString::place: light off placed")

    def on(self):
        if not self.xyz:
            logger.debug("light not placed")
            return
        if self.lightObject and not self.instance:
            self.instance = xp.createInstance(self.lightObject, self.drefs)
            xp.instanceSetPosition(self.instance, self.xyz, self.params)

    def off(self):
        if self.instance:
            xp.destroyInstance(self.instance)
            self.instance = None

    def destroy(self):
        self.off()
        if self.instanceOff:
            xp.destroyInstance(self.instanceOff)
            self.instanceOff = None


class Stopbar:
    # A set of red lights perpendicular to the taxiway direction (=heading).
    # Width is set by the taxiway width code if available, F (very wide) as default.
    # Holds a referece to its lights
    def __init__(
        self,
        position,
        heading,
        index,
        size: TAXIWAY_WIDTH_CODE = TAXIWAY_WIDTH_CODE.F,
        distance_between_stoplights: int = DISTANCE_BETWEEN_STOPLIGHTS,
        light: LIGHT_TYPE = LIGHT_TYPE.STOP,
    ):
        self.lights = []
        self.position = position
        self.heading = heading
        self.lightStringIndex = index
        self.width = TAXIWAY_WIDTH[size.value].value
        self.distance_between_stoplights = distance_between_stoplights
        self.light = light
        self._on = False
        self._cleared = False
        self.make()

    def make(self):
        numlights = int(self.width / self.distance_between_stoplights)

        if numlights < 4:
            logger.warning(f"stopbar has not enough lights {numlights}")
            numlights = 4

        # centerline
        self.lights.append(Light(self.light, self.position, 0, 0))

        # one side of centerline
        brng = self.heading + 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(self.light, pos, 0, i))

        # the other side of centerline
        brng = self.heading - 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(self.light, pos, 0, numlights + i))

    def place(self, lightTypes):
        for light in self.lights:
            light.place(lightTypes[light.lightType], lightTypes[LIGHT_TYPE.OFF])

    def on(self):
        for light in self.lights:
            light.on()
        self._on = True

    def off(self):
        for light in self.lights:
            light.off()
        self._on = False

    def destroy(self):
        for light in self.lights:
            light.destroy()

    @staticmethod
    def create_taxiway_light(name: str, color: str, intensity: int, position: tuple = (0.0, 0.0, 0.0)) -> str:
        """Creates a light object file with content derived from parameters.

        Args:
            name (str): file name of light object
            color (tuple): RGB colors, each value between 0 and 1.
            intensity (int): number of times the lihgt unit is releated. The more the brighter and the less natural...

        returns:
            str: file name of ligght object
        """
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        fn = os.path.join(curr_dir, "lights", name)
        with open(fn, "w") as fp:
            print(
                f"""I
800
OBJ

POINT_COUNTS    0 0 0 0

""",
                file=fp,
            )
            if color not in "bgry" or len(color) != 1:
                color = "g"
            ls1 = f"LIGHT_NAMED taxi_{color} +0.05 0.01 0.07"
            ls2 = f"LIGHT_NAMED taxi_{color} -0.05 0.01 0.07"
            logger.debug(f"create LIGHT_NAMED {name} ({color}, {intensity})")
            for i in range(intensity):
                print(ls1, file=fp)
                print(ls2, file=fp)
        return name


class Light:
    # A light to follow, or a stopbar light
    # Holds a referece to its instance
    def __init__(self, lightType, position, heading, index):
        self.lightType = lightType
        self.index = index
        self.position = position
        self.heading = heading  # this should be the heading to the previous light
        self.params = []  # LIGHT_PARAM_DEF       full_custom_halo        9   R   G   B   A   S       X   Y   Z   F
        self.drefs = []
        self.lightObject = None
        self.xyz = None
        self.instance = None
        self.instanceOff = None

    def groundXYZ(self, latstr, lonstr, altstr):
        lat, lon, alt = (float(latstr), float(lonstr), float(altstr))
        (x, y, z) = xp.worldToLocal(lat, lon, alt)  # this return proper altitude
        probe = xp.createProbe(xp.ProbeY)
        info = xp.probeTerrainXYZ(probe, x, y, z)
        if info.result == xp.ProbeError:
            logger.debug("Terrain error")
            (x, y, z) = xp.worldToLocal(lat, lon, alt)
        elif info.result == xp.ProbeMissed:
            logger.debug("Terrain Missed")
            (x, y, z) = xp.worldToLocal(lat, lon, alt)
        elif info.result == xp.ProbeHitTerrain:
            # logger.debug("Terrain info is [{}] {}".format(info.result, info))
            (x, y, z) = (info.locationX, info.locationY, info.locationZ)
            # (lat, lng, alt) = xp.localToWorld(info.locationX, info.locationY, info.locationZ)
            # logger.debug('lat, lng, alt is {} feet'.format((lat, lng, alt * 3.28)))
        xp.destroyProbe(probe)
        # (x, y, z) = xp.worldToLocal(float(light.position.lat), float(light.position.lon), alt)
        return (x, y, z)

    def place(self, lightType, lightTypeOff=None):
        self.lightObject = lightType.obj
        pitch, roll, alt = (0, 0, 0)
        (x, y, z) = self.groundXYZ(self.position.lat, self.position.lon, alt)
        self.xyz = (x, y, z, pitch, self.heading, roll)
        if lightTypeOff and not self.instanceOff:
            self.instanceOff = xp.createInstance(lightTypeOff.obj, self.drefs)
            xp.instanceSetPosition(self.instanceOff, self.xyz, self.params)
            # logger.debug("LightString::place: light off placed")

    def on(self):
        if not self.xyz:
            logger.debug("light not placed")
            return
        if self.lightObject and not self.instance:
            self.instance = xp.createInstance(self.lightObject, self.drefs)
            xp.instanceSetPosition(self.instance, self.xyz, self.params)

    def off(self):
        if self.instance:
            xp.destroyInstance(self.instance)
            self.instance = None

    def destroy(self):
        self.off()
        if self.instanceOff:
            xp.destroyInstance(self.instanceOff)
            self.instanceOff = None


class Stopbar:
    # A set of red lights perpendicular to the taxiway direction (=heading).
    # Width is set by the taxiway width code if available, F (very wide) as default.
    # Holds a referece to its lights
    def __init__(
        self,
        position,
        heading,
        index,
        size: TAXIWAY_WIDTH_CODE = TAXIWAY_WIDTH_CODE.F,
        distance_between_stoplights: int = DISTANCE_BETWEEN_STOPLIGHTS,
        light: LIGHT_TYPE = LIGHT_TYPE.STOP,
    ):
        self.lights = []
        self.position = position
        self.heading = heading
        self.lightStringIndex = index
        self.width = TAXIWAY_WIDTH[size.value].value
        self.distance_between_stoplights = distance_between_stoplights
        self.light = light
        self._on = False
        self._cleared = False
        self.make()

    def make(self):
        numlights = int(self.width / self.distance_between_stoplights)

        if numlights < 4:
            logger.warning(f"stopbar has not enough lights {numlights}")
            numlights = 4

        # centerline
        self.lights.append(Light(self.light, self.position, 0, 0))

        # one side of centerline
        brng = self.heading + 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(self.light, pos, 0, i))

        # the other side of centerline
        brng = self.heading - 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(self.light, pos, 0, numlights + i))

    def place(self, lightTypes):
        for light in self.lights:
            light.place(lightTypes[light.lightType], lightTypes[LIGHT_TYPE.OFF])

    def on(self):
        for light in self.lights:
            light.on()
        self._on = True

    def off(self):
        for light in self.lights:
            light.off()
        self._on = False

    def destroy(self):
        for light in self.lights:
            light.destroy()

class LightString:

    def __init__(self, airport, aircraft, preferences: dict = {}):
        self.airport = airport  # get some lighting preference from there
        self.aircraft = aircraft  # get some rabbit preference from there
        self.prefs = preferences  # get FtG preference from there

        self.lights = []  # all green lights from start to destination indexed from 0 to len(lights)
        self.stopbars = []  # Keys of this dict are green light indices.
        self.segments = 0
        self.currentSegment = 0
        self.rabbitIdx = 0
        self.rabbitCanRun = False

        self.route = None  # route as returned by graph.find(), i.e. a list of vertex indices.

        # g_ and r_ are for graphic objects (lights, green and red)
        self.drefs = []
        self.params = []
        self.txy_light_obj = None
        self.stp_light_obj = None
        self.xyzPlaced = False
        self.oldStart = -1
        self.lastLit = 0
        self.lightTypes = None
        self.taxiway_alt = 0

        # Preferences are first set from Airport preferences, which are global or airport specific
        self.distance_between_lights = airport.distance_between_green_lights  # float(get_global("DISTANCE_BETWEEN_GREEN_LIGHTS", preferences=self.prefs))
        if self.distance_between_lights == 0:
            self.distance_between_lights = 10
        self.distance_between_taxiway_lights = airport.distance_between_taxiway_lights
        if self.distance_between_lights == 0:
            self.distance_between_lights = 100
        self.lead_off_lights = int(float(get_global("LEAD_OFF_RUNWAY_DISTANCE", preferences=self.prefs)) / self.distance_between_lights)
        self.rwy_twy_lights = self.lead_off_lights  # initial value

        # Options
        self.add_light_at_vertex = get_global("ADD_LIGHT_AT_VERTEX", preferences=self.prefs)
        self.add_light_at_last_vertex = get_global("ADD_LIGHT_AT_LAST_VERTEX", preferences=self.prefs)
        self.distance_between_stoplights = get_global("DISTANCE_BETWEEN_STOPLIGHTS", preferences=self.prefs)
        self.min_segments_before_hold = get_global("MIN_SEGMENTS_BEFORE_HOLD", preferences=self.prefs)

        self.rabbit_mode = RABBIT_MODE.MED  # default mode on start

        # @todo: Check that preference has beed set at global / airport level.
        #        If set a global / airport level, aircraft preference may only "REFINE" preferences but not CONTREDICT them.
        #        Example: At airport level: rabbit_speed = 0 (= no rabbit). Aircraft may not decide to use a particular rabbit speed.
        #        But if airport level rabbit_speed = 0.2, aircraft may refine rabbit_speed = 0.3 for it own use.
        # following two will get adjusted for aircraft
        # if can_be_refined("RABBIT_SPEED", "LIGHTS_AHEAD"...): ...
        self.lights_ahead = get_global("LIGHTS_AHEAD", self.prefs)
        if "LIGHTS_AHEAD" not in self.prefs:  # if not explicitely defined for entire application
            self.lights_ahead = int(aircraft.lights_ahead / self.distance_between_lights)  # this never changes
            logger.debug(f"lights_ahead defined from aircraft preferences {self.lights_ahead}")
        self.num_lights_ahead = self.lights_ahead  # this adjusts with acf speed

        self.rabbit_length = get_global("RABBIT_LENGTH", self.prefs)
        if "RABBIT_LENGTH" not in self.prefs:  # if not explicitely defined for entire application
            self.rabbit_length = int(aircraft.rabbit_length / self.distance_between_lights)  # this never changes
            logger.debug(f"rabbit_length defined from aircraft preferences {self.rabbit_length}")
        self.num_rabbit_lights = self.rabbit_length  # can be 0, this adjusts with acf speed

        self.rabbit_speed = get_global("RABBIT_SPEED", self.prefs)  # this never changes
        logger.debug(f"rabbit_speed global preferences {self.rabbit_speed}")
        if "RABBIT_SPEED" not in self.prefs and self.rabbit_speed != 0.0 and aircraft.rabbit_speed != 0:  # if not explicitely defined for entire application
            self.rabbit_speed = airport.rabbit_speed  # this never changes
            logger.debug(f"rabbit_speed defined from aircraft preferences {self.rabbit_speed}")
        self.rabbit_duration = self.rabbit_speed  # this adjusts with acf speed

        # control logged info
        self._info_sent = False

        logger.debug(f"physical units: rabbit {aircraft.rabbit_length}m, {abs(round(self.rabbit_duration, 2))} secs., ahead {aircraft.lights_ahead}m")
        logger.info(
            f"rabbit: length={self.num_rabbit_lights}, speed={abs(self.rabbit_duration)}, ahead={abs(self.num_lights_ahead)}, greens={self.distance_between_lights}m"
        )

    def __str__(self):
        return json.dumps({"type": "FeatureCollection", "features": self.features()})

    def has_rabbit(self) -> bool:
        return (abs(self.rabbit_duration) > 0 and self.num_rabbit_lights > 0) or self.lights_ahead > 0

    def features(self):
        fc = []
        # Lights
        for light in self.lights:
            light.position.setProp("marker-color", "#00ff00")
            fc.append(light.position.feature())
        # logger.debug(f"added {len(self.lights)} lights")
        # Stop lights
        for sb in self.stopbars:
            for light in sb.lights:
                light.position.setProp("marker-color", "#ff0000")
                fc.append(light.position.feature())
        # logger.debug(f"added {len(self.stopbars)} stopbars")
        logger.debug(f"{len(fc)} features")
        return fc

    def closestEnd(self, light, edge):
        # When edges are not oriented, we take the extremity
        # that is closest to last light.
        dsrc = distance(light.position, edge.start)
        ddst = distance(light.position, edge.end)
        if dsrc < ddst:
            return edge.start
        return edge.end

    def resetRabbit(self):
        # set all lights
        maxl = min(len(self.lights), self.lastLit + self.num_rabbit_lights + self.num_lights_ahead)
        for i in range(self.lastLit, maxl):
            self.lights[i].on()
        logger.debug(f"rabbit reset: {self.lastLit} -> {maxl}")

    def newRabbitParameters(self, mode: RABBIT_MODE) -> tuple:
        # For now, parameters are static, they will become dynamic later
        # When taxiing fast, make sure enough lights are in front i.e. rabbit length is function of speed?
        adjustment = FTG_SPEED_PARAMS[mode]
        #          self.num_rabbit_lights,              self.rabbit_duration,            , self.num_lights_ahead
        return int(self.rabbit_length * adjustment[0]), self.rabbit_speed * adjustment[1], int(self.lights_ahead * adjustment[0])

    def changeRabbit(self, length: int, duration: float, ahead: int):
        if not self.has_rabbit():
            return
        self.num_rabbit_lights = length
        self.rabbit_duration = duration
        self.num_lights_ahead = ahead
        logger.info(f"rabbit mode: length={self.num_rabbit_lights}, speed={abs(self.rabbit_duration)}, ahead={abs(self.num_lights_ahead)}")

    def rabbitMode(self, mode: RABBIT_MODE):
        if not self.has_rabbit():
            return
        self.rabbit_mode = mode
        length, speed, ahead = self.newRabbitParameters(mode)
        self.resetRabbit()
        self.changeRabbit(length=length, duration=speed, ahead=ahead)
        logger.info(f"rabbit mode: {mode}: {length}, {round(speed, 2)} (ahead={self.num_lights_ahead})")

    def populate(self, route, move: MOVEMENT, onRunway: bool = False):
        # @todo: If already populated, must delete lights first
        logger.debug(f"populate: on runway = {onRunway}")
        self.route = route
        graph = route.graph
        thisLights = []
        onILSvtx = False
        onILSidx = None
        onRwy = onRunway

        if len(self.lights) > 0:
            self.destroy()

        currVertex = graph.get_vertex(route.route[0])
        currPoint = currVertex
        thisLights.append(Light(LIGHT_TYPE.FIRST, currPoint, 0, 0))
        logger.debug(f"added first light at {currVertex.id}")

        if SPECIAL_DEBUG:
            thisLights.append(Light(LIGHT_TYPE.WARNING, currPoint, 0, 0))

        lastLight = currPoint
        # logger.debug("placed first light")
        distanceBeforeNextLight = self.distance_between_lights

        logger.debug(f"at vertex 0, {currVertex.id}, {len(thisLights)}")
        # BEGIN OF ROUTE
        for i in range(1, len(route.route)):
            nextVertex = graph.get_vertex(route.route[i])
            logger.debug(f"at vertex {i}, {nextVertex.id}, {len(thisLights)}")

            thisEdge = graph.get_edge(currVertex.id, nextVertex.id)
            distToNextVertex = thisEdge.cost
            brng = bearing(currVertex, nextVertex)  # make sure we have it the right orientation

            # logger.debug(f"thisEdge: {currVertex.id}-{thisEdge.end.id}, {thisEdge.usage}, {thisEdge.mkActives()}, rwy={onRwy}, ils={False if not onILSvtx else True}")
            if not onILSvtx and thisEdge.has_active(TAXIWAY_ACTIVE.ILS):  # remember entry into ILS zone
                logger.debug(f"thisEdge start active ils section: {thisEdge.start.id}-{thisEdge.end.id}, route vertex={i}, usage={thisEdge.usage}")
                onILSvtx = currVertex
                onILSidx = len(thisLights)
            elif onILSvtx and not thisEdge.has_active(TAXIWAY_ACTIVE.ILS) and not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):  # no longer an ILS zone
                logger.debug(f"thisEdge ends active ils section, and not followed by active departure: route vertex={i}, {thisEdge.usage}")
                onILSvtx = False

            # logger.debug("dist to next: bearing: %f, distance: %f, type: %s", brng, distToNextVertex, thisEdge.usage)  # noqa: E501

            if move == MOVEMENT.DEPARTURE and thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                # must place a stopbar
                stopbarAt = currVertex
                lightAtStopbar = len(thisLights)
                if onILSvtx:
                    stopbarAt = onILSvtx
                    lightAtStopbar = onILSidx  # we also remember the light# where we should place the stopbar.
                    onILSvtx = False
                    logger.debug(f"potential stop bar on departure before previous ils at vertex={stopbarAt.id}, {lightAtStopbar}")
                else:
                    logger.debug(f"potential stop bar on departure at vertex={stopbarAt.id}, {lightAtStopbar} (no ils before)")

                # We remember the light index in the stopbar name. That way we can light the green up to the stopbar and light the stopbar
                # Yup, orientation may be funny, may be not square to [currVertex,nextVertex].  @todo
                if not onRwy:  # If we are on a runway, we assume that no stopbar is necessary to leave the runway
                    logger.debug(f"departure: not on runway at route vertex={i}, {thisEdge.usage}, adding stop bar at vertex {stopbarAt.id}")
                    self.mkStopbar(
                        lightIndex=lightAtStopbar,
                        src=stopbarAt,
                        dst=nextVertex,
                        extremity="start",
                        size=thisEdge.width_code,
                    )
                    self.segments += 1
                    onRwy = True  # We assume that we a setting a stopbar before a runway crossing. (26/1/2026: Ouch is that correct?)
                else:
                    logger.debug(f"departure: on runway #={i}, usage={thisEdge.usage}, active={thisEdge.mkActives()}")
                    if thisEdge.usage != "runway" and not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                        # if consecutive active departure segments, do not stop for them
                        logger.debug(f"departure: no longer on runway at edge {i}.")
                        onRwy = False

            # note: if move=arrival, we should not stop on the first taxiway segment, but we may have to cross another runway further on...
            # the criteria here should be refined. test for active=arrival, and runway=runway where we landed. @todo.
            # @todo: check also for hasActive(ARRIVAL)? Or either or both?
            if move == MOVEMENT.ARRIVAL and thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE) and i > self.min_segments_before_hold:  # must place a stop bar
                stopbarAt = currVertex  # but should avoid placing one as plane exits runway...
                lightAtStopbar = len(thisLights)
                if onILSvtx:
                    stopbarAt = onILSvtx
                    lightAtStopbar = len(thisLights)
                    logger.debug(f"potential stop bar on arrival before ils {i}, {lightAtStopbar}")
                    onILSvtx = False
                else:
                    logger.debug(f"potential stop bar on arrival {i}, {lightAtStopbar}")

                # We remember the light index in the stopbar name. That way we can light the green up to the stopbar and light the stopbar
                if not onRwy:  # If we are on a runway, we assume that no stopbar is necessary to leave the runway
                    logger.debug(f"arrival: on runway {i}, {thisEdge.usage}, adding stop bar at vertex {stopbarAt.id}")
                    self.mkStopbar(
                        lightIndex=lightAtStopbar,
                        src=stopbarAt,
                        dst=nextVertex,
                        extremity="start",
                        size=thisEdge.width_code,
                    )
                    self.segments += 1
                    onRwy = True  # We assume that we a setting a stopbar before a runway crossing.
                else:
                    logger.debug(f"arrival: not on runway {i}, {thisEdge.usage}")
                    if thisEdge.usage != "runway" and not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                        # if consecutive active departure segments, do not stop for them
                        logger.debug(f"arrival: no longer on runway at edge {i}.")
                        onRwy = False

            if onRwy and thisEdge.usage != "runway" and not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                # if consecutive active departure segments, do not stop for them
                logger.debug(f"no longer on runway at edge {i}.")
                onRwy = False

            if distToNextVertex < distanceBeforeNextLight:
                # we don't insert a light, we go to next leg  # noqa: E501
                distanceBeforeNextLight = distanceBeforeNextLight - distToNextVertex
            else:  # we insert a light until we reach the next point
                while distanceBeforeNextLight < distToNextVertex:
                    nextLightPos = destination(currPoint, brng, distanceBeforeNextLight)
                    brgn = bearing(lastLight, nextLightPos)
                    thisLights.append(Light(self.nextTaxiwayLight(nextLightPos, thisEdge), nextLightPos, brgn, i))
                    lastLight = nextLightPos
                    distToNextVertex = distToNextVertex - distanceBeforeNextLight  # should be close to ftg_geoutil.distance(currPoint, nextVertex)
                    currPoint = nextLightPos
                    distanceBeforeNextLight = self.distance_between_lights
                    # logger.debug("added light %f, %f", distanceBeforeNextLight, distToNextVertex)

                distanceBeforeNextLight = distanceBeforeNextLight - distToNextVertex
                # logger.debug("remaining: %f", distanceBeforeNextLight)

                if self.add_light_at_vertex:  # may be we insert a last light at the vertex?
                    brgn = bearing(lastLight, nextVertex)
                    thisLights.append(Light(self.nextTaxiwayLight(nextVertex, thisEdge), nextVertex, brgn, i))
                    lastLight = nextVertex
                    # logger.debug("added light at vertex %s", nextVertex.id)

            currPoint = nextVertex
            currVertex = nextVertex
        # END OF ROUTE

        if self.add_light_at_last_vertex:  # may be we insert a last light at the last vertex?
            lastPoint = route.route[len(route.route) - 1]
            lastVertex = graph.get_vertex(route.route[len(route.route) - 1])
            brgn = bearing(lastLight, lastPoint)
            thisLights.append(Light(LIGHT_TYPE.LAST, lastVertex, brgn, i))
            lastLight = lastPoint
            logger.debug(f"added light at last vertex {route.route[len(route.route) - 1].id}")

        if SPECIAL_DEBUG:
            lastVertex = graph.get_vertex(route.route[len(route.route) - 1])
            thisLights.append(Light(LIGHT_TYPE.WARNING, lastVertex, brgn, i))

        last = 0
        for i in range(len(self.stopbars)):
            sb = self.stopbars[i]
            logger.debug(f"stopbar {i}: {last}-{sb.lightStringIndex}.")
            last = sb.lightStringIndex

        self.lights = thisLights

        return thisLights

    def printSegments(self):
        # for debugging purpose
        logger.info(f"added {len(self.lights)} lights, {self.segments + 1} segments, {len(self.stopbars)} stop bars.")
        if len(self.stopbars) > 0:
            segs = []
            last = 0
            for i in range(len(self.stopbars)):
                segs.append(f"#{i}:{last}-{self.stopbars[i].lightStringIndex - 1}")
                last = self.stopbars[i].lightStringIndex
            segs.append(f"#{i}:{last}-{len(self.lights) - 1}")
            logger.debug("segments: " + ", ".join(segs))

        logger.debug(f"distance between taxiway center lights: {self.distance_between_lights} m")
        logger.debug(f"lights ahead: {self.num_lights_ahead},  {self.aircraft.lights_ahead} m")
        logger.debug(f"rabbit: length: {self.num_rabbit_lights} lights, {self.aircraft.rabbit_length} m")
        logger.debug(f"runway lead-off lights: {self.lead_off_lights} lights, {float(get_global('LEAD_OFF_RUNWAY_DISTANCE', preferences=self.prefs))} m")
        if logger.level < 10:
            fn = os.path.join(os.path.dirname(__file__), "..", "ftg_ls.geojson")
            with open(fn, "w") as fp:
                print(self, file=fp)
            logger.debug(f"LightString saved in {fn}")

    # We make a stopbar after the green light index lightIndex
    def mkStopbar(self, lightIndex, src, dst, extremity="end", size: TAXIWAY_WIDTH_CODE = TAXIWAY_WIDTH_CODE.E, light: LIGHT_TYPE = LIGHT_TYPE.STOP):
        if size is None:
            size = TAXIWAY_WIDTH_CODE.E
        brng = bearing(src, dst)
        start = None
        if extremity == "end":
            start = dst
        else:
            start = src
        stopbar = Stopbar(position=start, heading=brng, index=lightIndex, size=size, light=light)
        self.stopbars.append(stopbar)
        logger.debug(f"added stopbar at light index {lightIndex}")

        return stopbar.lights

    def initial(self, coord, heading):
        start = Point(coord[0], coord[1])
        brng = bearing(start, self.lights[0].position)
        dist = distance(start, self.lights[0].position)
        return [
            10 * round(brng / 10),
            10 * round(dist / 10),
            abs(brng - convertAngleTo360(heading)),
        ]

    def loadObjects(self):
        lightsConfig = self.prefs.get("Lights", {})
        DEFAULT_LIGHT_VALUES = {
            "name": f"ftglight{randint(1000,9999)}.obj",
            "color": [1, 1, 1],  # white
            "size": 20,
            "intensity": 20,
            "texture": LightType.DEFAULT_TEXTURE_CODE,
        }
        PINK = self.prefs.get("VALENTINE", False)
        pinkfn = ""
        if PINK:
            pinkfn = LightType.create(name="egg.obj", color=(0.9, 0.1, 0.9), size=18, intensity=10, texture=LightType.DEFAULT_TEXTURE_CODE)
        self.lightTypes = {}
        for k, f in LIGHT_TYPE_OBJFILES.items():
            if PINK and k != LIGHT_TYPE.STOP:
                self.lightTypes[k] = LightType(k, pinkfn)
            elif type(f) is str:
                self.lightTypes[k] = LightType(k, f)
            elif type(f) in [tuple, list]:
                fn = LightType.create(name=f[0], color=f[1], size=f[2], intensity=f[3], texture=f[4])
                self.lightTypes[k] = LightType(k, fn)
            if k in lightsConfig:
                cfg = lightsConfig.get(k)
                if type(cfg) is dict:
                    thisLightConfig = DEFAULT_LIGHT_VALUES | cfg
                    if not thisLightConfig["name"].endswith(".obj"):
                        thisLightConfig["name"] = thisLightConfig["name"] + ".obj"
                    fn = LightType.create(**thisLightConfig)
                    self.lightTypes[k] = LightType(k, fn)
                    logger.debug(f"created preferred light {thisLightConfig}")
                elif type(cfg) is str:  # simple alternate name for obj file
                    self.lightTypes[k] = LightType(k, cfg)
                    logger.debug(f"created preferred light named {cfg}")
                else:
                    logger.warning(f"invalid config {lightsConfig.get(k)} for light{k}, ignored")
                    continue
            self.lightTypes[k].load()
        logger.debug("loaded.")
        return True

    def placeLights(self):
        for light in self.lights:
            light.place(self.lightTypes[light.lightType], self.lightTypes[LIGHT_TYPE.OFF])

        for sb in self.stopbars:
            sb.place(self.lightTypes)

        self.xyzPlaced = True
        logger.debug("placed.")
        return True

    def blackenSegment(self, segment):
        if segment >= len(self.stopbars):
            return
        self.stopbars[segment].off()
        logger.debug("done.")

    def illuminateSegment(self, segment):
        # Lights up a segment of lights between 2 stop bars
        if not self.lightTypes:
            if not self.loadObjects():
                return [False, "Could not load light objects."]

        if not self.xyzPlaced:  # do it once and for all. Lights rarely move.
            if not self.placeLights():
                return [False, "Could not place light objects."]

        self.currentSegment = segment
        start = 0
        end = 0
        if segment >= len(self.stopbars):  # there might be more green lights after the last stopbars
            segment = len(self.stopbars)  # can't be larger
            if segment > 0:
                self.blackenSegment(segment - 1)
                lastSb = self.stopbars[segment - 1]
                start = lastSb.lightStringIndex
            end = len(self.lights)
            logger.debug(f"will instanciate(green): last segment {segment} between {start} and {end}.")
        else:
            sbend = self.stopbars[segment]
            if segment > 0:
                self.blackenSegment(segment - 1)
                sbbeging = self.stopbars[segment - 1]
                start = sbbeging.lightStringIndex
            end = sbend.lightStringIndex
            logger.debug(f"will instanciate(green): {segment} between {start} and {end}.")

        if self.num_lights_ahead is None or self.num_lights_ahead == 0:
            # Instanciate for each green light in segment and stop bar
            for i in range(start, end):
                self.lights[i].on()
            # map(lambda x: x.on(self.txy_light_obj), self.lights[start:end])
            logger.debug("no light ahead: instanciate(green): done.")
        # else, lights will be turned on in front of rabbit

        # Instanciate for each stop light
        # for sb in self.stopbars:
        if len(self.stopbars) > 0 and segment < len(self.stopbars):
            sbend = self.stopbars[segment]
            for light in sbend.lights:
                light.on()
            logger.debug(f"illuminated {len(sbend.lights)} stop lights")
            # map(lambda x: x.on(self.stp_light_obj), sbend.lights)
        logger.debug("no light ahead: instanciate(stop): done.")

        if not self.rabbitCanRun:
            self.rabbitCanRun = True

        return [True, "green is set"]

    def nextTaxiwayLight(self, position, edge) -> LIGHT_TYPE:
        # This is to provide alternate green/amber light
        # on runway Lead-Off lights to taxiway.
        # Lights are green/amber on runway, then a few more until on taxiway.
        # Then all green as normal taxiway.
        # This is ONLY if the aircraft is on the runway, and just for the lights
        # to lead it off runway. (This is not for "all" lead-off lights and all runways.)
        #
        # logger.debug(f"nextTaxiwayLightEdge: {edge.start.id}-{edge.end.id}, active={edge.has_active()}, {edge.mkActives()}, {edge.has_active()}, {len(edge.active)}")
        if self.route.runway is not None:  # on runway may need lead-off ligths
            self.taxiway_alt = self.taxiway_alt + 1  # alternate
            if self.rwy_twy_lights == self.lead_off_lights:  # always on runway
                if pointInPolygon(position, self.route.runway.polygon):
                    logger.debug(f"on runway, alternate {LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT}")
                    return LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT
            # no longer on runway, keep alterning for a few lights
            self.rwy_twy_lights = self.rwy_twy_lights - 1
            if self.rwy_twy_lights > 0:
                logger.debug(f"not on runway, leaving, alternate {LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT}")
                return LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT
            if not self._info_sent:
                logger.debug("no longer on runway, using normal lights")
                self._info_sent = True

        if not self._info_sent:
            logger.debug("not on runway, using normal lights")
            self._info_sent = True

        # if edge.direction == TAXIWAY_DIRECTION.ONEWAY:
        #     return LIGHT_TYPE.ONEWAY
        # if edge.is_inner_only:
        #     return LIGHT_TYPE.INNER
        # if edge.is_outer_only:
        #     return LIGHT_TYPE.OUTER
        # if edge.has_active(TAXIWAY_ACTIVE.ARRIVAL):
        #     return LIGHT_TYPE.ACTIVE_ARR
        # if edge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
        #     return LIGHT_TYPE.ACTIVE_DEP
        # if edge.has_active(TAXIWAY_ACTIVE.ILS):
        #     return LIGHT_TYPE.ACTIVE_ILS
        if edge.has_active():
            logger.debug(f"edge is active ({edge.mkActives()})")
            return LIGHT_TYPE.ACTIVE

        return LIGHT_TYPE.TAXIWAY

    def nextStop(self):
        # index of light where should stop next
        if self.currentSegment < len(self.stopbars):
            return self.stopbars[self.currentSegment].lightStringIndex
        return len(self.lights) - 1

    def closest(self, position, after: int = 0):
        # Find closest light to position (often plane)
        dist = math.inf
        idx = None
        point = Point(position[0], position[1])
        for i in range(after, len(self.lights)):
            light = self.lights[i]
            d = distance(point, light.position)
            if d < dist:
                dist = d
                idx = i

        return [idx, dist]

    def toNextStop(self, position):
        # ilight index of next stop position and distance to it
        ns = self.nextStop()
        light = self.lights[ns]
        point = Point(position[0], position[1])
        d = distance(point, light.position)
        return [ns, d]

    def offToIndex(self, idx):
        if idx < len(self.lights):
            for i in range(self.lastLit, idx):
                self.lights[i].off()
            self.lastLit = idx
            logger.debug(f"turned off {idx} -> {self.lastLit}")
        # else: idx out of range?

    def onToIndex(self, idx):
        last = min(idx, len(self.lights))
        for i in range(self.lastLit, last):
            self.lights[i].on()
        # warning, verbose, since called at each rabbit flightloop
        # logger.debug("turned on %d -> %d.", self.lastLit, last)

    def rabbit(self, start: int):
        if not self.rabbitCanRun:
            return 10  # checks 10 seconds later

        def restore(strt, sq, rn):
            if self.num_rabbit_lights == 0:
                return  # nothing to restore if no rabbit
            prev = strt + ((sq - 1) % self.num_rabbit_lights)
            if prev < rn:
                self.lights[prev].on()

        rabbitNose = self.nextStop()

        if start != self.oldStart:  # restore previous but with old start
            # restore(self.oldStart, self.rabbitIdx, rabbitNose)
            self.oldStart = start
            if start > 0:  # can't be.
                self.offToIndex(start - 1)

            if self.num_lights_ahead > 0:
                # we need to turn lights on ahead of rabbit
                wishidx = start + self.num_rabbit_lights + self.num_lights_ahead
                if wishidx < rabbitNose:
                    self.onToIndex(wishidx)
                else:
                    self.onToIndex(rabbitNose)
                    # there might be a stop bar...
                    if len(self.stopbars) > 0 and self.currentSegment < len(self.stopbars):  # there might be more green lights after the last stopbars
                        sb = self.stopbars[self.currentSegment]
                        for redlight in sb.lights:
                            redlight.on()
                        # map(lambda x: x.on(self.stp_light_obj), sbend.lights)
                        logger.debug(f"light ahead: instanciate stopbar {self.currentSegment}: done.")

        else:  # restore previous
            restore(start, self.rabbitIdx, rabbitNose)

        if self.num_rabbit_lights > 0:
            curr = start + (self.rabbitIdx % self.num_rabbit_lights)
            if curr < rabbitNose:
                self.lights[curr].off()

        self.rabbitIdx += 1

        # debugging negative duration is not limited
        return max(self.rabbit_duration, HARDCODED_MIN_TIME) if self.rabbit_duration > 0 else abs(self.rabbit_duration)

    def showAll(self, airport):
        def showSegment(s, cnt):
            brng = s.bearing()

            # light at start of segment
            self.lights.append(Light(LIGHT_TYPE.DEFAULT, s.start, brng, cnt))
            cnt += 1

            step = max(self.distance_between_taxiway_lights, HARDCODED_MIN_DISTANCE)
            dist = step
            while dist < s.length():
                pos = destination(s.start, brng, dist)
                self.lights.append(Light(LIGHT_TYPE.DEFAULT, pos, brng, cnt))
                cnt += 1
                dist += step

            # light at end of segment
            self.lights.append(Light(LIGHT_TYPE.DEFAULT, s.end, brng, cnt))
            cnt += 1
            return cnt

        lightcount = 0
        for e in airport.graph.edges_arr:
            lightcount = showSegment(e, lightcount)

        # Lights up a segment of lights between 2 stop bars
        if not self.lightTypes:
            if not self.loadObjects():
                return [False, "Could not load light objects."]

        if not self.xyzPlaced:  # do it once and for all. Lights rarely move.
            if not self.placeLights():
                return [False, "Could not place light objects."]

        for light in self.lights:
            light.on()

        return lightcount

    def destroy(self):
        # Destroy each green light
        self.rabbitCanRun = False
        if self.lights:
            for light in self.lights:
                light.destroy()
            logger.debug("destroy(green): done.")

        # Destroy each stopbar
        if self.stopbars:
            for sb in self.stopbars:
                sb.destroy()
            logger.debug("destroy(stop): done.")

        # Unload light objects
        if self.lightTypes:
            for k, f in self.lightTypes.items():
                f.unload()
            self.lightTypes = None
            logger.debug("destroy: unloaded.")
