__NAME__ = "Follow the greens"
__SIGNATURE__ = "xppython3.followthegreens"
__DESCRIPTION__ = "Follow the greens, an X-Plane ATC A-SMGCS experience."
__VERSION__ = "2.0.0"


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
from .globals import FOLLOW_THE_GREENS_IS_RUNNING
from .globals import XP_FTG_COMMAND, XP_FTG_COMMAND_DESC, FTG_MENU
from .globals import XP_STW_COMMAND, XP_STW_COMMAND_DESC, STW_MENU
from .globals import XP_FTG_CLEARANCE_COMMAND, XP_FTG_CLEARANCE_COMMAND_DESC
from .globals import XP_FTG_CANCEL_COMMAND, XP_FTG_CANCEL_COMMAND_DESC
from .globals import XP_FTG_OK_COMMAND, XP_FTG_OK_COMMAND_DESC
from .globals import XP_FTG_SPEED_COMMAND, XP_FTG_SPEED_COMMAND_DESC
