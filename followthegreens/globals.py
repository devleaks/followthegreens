# Global constants
#
import os
import logging
from enum import Enum, StrEnum

# Setup logging
plugin_path = os.path.dirname(__file__)
FORMAT = "%(levelname)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
LOGFILENAME = "ftg_log.txt"
logging.basicConfig(
    #
    #
    level=logging.DEBUG,
    #
    #   You can change the above level by using WARN, INFO, or DEBUG.
    #   In case of problem, the developer may ask you to set the level
    #   to a specific value.
    #   Messages are logged in the file called ftg_log.txt that is located
    #   in the followthegreens folder.
    #
    #
    format=FORMAT,
    handlers=[
        logging.FileHandler(os.path.join(plugin_path, "..", LOGFILENAME)),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("FtG")

SHOW_TRACE = True

# X-Plane Interface
FTG_PLUGIN_ROOT_PATH = "XPPython3/followthegreens/"


class FTG_STATUS(StrEnum):
    NEW = "NEW"
    INITIALIZED = "INIT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class FTG_FSM(StrEnum):
    INITIALIZED = "INIT"
    DESTNATION = "DESTNATION"
    RUNNING = "RUNNING"
    WAIT_CLR = "WAIT FOR CLEARANCE"
    WAIT_END = "WAIT END"


# ################################
# X-PLANE Interface
#
# Menu entry texts
FTG_MENU = "Follow the greens..."
STW_MENU = "Show taxiways"  # if None, do not show menu entry for Show Taxiways, mainly used for debugging...

# Commands: Path and description
FTG_COMMAND = FTG_PLUGIN_ROOT_PATH + "main_windown_toggle"
FTG_COMMAND_DESC = "Open or close Follow the greens window"

FTG_CLEARANCE_COMMAND = FTG_PLUGIN_ROOT_PATH + "send_clearance_ok"
FTG_CLEARANCE_COMMAND_DESC = "Clears next stop bar on greens"

FTG_CANCEL_COMMAND = FTG_PLUGIN_ROOT_PATH + "send_cancel"
FTG_CANCEL_COMMAND_DESC = "Cancel Follow the greens"

FTG_OK_COMMAND = FTG_PLUGIN_ROOT_PATH + "send_ok"
FTG_OK_COMMAND_DESC = "Send OK to Follow the greens"

STW_COMMAND = FTG_PLUGIN_ROOT_PATH + "highlight_taxiways_toggle"
STW_COMMAND_DESC = "Show / hide taxiway network"

FTG_SPEED_COMMAND = FTG_PLUGIN_ROOT_PATH + "speed_"  # + FTP_SPEED
FTG_SPEED_COMMAND_DESC = "Set Follow the Greens rabbit to "  # + FTP_SPEED

# Data Accessor
FTG_IS_RUNNING = FTG_PLUGIN_ROOT_PATH + "is_running"


# X-PLANE Runway Lights Datarefs
class AMBIANT_RWY_LIGHT(StrEnum):
    OFF = "off"
    LOW = "lo"
    MEDIUM = "med"
    MED = "med"
    HIGH = "hi"


AMBIANT_RWY_LIGHT_CMDROOT = "sim/operation/rwy_lights_"  # + AMBIANT_RWY_LIGHT
AMBIANT_RWY_LIGHT_VALUE = "sim/graphics/scenery/airport_light_level"
AIRPORTLIGHT_ON = "sim/graphics/scenery/airport_lights_on"

# Preferences
RUNWAY_LIGHT_LEVEL_WHILE_FTG = AMBIANT_RWY_LIGHT.LOW

# ################################
# FTG USER INTERFACE
#
# Main UI Window display and position
#
MAINWINDOW_AUTOHIDE = True  # If false, main UI window will always remain visible.
MAINWINDOW_DISPLAY_TIME = 30  # If above true, main UI window will disappear after that amount seconds of inactivity

# you may carefully adjust those:
MAINWINDOW_FROM_LEFT = 100  # Distance of main UI window from left of screen
MAINWINDOW_FROM_BOTTOM = 80  # Distance of the bottom of the main window from the bottom of the screen

# don't touch those:
MAINWINDOW_WIDTH = 500  # Normal main window width. May need adjustment if font size is changed
MAINWINDOW_HEIGHT = 80  # Additional main window height to accommodate from space and title bar


# ################################
# FTG INTERNALS
#
# X-Plane APT files constants and keywords
#
class NODE_TYPE(StrEnum):
    BOTH = "both"
    DESTNATION = "dest"
    DEPART = "init"
    JUNCTION = "junc"


class TAXIWAY_DIRECTION(StrEnum):
    ONEWAY = "oneway"
    TWOWAY = "twoway"
    INNER = "inner"
    OUTER = "outer"
    BOTH = "both"


class TAXIWAY_TYPE(StrEnum):
    TAXIWAY = "taxiway"
    RUNWAY = "runway"
    BOTH = "both"


class TAXIWAY_ACTIVE(StrEnum):
    DEPARTURE = "departure"
    ARRIVAL = "arrival"
    ILS = "ils"


# AIRPORT/AERONAUTICAL CONSTANTS
#
# ICAO Annex 14 - Aerodrome Reference Code Element 2, Table 1-1
# (Aeroplane Wingspan; Outer Main Gear Wheel Span)
# Code A - < 15m (49.2'); <4.5m (14.8')
# Code B - 15m (49.2') - <24m (78.7'); 4.5m (14.8') - <6m (19.7')
# Code C - 24m (78.7') - <36m (118.1'); 6m (19.7') - <9m (29.5')
# Code D - 36m (118.1') - <52m (170.6'); 9m (29.5') - <14m (45.9')
# Code E - 52m (170.6') - <65m (213.3'); 9m (29.5') - <14m (45.9')
# Code F - 65m (213.3') - <80m (262.5'); 14m (45.9') - <16m (52.5')
#
# X  WheelBase  WingSpan Example
# A 4.5m  15m Learjet 45, Baron etc, DC2 Beaver
# B 6m  24m DHC6 Twotter,
# C 9m  36m 737 NG / 737 , Q400, 300 ATR 72, A320 / E jet / Q400,300, F50
# D 14m 52m
# E 14m 65m Boeing 747 to 400 / A330/ 340 , 787-8 (DL)
# F 16m 80m 747_800, airbus
#
# Aicraft type/class (size) is used to estimate minimal taxiway width
#
class TAXIWAY_WIDTH_CODE(Enum):  # Half width of taxiway in meters
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


class TAXIWAY_WIDTH(Enum):  # Half width of taxiway in meters
    A = 4  # 7.5m
    B = 6  # 10.5m
    C = 8  # 15m or 18m
    D = 9  # 18m or 23m
    E = 12  # 23m
    F = 15  # 30m


# ROUTING
class ROUTING_ALGORITHMS(StrEnum):
    DIJKSTRA = "dijkstra"
    ASTAR = "astart"


ROUTING_ALGORITHM = ROUTING_ALGORITHMS.ASTAR  # astar, dijkstra (default)
USE_STRICT_MODE = True  # set to True at your own risk


# INTERNALS
#
class MOVEMENT(StrEnum):
    ARRIVAL = "arrival"
    DEPARTURE = "departure"


DISTANCE_TO_RAMPS = 100  # meters, if closer that this to a ramp, assume departure, otherwise, assume arrival
TOO_FAR = 500  # meters, if further than this from a taxiway, does not kick in.
WARNING_DISTANCE = 150  # When getting close to a STOP BAR, show main window.

PLANE_MONITOR_DURATION = 3  # sec, flight loop to monitor plane movements. No need to rush. Mainly turns lights off behind plane.
MIN_SEGMENTS_BEFORE_HOLD = 3  # on arrival, number of segments to travel before getting potential stop bar

ADD_LIGHT_AT_VERTEX = False  # Add a light at each taxiway network vertex on the path
ADD_LIGHT_AT_LAST_VERTEX = False  # Add a light at the last vertex, even if it is closer than DISTANCE_BETWEEN_GREEN_LIGHTS
ADD_STOPBAR_AT_LAST_VERTEX = False  # Add a stop bar at the end (artificial)

# Follow the greens lighting constants
#
DISTANCE_BETWEEN_GREEN_LIGHTS = 20  # meters, distance between lights on ground. I *think* that the standard for taxi center line lights is 60 meters.
DISTANCE_BETWEEN_STOPLIGHTS = 2  # meters, distance between red stop lights on the ground. Should be small, like 2 meters
DISTANCE_BETWEEN_LIGHTS = 40  # meters, when showing all taxiways. This can build numerous lights! Use 40-80 range.


# ################################
# RABBIT
#
class RABBIT_MODE(StrEnum):
    SLOW = "slow"
    SLOWER = "slower"
    MED = "med"
    FASTER = "faster"
    FAST = "fast"


LIGHTS_AHEAD = 0  # Number of lights in front of rabbit. If 0, lights all lights up to next stopbar or destination.
RABBIT_LENGTH = 10  # number of lights that blink in front of aircraft
RABBIT_DURATION = 0.15  # sec duration of "off" light in rabbit

# As a first step, uses 5 standard rabbit (length, speed)
FTG_SPEED_PARAMS = {  # [#lights_in_rabbit(int), #secs_for_one_light(float)]
    RABBIT_MODE.FAST: [
        2 * RABBIT_LENGTH,
        RABBIT_DURATION / 2,
    ],  # accelerate (long and fast)
    RABBIT_MODE.FASTER: [
        RABBIT_LENGTH,
        RABBIT_DURATION / 3,
    ],  # go faster (same length, faster)
    RABBIT_MODE.MED: [RABBIT_LENGTH, RABBIT_DURATION],  # normal
    RABBIT_MODE.SLOWER: [
        RABBIT_LENGTH,
        3 * RABBIT_DURATION,
    ],  # slow down (same length, slower)
    RABBIT_MODE.SLOW: [
        int(RABBIT_LENGTH / 2),
        2 * RABBIT_DURATION,
    ],  # slow down (short and slow)
}


# RABBIT SPEED CONTROL
# Speed target, will soon move to Aircraft()
class TAXI_SPEED(Enum):  # in m/s
    FAST = [12, 18]
    MED = [7, 10]
    SLOW = [5, 8]
    CAUTION = [3, 6]
    TURN = [1, 3]


BRAKING_DISTANCE = 200.0  # m, currently hardcoded, will soon be computed


# ################################
# LIGHTS
#
class LIGHT_TYPE(StrEnum):  # DO NOT CHANGE
    OFF = "OFF"
    DEFAULT = "DEFAULT"
    FIRST = "FIRST"
    TAXIWAY = "TAXIWAY"
    TAXIWAY_ALT = "TAXIWAY_ALT"
    STOP = "STOP"
    LAST = "LAST"


LIGHT_TYPE_OBJFILES = {  # key MUST be one of the above enum key
    LIGHT_TYPE.OFF: "off_light.obj",  # physical taxiway off light, DO NOT CHANGE
    LIGHT_TYPE.DEFAULT: "green.obj",  # or ("custom_green.obj", (0, 1, 0), 20, 20, 3) to define a custom light that will dynamically be generated
    LIGHT_TYPE.FIRST: "green.obj",  # DO NOT use file name green.obj, amber.obj, red.obj to not override default files. It might break the entire app
    LIGHT_TYPE.TAXIWAY: "green.obj",  # format is (filename, (red[0-1], green, blue), size[5-60], intensity[5-50], texture[0-3]) ([n-m]: value between n and m.)
    LIGHT_TYPE.TAXIWAY_ALT: "amber.obj",
    LIGHT_TYPE.STOP: "red.obj",
    LIGHT_TYPE.LAST: "green.obj",
}


# ################################
# MISCELLANEOUS
#
class ATC(StrEnum):
    NONE = "None"
    DELIVERY = "Delivery"
    GROUND = "Ground"
    TOWER = "Tower"
    TRACON = "Tracon"
    CENTER = "Center"


# ATC greetings
GOOD = {"morning": 4, "day": 9, "afternoon": 12, "evening": 17, "night": 20}  # hour time of day when to use appropriate greeting
# GOOD = {"morning": 4, "day": 6, "afternoon": 9, "evening": 12, "night": 17}  # special US :-D
