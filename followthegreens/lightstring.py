# Light setup utility Class
# Keep track of all lights set for FTG, their status, etc. Manipulate them as well.
#
import math
import json
import os.path
from enum import StrEnum

import xp

from .geo import Point, distance, bearing, destination, convertAngleTo360, pointInPolygon
from .globals import (
    logger,
    ADD_LIGHT_AT_LAST_VERTEX,
    ADD_LIGHT_AT_VERTEX,
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    DISTANCE_BETWEEN_LIGHTS,
    DISTANCE_BETWEEN_STOPLIGHTS,
    FTG_SPEED_PARAMS,
    LIGHTS_AHEAD,
    MIN_SEGMENTS_BEFORE_HOLD,
    MOVEMENT,
    RABBIT_DURATION,
    RABBIT_LENGTH,
    RABBIT_MODE,
    TAXIWAY_ACTIVE,
    TAXIWAY_WIDTH_CODE,
    TAXIWAY_WIDTH,
    LIGHT_TYPE,
    LIGHT_TYPE_OBJFILES,
    LEAD_OFF_RUNWAY_DISTANCE,
)

HARDCODED_MIN_DISTANCE = 10  # meters
HARDCODED_MIN_TIME = 0.1  # secs


class LightType:
    # A light to follow, or a stopbar light
    # Holds a referece to its instance
    def __init__(self, name, filename):
        self.name = name
        self.filename = filename
        self.obj = None

    def load(self):
        if not self.obj:
            curr_dir = os.path.dirname(os.path.realpath(__file__))
            real_path = os.path.join(curr_dir, "lights", self.filename)
            self.obj = xp.loadObject(real_path)
            logger.debug(f"LoadObject loaded {self.filename}")

    def unload(self):
        if self.obj:
            xp.unloadObject(self.obj)
            self.obj = None
            logger.debug(f"object unloaded {self.name}")

    @staticmethod
    def create(name: str, color: tuple, size: int, intensity: int, texture: int) -> str:
        TEXTURES = [
            "0.5  1.0  1.0  0.5",  # TOP RIGHT
            "0.0  1.0  0.5  0.5",  # TOP LEFT
            "0.5  0.5  1.0  0.0",  # BOT RIGHT
            "0.0  0.5  0.5  0.0",  # BOT LEFT
        ]
        curr_dir = os.path.dirname(os.path.realpath(__file__))
        fn = os.path.join(curr_dir, "lights", name)
        fsize = round(size / 100, 2)
        alpha = 1
        with open(fn, "w") as fp:
            print(
                """I
800
OBJ

TEXTURE lights.png
TEXTURE_LIT lights.png

POINT_COUNTS    0 0 0 0

""",
                file=fp,
            )
            ls = f"LIGHT_CUSTOM 0 1 0 {round(color[0],2)} {round(color[1],2)} {round(color[2],2)} {alpha} {fsize} {TEXTURES[texture]} UNUSED"
            logger.debug(f"create light {name} ({size}, {intensity}): {ls}")
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
    ):
        self.lights = []
        self.position = position
        self.heading = heading
        self.lightStringIndex = index
        self.width = TAXIWAY_WIDTH[size.value].value
        self.distance_between_stoplights = distance_between_stoplights
        self._on = False
        self._cleared = False
        self.make()

    def make(self):
        numlights = int(self.width / self.distance_between_stoplights)

        if numlights < 4:
            logger.warning(f"stopbar has not enough lights {numlights}")
            numlights = 4

        # centerline
        self.lights.append(Light(LIGHT_TYPE.STOP, self.position, 0, 0))

        # one side of centerline
        brng = self.heading + 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(LIGHT_TYPE.STOP, pos, 0, i))

        # the other side of centerline
        brng = self.heading - 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * self.distance_between_stoplights)
            self.lights.append(Light(LIGHT_TYPE.STOP, pos, 0, numlights + i))

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

    def __init__(self, config: dict = {}):
        self.lights = []  # all green lights from start to destination indexed from 0 to len(lights)
        self.stopbars = []  # Keys of this dict are green light indices.
        self.segments = 0
        self.currentSegment = 0
        self.rabbitIdx = 0
        self.rabbitCanRun = False

        self.route = None  # route as returned by graph.Dijkstra, i.e. a list of vertex indices.

        # g_ and r_ are for graphic objects (lights, green and red)
        self.drefs = []
        self.params = []  # LIGHT_PARAM_DEF       full_custom_halo        9   R   G   B   A   S       X   Y   Z   F
        self.txy_light_obj = None
        self.stp_light_obj = None
        self.xyzPlaced = False
        self.oldStart = -1
        self.lastLit = 0
        self.lightTypes = None
        self.taxiway_alt = 0
        self.distance_between_lights = config.get("DISTANCE_BETWEEN_GREEN_LIGHTS", DISTANCE_BETWEEN_GREEN_LIGHTS)
        if self.distance_between_lights == 0:
            self.distance_between_lights = 10
        self.lead_off_lights = LEAD_OFF_RUNWAY_DISTANCE / self.distance_between_lights
        self.rwy_twy_lights = self.lead_off_lights

        self.num_lights_ahead = config.get("LIGHTS_AHEAD", LIGHTS_AHEAD)  # if zero, all lights are shown, otherwise, must be >= self.rabbit_length
        self.rabbit_length = config.get("RABBIT_LENGTH", RABBIT_LENGTH)
        self.rabbit_duration = config.get("RABBIT_DURATION", RABBIT_DURATION)
        self.rabbit_mode = RABBIT_MODE.MED

        logger.debug(f"LightString created {self.rabbit_length}, {self.rabbit_duration}")

    def __str__(self):
        return json.dumps({"type": "FeatureCollection", "features": self.features()})

    def has_rabbit(self) -> bool:
        return self.rabbit_duration > 0 and self.rabbit_length > 0

    def features(self):
        fc = []
        # Lights
        for light in self.lights:
            light.position.markerColor = "#00ff00"
            fc.append(light.position.feature())
        # Stop lights
        for sb in self.stopbars:
            for light in sb.lights:
                light.position.markerColor = "#ff0000"
                fc.append(light.position.feature())
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
        maxl = min(len(self.lights), self.lastLit + self.rabbit_length + self.num_lights_ahead)
        for i in range(self.lastLit, maxl):
            self.lights[i].on()
        logger.debug(f"rabbit reset: {self.lastLit} -> {maxl}")

    def rabbitMode(self, mode: RABBIT_MODE):
        if not self.has_rabbit():
            return
        self.rabbit_mode = mode
        length, speed = FTG_SPEED_PARAMS[mode]
        self.resetRabbit()
        self.changeRabbit(length=length, duration=speed, ahead=self.num_lights_ahead)
        logger.info(f"rabbit mode: {mode}: {length}, {round(speed, 2)} (ahead={self.num_lights_ahead})")

    def changeRabbit(self, length: int, duration: float, ahead: int):
        if not self.has_rabbit():
            return
        self.rabbit_length = length
        self.rabbit_duration = duration
        logger.info(f"rabbit mode: {self.rabbit_length}, {self.rabbit_duration}")

    def populate(self, route, onRunway=False):
        # @todo: If already populated, must delete lights first
        logger.debug(f"populate: on runway = {onRunway}")
        self.route = route
        graph = route.graph
        thisLights = []
        onILS = False
        onILSidx = None
        onRwy = onRunway

        if len(self.lights) > 0:
            self.detroy()

        currVertex = graph.get_vertex(route.route[0])
        currPoint = currVertex
        thisLights.append(Light(LIGHT_TYPE.FIRST, currPoint, 0, 0))
        lastLight = currPoint
        # logger.debug("placed first light")
        distanceBeforeNextLight = self.distance_between_lights

        logger.debug(f"at vertex 0, {currVertex.id}, {len(thisLights)}")
        for i in range(1, len(route.route)):
            nextVertex = graph.get_vertex(route.route[i])
            logger.debug(f"at vertex {i}, {nextVertex.id}, {len(thisLights)}")

            distToNextVertex = distance(currPoint, nextVertex)
            brng = bearing(currVertex, nextVertex)

            thisEdge = graph.get_edge(currVertex.id, nextVertex.id)
            if not onILS and thisEdge.has_active(TAXIWAY_ACTIVE.ILS):  # remember entry into ILS zone
                logger.debug(f"thisEdge active ils {thisEdge.start.id}-{thisEdge.end.id}, {i}, {thisEdge.usage}")
                onILS = thisEdge
                onILSidx = len(thisLights)
            elif not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):  # no longer an ILS zone
                # logger.debug("thisEdge %d, %s.", i, thisEdge.usage)
                onILS = False

            # logger.debug("dist to next: bearing: %f, distance: %f, type: %s", brng, distToNextVertex, thisEdge.usage)  # noqa: E501

            if route.move == MOVEMENT.DEPARTURE and thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                # must place a stopbar
                stopbarAt = currVertex
                lightAtStopbar = len(thisLights)
                if onILS:
                    stopbarAt = graph.get_vertex(onILS.start.id)
                    lightAtStopbar = onILSidx  # we also remember the light# where we should place the stopbar.
                    onILS = False
                    logger.debug(f"potential stop bar on departure before ils at edge {i}, {lightAtStopbar}")
                else:
                    logger.debug(f"potential stop bar on departure at edge {i}, {lightAtStopbar}")

                # We remember the light index in the stopbar name. That way we can light the green up to the stopbar and light the stopbar
                # Yup, orientation may be funny, may be not square to [currVertex,nextVertex].  @todo
                if not onRwy:  # If we are on a runway, we assume that no stopbar is necessary to leave the runway
                    logger.debug(f"departure: not on runway at edge {i}, {thisEdge.usage}")
                    self.mkStopBar(
                        lightAtStopbar,
                        stopbarAt,
                        nextVertex,
                        "start",
                        thisEdge.width_code,
                    )
                    self.segments += 1
                    onRwy = True  # We assume that we a setting a stopbar before a runway crossing.
                else:
                    logger.debug(
                        f"LightString::populate: departure: on runway #={i}, usage={thisEdge.usage}, dept?={thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE)}, {thisEdge.mkActives()}"
                    )
                    if thisEdge.usage != "runway" and not thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE):
                        # if consecutive active departure segments, do not stop for them
                        logger.debug(f"departure: no longer on runway at edge {i}.")
                        onRwy = False

            # note: if move=arrival, we should not stop on the first taxiway segment, but we may have to cross another runway further on...
            # the criteria here should be refined. test for active=arrival, and runway=runway where we landed. @todo.
            # @todo: check also for hasActive(ARRIVAL)? Or either or both?
            if route.move == MOVEMENT.ARRIVAL and thisEdge.has_active(TAXIWAY_ACTIVE.DEPARTURE) and i > MIN_SEGMENTS_BEFORE_HOLD:  # must place a stop bar
                stopbarAt = currVertex  # but should avoid placing one as plane exits runway...
                lightAtStopbar = len(thisLights)
                if onILS:
                    stopbarAt = graph.get_vertex(onILS.start.id)
                    lightAtStopbar = len(thisLights)
                    logger.debug(f"potential stop bar on arrival before ils {i}, {lightAtStopbar}")
                    onILS = False
                else:
                    logger.debug(f"potential stop bar on arrival {i}, {lightAtStopbar}")

                # We remember the light index in the stopbar name. That way we can light the green up to the stopbar and light the stopbar
                if not onRwy:  # If we are on a runway, we assume that no stopbar is necessary to leave the runway
                    logger.debug(f"arrival: on runway {i}, {thisEdge.usage}")
                    self.mkStopBar(
                        lightAtStopbar,
                        stopbarAt,
                        nextVertex,
                        "start",
                        thisEdge.width_code,
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
                    thisLights.append(Light(self.next_taxiway_light(nextLightPos), nextLightPos, brgn, i))
                    lastLight = nextLightPos
                    distToNextVertex = distToNextVertex - distanceBeforeNextLight  # should be close to ftg_geoutil.distance(currPoint, nextVertex)
                    currPoint = nextLightPos
                    distanceBeforeNextLight = self.distance_between_lights
                    # logger.debug("added light %f, %f", distanceBeforeNextLight, distToNextVertex)

                distanceBeforeNextLight = distanceBeforeNextLight - distToNextVertex
                # logger.debug("remaining: %f", distanceBeforeNextLight)

                if ADD_LIGHT_AT_VERTEX:  # may be we insert a last light at the vertex?
                    brgn = bearing(lastLight, nextVertex)
                    thisLights.append(Light(self.next_taxiway_light(nextVertex), nextVertex, brgn, i))
                    lastLight = nextVertex
                    # logger.debug("added light at vertex %s", nextVertex.id)

            currPoint = nextVertex
            currVertex = nextVertex

        if ADD_LIGHT_AT_LAST_VERTEX:  # may be we insert a last light at the last vertex?
            lastPoint = route.route[len(route.route) - 1]
            brgn = bearing(lastLight, lastPoint)
            thisLights.append(Light(LIGHT_TYPE.TAXIWAY, lastPoint, brgn, i))
            lastLight = lastPoint
            logger.debug(f"added light at last vertex {route.route[len(route.route) - 1].id}")

        last = 0
        for i in range(len(self.stopbars)):
            sb = self.stopbars[i]
            logger.debug(f"stopbar {i}: {last}-{sb.lightStringIndex}.")
            last = sb.lightStringIndex

        self.lights = thisLights

        return thisLights

    # We make a stopbar after the green light index lightIndex
    def mkStopBar(
        self,
        lightIndex,
        src,
        dst,
        extremity="end",
        size: TAXIWAY_WIDTH_CODE = TAXIWAY_WIDTH_CODE.E,
    ):
        if size is None:
            size = TAXIWAY_WIDTH_CODE.E
        brng = bearing(src, dst)
        start = None
        if extremity == "end":
            start = dst
        else:
            start = src
        stopbar = Stopbar(start, brng, lightIndex, size)

        self.stopbars.append(stopbar)
        logger.debug(f"added stopbar at {lightIndex}")

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
        self.lightTypes = {}
        for k, f in LIGHT_TYPE_OBJFILES.items():
            if type(f) is str:
                self.lightTypes[k] = LightType(k, f)
            elif type(f) in [tuple, list]:
                fn = LightType.create(name=f[0], color=f[1], size=f[2], intensity=f[3], texture=f[4])
                self.lightTypes[k] = LightType(k, fn)
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
            # Instanciate for each stop light
            # for sb in self.stopbars:
            if len(self.stopbars) > 0 and segment < len(self.stopbars):
                sbend = self.stopbars[segment]
                for light in sbend.lights:
                    light.on()
                    logger.debug("illuminating stop light.")
                # map(lambda x: x.on(self.stp_light_obj), sbend.lights)
            logger.debug("no light ahead: instanciate(stop): done.")
        # else, lights will be turned on in front of rabbit

        if not self.rabbitCanRun:
            self.rabbitCanRun = True

        return [True, "green is set"]

    def next_taxiway_light(self, position) -> LIGHT_TYPE:
        # This is to provide alternate green/amber light
        # on runway Lead-Off lights to taxiway.
        # Lights are green/amber on runway, then a few more until on taxiway.
        # Then all green as normal taxiway.
        #
        if self.route.runway is None:  # no runway, all green
            logger.debug("next_taxiway_light: no runway, all greens")
            return LIGHT_TYPE.TAXIWAY
        self.taxiway_alt = self.taxiway_alt + 1
        if self.rwy_twy_lights == self.lead_off_lights:  # always on runway
            if pointInPolygon(position, self.route.runway.polygon):
                logger.debug(f"next_taxiway_light: on runway, alternate {LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT}")
                return LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT
        self.rwy_twy_lights = self.rwy_twy_lights - 1
        if self.rwy_twy_lights > 0:
            logger.debug(f"next_taxiway_light: not on runway, leaving, alternate {LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT}")
            return LIGHT_TYPE.TAXIWAY if self.taxiway_alt % 2 == 0 else LIGHT_TYPE.TAXIWAY_ALT
        logger.debug(f"next_taxiway_light: no longer on runway all greens")
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
            prev = strt + ((sq - 1) % self.rabbit_length)
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
                wishidx = start + self.rabbit_length + self.num_lights_ahead
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

        curr = start + (self.rabbitIdx % self.rabbit_length)
        if curr < rabbitNose:
            self.lights[curr].off()

        self.rabbitIdx += 1

        return max(self.rabbit_duration, HARDCODED_MIN_TIME)

    def showAll(self, airport):
        def showSegment(s, cnt):
            brng = s.bearing()

            # light at start of segment
            self.lights.append(Light(LIGHT_TYPE.TAXIWAY, s.start, brng, cnt))
            cnt += 1

            step = max(DISTANCE_BETWEEN_LIGHTS, HARDCODED_MIN_DISTANCE)
            dist = step
            while dist < s.length():
                pos = destination(s.start, brng, dist)
                self.lights.append(Light(LIGHT_TYPE.TAXIWAY, pos, brng, cnt))
                cnt += 1
                dist += step

            # light at end of segment
            self.lights.append(Light(LIGHT_TYPE.TAXIWAY, s.end, brng, cnt))
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
