# Light setup utility Class
# Keep track of all lights set for FTG, their status, etc. Manipulate them as well.
#
import math
import logging
import json
import os.path

import xp

from .geo import Point, distance, bearing, destination, convertAngleTo360
from .globals import (
    DISTANCE_BETWEEN_GREEN_LIGHTS,
    ADD_LIGHT_AT_VERTEX,
    ADD_LIGHT_AT_LAST_VERTEX,
    DISTANCE_BETWEEN_STOPLIGHTS,
    MIN_SEGMENTS_BEFORE_HOLD,
    DISTANCE_BETWEEN_LIGHTS,
)
from .globals import RABBIT_LENGTH, RABBIT_DURATION, LIGHTS_AHEAD
from .globals import AIRCRAFT_TYPES as TAXIWAY_WIDTH
from .globals import DEPARTURE, ARRIVAL

logger = logging.getLogger(__name__)

LIGHT_TYPE_OFF = "LIGHT_TYPE_OFF"
LIGHT_TYPE_DEFAULT = "LIGHT_TYPE_DEFAULT"
LIGHT_TYPE_FIRST = "LIGHT_TYPE_FIRST"
LIGHT_TYPE_TAXIWAY = "LIGHT_TYPE_TAXIWAY"
LIGHT_TYPE_TAXIWAY_ALT = "LIGHT_TYPE_TAXIWAY_ALT"
LIGHT_TYPE_STOP = "LIGHT_TYPE_STOP"
LIGHT_TYPE_LAST = "LIGHT_TYPE_LAST"

LIGHT_TYPES_OBJFILES = {
    LIGHT_TYPE_OFF: "off_light.obj",  # off_light_alt
    LIGHT_TYPE_DEFAULT: "green.obj",
    LIGHT_TYPE_FIRST: "green.obj",
    LIGHT_TYPE_TAXIWAY: "green.obj",
    LIGHT_TYPE_TAXIWAY_ALT: "amber.obj",
    LIGHT_TYPE_STOP: "red.obj",
    LIGHT_TYPE_LAST: "green.obj",
}


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
    def __init__(self, position, heading, index, size="F"):
        self.lights = []
        self.position = position
        self.heading = heading
        self.lightStringIndex = index
        self.width = TAXIWAY_WIDTH[size]  # must check size in TAXIWAY_WIDTH.keys()
        self._on = False
        self.make()

    def make(self):
        numlights = int(self.width / DISTANCE_BETWEEN_STOPLIGHTS)

        # centerline
        self.lights.append(Light(LIGHT_TYPE_STOP, self.position, 0, 0))

        # one side of centerline
        brng = self.heading + 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * DISTANCE_BETWEEN_STOPLIGHTS)
            self.lights.append(Light(LIGHT_TYPE_STOP, pos, 0, i))

        # the other side of centerline
        brng = self.heading - 90
        for i in range(numlights):
            pos = destination(self.position, brng, i * DISTANCE_BETWEEN_STOPLIGHTS)
            self.lights.append(Light(LIGHT_TYPE_STOP, pos, 0, numlights + i))

    def place(self, lightTypes):
        for light in self.lights:
            light.place(lightTypes[light.lightType], lightTypes[LIGHT_TYPE_OFF])

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
    def __init__(self):
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

    def __str__(self):
        return json.dumps({"type": "FeatureCollection", "features": self.features()})

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

    def populate(self, route, onRunway=False):
        # @todo: If already populated, must delete lights first
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
        thisLights.append(Light(LIGHT_TYPE_FIRST, currPoint, 0, 0))
        lastLight = currPoint
        # logger.debug("placed first light")
        distanceBeforeNextLight = DISTANCE_BETWEEN_GREEN_LIGHTS

        logger.debug(f"at vertex 0, {currVertex.id}, {len(thisLights)}")
        for i in range(1, len(route.route)):
            nextVertex = graph.get_vertex(route.route[i])
            logger.debug(f"at vertex {i}, {nextVertex.id}, {len(thisLights)}")

            distToNextVertex = distance(currPoint, nextVertex)
            brng = bearing(currVertex, nextVertex)

            thisEdge = graph.get_edge(currVertex.id, nextVertex.id)
            if not onILS and thisEdge.has_active("ils"):  # remember entry into ILS zone
                logger.debug(f"thisEdge active ils {thisEdge.start.id}-{thisEdge.end.id}, {i}, {thisEdge.usage}")
                onILS = thisEdge
                onILSidx = len(thisLights)
            elif not thisEdge.has_active(DEPARTURE):  # no longer an ILS zone
                # logger.debug("thisEdge %d, %s.", i, thisEdge.usage)
                onILS = False

            # logger.debug("dist to next: bearing: %f, distance: %f, type: %s", brng, distToNextVertex, thisEdge.usage)  # noqa: E501

            if route.move == DEPARTURE and thisEdge.has_active(DEPARTURE):  # must place a stopbar
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
                    self.mkStopBar(lightAtStopbar, stopbarAt, nextVertex, "start", thisEdge.widthCode("E"))
                    self.segments += 1
                    onRwy = True  # We assume that we a setting a stopbar before a runway crossing.
                else:
                    logger.debug(
                        f"LightString::populate: departure: on runway #={i}, usage={thisEdge.usage}, dept?={thisEdge.has_active(DEPARTURE)}, {thisEdge.mkActives()}"
                    )
                    if thisEdge.usage != "runway" and not thisEdge.has_active(DEPARTURE):  # if consecutive active departure segments, do not stop for them
                        logger.debug(f"departure: no longer on runway at edge {i}.")
                        onRwy = False

            # note: if move=arrival, we should not stop on the first taxiway segment, but we may have to cross another runway further on...
            # the criteria here should be refined. test for active=arrival, and runway=runway where we landed. @todo.
            # @todo: check also for hasActive(ARRIVAL)? Or either or both?
            if route.move == ARRIVAL and thisEdge.has_active(DEPARTURE) and i > MIN_SEGMENTS_BEFORE_HOLD:  # must place a stop bar
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
                    self.mkStopBar(lightAtStopbar, stopbarAt, nextVertex, "start", thisEdge.widthCode("E"))
                    self.segments += 1
                    onRwy = True  # We assume that we a setting a stopbar before a runway crossing.
                else:
                    logger.debug(f"arrival: not on runway {i}, {thisEdge.usage}")
                    if thisEdge.usage != "runway" and not thisEdge.has_active(DEPARTURE):  # if consecutive active departure segments, do not stop for them
                        logger.debug(f"arrival: no longer on runway at edge {i}.")
                        onRwy = False

            if onRwy and thisEdge.usage != "runway" and not thisEdge.has_active(DEPARTURE):  # if consecutive active departure segments, do not stop for them
                logger.debug(f"no longer on runway at edge {i}.")
                onRwy = False

            if distToNextVertex < distanceBeforeNextLight:  # we don't insert a light, we go to next leg  # noqa: E501
                distanceBeforeNextLight = distanceBeforeNextLight - distToNextVertex
            else:  # we insert a light until we reach the next point
                while distanceBeforeNextLight < distToNextVertex:
                    nextLightPos = destination(currPoint, brng, distanceBeforeNextLight)
                    brgn = bearing(lastLight, nextLightPos)
                    thisLights.append(Light(LIGHT_TYPE_TAXIWAY, nextLightPos, brgn, i))
                    lastLight = nextLightPos
                    distToNextVertex = distToNextVertex - distanceBeforeNextLight  # should be close to ftg_geoutil.distance(currPoint, nextVertex)
                    currPoint = nextLightPos
                    distanceBeforeNextLight = DISTANCE_BETWEEN_GREEN_LIGHTS
                    # logger.debug("added light %f, %f", distanceBeforeNextLight, distToNextVertex)

                distanceBeforeNextLight = distanceBeforeNextLight - distToNextVertex
                # logger.debug("remaining: %f", distanceBeforeNextLight)

                if ADD_LIGHT_AT_VERTEX:  # may be we insert a last light at the vertex?
                    brgn = bearing(lastLight, nextVertex)
                    thisLights.append(Light(LIGHT_TYPE_TAXIWAY, nextVertex, brgn, i))
                    lastLight = nextVertex
                    # logger.debug("added light at vertex %s", nextVertex.id)

            currPoint = nextVertex
            currVertex = nextVertex

        if ADD_LIGHT_AT_LAST_VERTEX:  # may be we insert a last light at the last vertex?
            lastPoint = route.route[len(route.route) - 1]
            brgn = bearing(lastLight, lastPoint)
            thisLights.append(Light(LIGHT_TYPE_TAXIWAY, lastPoint, brgn, i))
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
    def mkStopBar(self, lightIndex, src, dst, extremity="end", size="E"):
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
        return [10 * round(brng / 10), 10 * round(dist / 10), abs(brng - convertAngleTo360(heading))]

    def loadObjects(self):
        self.lightTypes = {}
        for k, f in LIGHT_TYPES_OBJFILES.items():
            self.lightTypes[k] = LightType(k, f)
            self.lightTypes[k].load()
        logger.debug("loaded.")
        return True

    def placeLights(self):
        for light in self.lights:
            light.place(self.lightTypes[light.lightType], self.lightTypes[LIGHT_TYPE_OFF])

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

        if LIGHTS_AHEAD is None or LIGHTS_AHEAD == 0:
            # Instanciate for each green light in segment and stop bar
            for i in range(start, end):
                self.lights[i].on()
            # map(lambda x: x.on(self.txy_light_obj), self.lights[start:end])
            logger.debug("no light ahead: instanciate(green): done.")
            # Instanciate for each stop light
            # for sb in self.stopbars:
            if len(self.stopbars) > 0 and segment < len(self.stopbars):
                for light in sbend.lights:
                    light.on()
                    logger.debug(f"illuminating stop light.")
                # map(lambda x: x.on(self.stp_light_obj), sbend.lights)
            logger.debug("no light ahead: instanciate(stop): done.")
        # else, lights will be turned on in front of rabbit

        if not self.rabbitCanRun:
            self.rabbitCanRun = True

        return [True, "green is set"]

    def nextStop(self):
        # index of light where should stop next
        if self.currentSegment < len(self.stopbars):
            return self.stopbars[self.currentSegment].lightStringIndex
        return len(self.lights) - 1

    def closest(self, position, after=0):
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

    def rabbit(self, start):
        if not self.rabbitCanRun:
            return 10  # checks 10 seconds later

        def restore(strt, sq, rn):
            prev = strt + ((sq - 1) % RABBIT_LENGTH)
            if prev < rn:
                self.lights[prev].on()

        rabbitNose = self.nextStop()

        if start != self.oldStart:  # restore previous but with old start
            # restore(self.oldStart, self.rabbitIdx, rabbitNose)
            self.oldStart = start
            if start > 0:  # can't be.
                self.offToIndex(start - 1)

            if LIGHTS_AHEAD > 0:
                # we need to turn lights on ahead of rabbit
                wishidx = start + RABBIT_LENGTH + LIGHTS_AHEAD
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

        curr = start + (self.rabbitIdx % RABBIT_LENGTH)
        if curr < rabbitNose:
            self.lights[curr].off()

        self.rabbitIdx += 1
        return RABBIT_DURATION

    def showAll(self, airport):
        def showSegment(s, cnt):
            brng = s.bearing()

            # light at start of segment
            self.lights.append(Light(LIGHT_TYPE_TAXIWAY, s.start, brng, cnt))
            cnt += 1

            dist = DISTANCE_BETWEEN_LIGHTS
            while dist < s.length():
                pos = destination(s.start, brng, dist)
                self.lights.append(Light(LIGHT_TYPE_TAXIWAY, pos, brng, cnt))
                cnt += 1
                dist += DISTANCE_BETWEEN_LIGHTS

            # light at end of segment
            self.lights.append(Light(LIGHT_TYPE_TAXIWAY, s.end, brng, cnt))
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
