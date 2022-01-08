__VERSION__ = '0.5'
__NAME__ = "followthegreen"
__SIGNATURE__ = "followthegreen.xppython3"
__DESCRIPTION__ = "Follow the green, an X-Plane ATC A-SMGCS experience."

try:
    from .followthegreen import FollowTheGreen
    from .showtaxiways import ShowTaxiways
    from .aircraft import Aircraft
    from .airport import Airport
    from .flightloop import FlightLoop
    from .geo import Point, Line, Polygon, FeatureCollection
    from .geo import distance, bearing, destination
    from .geo import nearestPointToLines, pointInPolygon
    from .graph import Graph, Edge, Vertex
    from .lightstring import LightString
    from .ui import UIUtil
    from .XPDref import XPDref
except ImportError:
    pass
