__NAME__ = "Follow the greens"
__SIGNATURE__ = "xppython3.followthegreens"
__DESCRIPTION__ = "Follow the greens, an X-Plane ATC A-SMGCS experience."
__VERSION__ = "1.6.2"


from .followthegreens import FollowTheGreens
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
from .globals import FOLLOW_THE_GREENS_IS_RUNNING, XP_FTG_COMMAND, XP_FTG_COMMAND_DESC, XP_STW_COMMAND, XP_STW_COMMAND_DESC
