# Geographic geometry utility functions
# I tested geo-py but precision was inferior(?).
# I'd love to user pyturf but it does not have all function I need
# and it loads heavy packages.
# So I made the functions I need.
#
import math
import json

# Geology constants
R = 6371000            # Radius of third rock from the sun, in metres
FT = 12 * 0.0254       # 1 FOOT = 12 INCHES
NAUTICAL_MILE = 1.852  # Nautical mile in meters 6076.118ft=1nm


def toNm(m):
    return math.round(m / NAUTICAL_MILE)


def toFeet(m):
    return math.round(m / FT)


def toMeter(f):
    return math.round(ft * FT)


def toKn(kmh):
    return kmh / NAUTICAL_MILE


def toKmh(kn):
    return kn * NAUTICAL_MILE


def convertAngleTo360(alfa):
    beta = alfa % 360
    if beta < 0:
        beta = beta + 360
    return beta


def turn(bi, bo):
    t = bi - bo
    if t < 0:
        t += 360
    if t > 180:
        t -= 360
    return t


def sign(x):  # there is no sign function in python...
    if x < 0:
        return -1
    elif x > 0:
        return 1
    return 0


class Feature:

    def __init__(self):
        self.properties = {}
        self.featureType = "Feature"

    def props(self):
        return self.properties

    def setProp(self, name, value):
        self.properties[name] = value

    def getProp(self, name):
        if name in self.properties.keys():
            return self.properties[name]
        return None

    def feature(self):
        return {
            "type": "Feature",
            "geometry": self.geom(True),
            "properties": self.props()
        }

    def geom(self, lonLat=False):
        return {
            "type": self.geomType,
            "coordinates": self.coords(lonLat)
        }

    def __str__(self):
        return json.dumps(self.feature())


class FeatureCollection:

    def __init__(self, features=[]):
        self.features = features

    def featureCollection(self):
        return {
            "type": "FeatureCollection",
            "features": self.features
        }

    def __str__(self):
        return json.dumps(self.featureCollection())

    def save(self, filename):
        f = open(filename, 'w')
        json.dump(self.featureCollection(), f, indent=2)
        f.close()


class Point(Feature):

    def __init__(self, lat, lon, alt=0):
        Feature.__init__(self)
        self.geomType = "Point"
        self.lat = float(lat)
        self.lon = float(lon)
        self.alt = float(alt)
        # self.properties["marker"] = None
        self.properties["marker-color"] = "#aaaaaa"
        self.properties["marker-size"] = "medium"

    def coords(self, lonLat=False):
        if lonLat:
            return [self.lon, self.lat]
        return [self.lat, self.lon]  # should be lon, lat for pure geojson.


class Line(Feature):

    def __init__(self, start, end):
        Feature.__init__(self)
        self.geomType = "LineString"
        self.start = start
        self.end = end
        self.properties["stroke"] = "#aaaaaa"
        self.properties["strokeWidth"] = 1
        self.properties["strokeOpacity"] = 1

    def coords(self, lonLat=False):
        return [self.start.coords(lonLat), self.end.coords(lonLat)]

    def length(self):
        return distance(self.start, self.end)

    def bearing(self):
        return bearing(self.start, self.end)


class LineString(Feature):

    def __init__(self, points):
        Feature.__init__(self)
        self.geomType = "LineString"
        self.points = points
        self.properties["stroke"] = "#aaaaaa"
        self.properties["strokeWidth"] = 1
        self.properties["strokeOpacity"] = 1

    def coords(self, lonLat=False):
        return list(map(lambda x: x.coords(lonLat), self.points))

    def getLine(self, idx):
        COPYPROPS = ["name", "edge"]
        if idx < len(self.points) - 1:
            l = Line(self.points[idx], self.points[idx + 1])
            for prop in COPYPROPS:
                if prop in self.points[idx].properties:
                    l.setProp(prop, self.points[idx].properties[prop])
            return l
        return None


class Polygon(Feature):

    def __init__(self, p):
        Feature.__init__(self)
        self.geomType = "Polygon"
        self.coordinates = p
        self.properties["stroke"] = "#aaaaaa"
        self.properties["strokeWidth"] = 1
        self.properties["strokeOpacity"] = 1

    def coords(self, lonLat=False):
        return list(map(lambda x: x.coords(lonLat), self.coordinates))


    @staticmethod
    def mkPolygon(lat1, lon1, lat2, lon2, width):
        p1 = Point(lat1, lon1)
        p2 = Point(lat2, lon2)
        brng = bearing(p1, p2)
        # one side of centerline
        brng = brng + 90
        a0 = destination(p1, brng, width / 2)
        a2 = destination(p2, brng, width / 2)
        # other side of centerline
        brng = brng - 90
        a1 = destination(p1, brng, width / 2)
        a3 = destination(p2, brng, width / 2)
        # join
        return Polygon([a0, a1, a3, a2])


def haversine(lat1, lat2, long1, long2): # in radians.
    dlat, dlong = lat2 - lat1, long2 - long1
    return math.pow(math.sin(dlat / 2), 2) + math.cos(lat1) * math.cos(lat2) * math.pow(math.sin(dlong / 2), 2)


def distance(p1, p2):  # in degrees.
    lat1, lat2 = math.radians(p1.lat), math.radians(p2.lat)
    long1, long2 = math.radians(p1.lon), math.radians(p2.lon)
    a = haversine(lat1, lat2, long1, long2)
    return 2 * R * math.asin(math.sqrt(a))  # in m


def bearing(src, dst):
    lat1 = math.radians(src.lat)
    lon1 = math.radians(src.lon)
    lat2 = math.radians(dst.lat)
    lon2 = math.radians(dst.lon)

    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    t = math.atan2(y, x)
    brng = convertAngleTo360(math.degrees(t))  # in degrees
    return brng


def destination(src, brngDeg, d):
    lat = math.radians(src.lat)
    lon = math.radians(src.lon)
    brng = math.radians(brngDeg)
    r = d / R

    lat2 = math.asin(math.sin(lat) * math.cos(r) + math.cos(lat) * math.sin(r) * math.cos(brng))
    lon2 = lon + math.atan2(math.sin(brng) * math.sin(r) * math.cos(lat), math.cos(r) - math.sin(lat) * math.sin(lat2))
    return Point(math.degrees(lat2), math.degrees(lon2))


def lineintersect(line1, line2):
    # Finds intersection of line1 and line2. Returns Point() of intersection or None.
    # !! Source code copied from GeoJSON code where coordinates are (longitude, latitude).
    x1 = line1.start.lon
    y1 = line1.start.lat
    x2 = line1.end.lon
    y2 = line1.end.lat
    x3 = line2.start.lon
    y3 = line2.start.lat
    x4 = line2.end.lon
    y4 = line2.end.lat
    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    numeA = (x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)
    numeB = (x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)

    if denom == 0:
        if numeA == 0 and numeB == 0:
            return None
        return None

    uA = numeA / denom
    uB = numeB / denom

    if uA >= 0 and uA <= 1 and uB >= 0 and uB <= 1:
        x = x1 + uA * (x2 - x1)
        y = y1 + uA * (y2 - y1)
        # return [x, y]  # x is longitude, y is latitude.
        return Point(y, x)
    return None


def nearestPointToLines(p, lines):
    # First the nearest point to a collection of lines.
    # Lines is an array if Line()
    # Returns the point and and distance to it.
    nearest = None
    dist = math.inf
    for line in lines:
        d1 = distance(p, line.start)
        d2 = distance(p, line.end)
        dl = max(d1, d2)
        brng = bearing(line.start, line.end)
        brng += 90  # perpendicular
        p1 = destination(p, brng, dl)
        brng -= 180  # perpendicular
        p2 = destination(p, brng, dl)
        perpendicular = Line(p1, p2)
        intersect = lineintersect(perpendicular, line)
        if intersect:
            d = distance(p, intersect)
            if d < dist:
                dist = d
                nearest = intersect

    return [nearest, distance]  # might need to be changed to "d" as distance returns a function


def pointInPolygon(point, polygon):
    # this will do. We do very local geometry (500m around current location)
    # pt is [x,y], pol is [[x,y],...].
    pt = point.coords()
    pol = polygon.coords()
    inside = False
    for i in range(len(pol)):
        x0, y0 = pol[i]
        x1, y1 = pol[(i + 1) % len(pol)]
        if not min(y0, y1) < pt[1] <= max(y0, y1):
            continue
        if pt[0] < min(x0, x1):
            continue
        cur_x = x0 if x0 == x1 else x0 + (pt[1] - y0) * (x1 - x0) / (y1 - y0)
        inside ^= pt[0] > cur_x
    return inside


#
# Functions to smooth turns
#
#
debugFeature = []

def debugF(f, n, c=None):
    f.setProp("name", n)
    if c:
        f.setProp("stroke", c)
        f.setProp("marker-color", c)
    debugFeature.append(f)


def extendLine(line, dist):
    # Extends a line in each direction by distance meters
    brng = bearing(line.start, line.end)
    far0 = destination(line.end, brng, dist)
    far1 = destination(line.start, brng + 180, dist)
    return Line(Point(far0.lat, far0.lon), Point(far1.lat, far1.lon))


def lineOffset(line, offset):
    # Returns a line parallel to supplied line at offset meter distance.
    # Offset should be small (< 10km). Negative offset puts the line
    # on the other side.
    brng = bearing(line.start, line.end)
    if offset > 0:
        brng -= 90
    else:
        brng += 90
    d = abs(offset)
    far0 = destination(line.start, brng, d)
    far1 = destination(line.end, brng, d)
    return Line(Point(far0.lat, far0.lon), Point(far1.lat, far1.lon))


def lineArc(center, radius, bearing1, bearing2, steps=36):
    # Make a linestring arc from bearing1 to bearing2, centered on center, of radius radius.
    # Angle step size set to 360/steps.
    # Label first half of arc with idx, second half with idx+1.
    angle1 = convertAngleTo360(bearing1)
    angle2 = convertAngleTo360(bearing2)

    arcStartDegree = angle1
    arcEndDegree = angle2 + 360
    if angle1 < angle2:
        arcEndDegree = angle2

    coordinates = []
    rot = 360 / steps
    alfa = arcStartDegree
    while alfa < arcEndDegree:
        coordinates.append(destination(center, alfa, radius))
        alfa += rot

    if alfa > arcEndDegree:
        coordinates.append(destination(center, arcEndDegree, radius))

    return coordinates


def arcCenter(l0, l1, radius):
    # returns arc center, always "inside" both lines l0 and l1
    b_in = bearing(l0.start, l0.end)
    b_out = bearing(l1.start, l1.end)
    turnAngle = turn(b_in, b_out)
    oppositeTurnAngle = turn(b_out, b_in)
    l0b = lineOffset(l0, sign(turnAngle) * radius)   # offset line is always on right side of line
    l1b = lineOffset(l1, sign(oppositeTurnAngle) * radius)
    return lineintersect(l0b, l1b)


def mkTurn(l0, l1, radius, idx, step=36):
    # returns a collection of point, from l0[0] to l1[1]
    # with an arc to smoothly turn from l0 to l1.
    b_in = bearing(l0.start, l0.end)
    b_out = bearing(l1.start, l1.end)
    turnAngle = turn(b_in, b_out)
    oppositeTurnAngle = turn(b_out, b_in)

    l0e = extendLine(l0, 500)  # meters
    l1e = extendLine(l1, 500)
    cross = lineintersect(l0e, l1e)
    if not cross:
        return None

    if idx == 0:
        debugF(l0, "l0:%d" % idx, "#000000")

    debugF(l1, "l0:%d" % idx, "#000000")
    # arc center
    l0b = lineOffset(l0e, sign(oppositeTurnAngle) * radius)
    # debugF(l0b, "l0b:%d"%idx, "#ff0000")
    l1b = lineOffset(l1e, sign(oppositeTurnAngle) * radius)
    # debugF(l1b, "l0e:%d"%idx, "#00ff00")
    center = lineintersect(l0b, l1b)
    if not center:
        return None
    # debugF(center, "intersect:%d"%idx, "#888800")

    # arc
    arc0, arc1 = (0, 0)
    if turnAngle > 0:
        arc0 = b_out + 90
        arc1 = b_in + 90
    else:
        arc0 = b_in - 90
        arc1 = b_out - 90
    arc = lineArc(center, radius, arc0, arc1, step)  # steps

    if turnAngle > 0:
        # reverse coordinates order
        arc.reverse()

    # add reference to orignal line
    mid = int(len(arc) / 2)
    for i in range(len(arc)):
        if i <= mid:
            arc[i].setProp("lsidx", idx)
        else:
            arc[i].setProp("lsidx", idx + 1)

    return arc


def smoothTurns(ls, radius=60, steps=36):
    # From line string (collection of Points), returns a new line string (collection of Points)
    # with each turn smoothed.
    # We _try_ to carry some properties over from original line string to smoothed one.
    # @todo: should remove/ignore segments that are smaller than 2 * radius.
    newls = []
    ls[0].setProp("lsidx", 0)
    newls.append(ls[0])  # first point

    for i in range(1, len(ls) - 1):
        l0 = Line(ls[i - 1], ls[i])
        l0.setProp("lsidx", i - 1)
        l1 = Line(ls[i], ls[i + 1])
        l1.setProp("lsidx", i)
        arc = mkTurn(l0, l1, radius, i - 1, steps)
        if arc:
            newls += arc
        else:
            newls.append(ls[i])

    ls[-1].setProp("lsidx", len(ls) - 2)
    newls.append(ls[-1])  # last point

    return newls
