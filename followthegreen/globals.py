# Global constants
#
SYSTEM_DIRECTORY = "."

# Aeronautics constant
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
AIRCRAFT_TYPES = {  # Half width of taxiway in meters
    'A': 4,     # 7.5m
    'B': 6,     # 10.5m
    'C': 8,     # 15m or 18m
    'D': 9,     # 18m or 23m
    'E': 12,    # 23m
    'F': 15     # 30m
}


# X-Plane APT files constants
#
NODE_TYPE_BOTH = "both"
NODE_TYPE_DESTNATION = "dest"
NODE_TYPE_DEPART = "init"
NODE_TYPE_JUNCTION = "junc"

TAXIWAY_DIR_ONEWAY = "oneway"
TAXIWAY_DIR_TWOWAY = "twoway"

TAXIWAY_TYPE_TAXIWAY = "taxiway"
TAXIWAY_TYPE_RUNWAY = "runway"

TAXIWAY_ACTIVE_DEPARTURE = "departure"
TAXIWAY_ACTIVE_ARRIVAL = "arrival"
TAXIWAY_ACTIVE_ILS = "ils"

# Follow The Green constants
#
MAINWINDOW_AUTOHIDE = True
ARRIVAL = TAXIWAY_ACTIVE_ARRIVAL
DEPARTURE = TAXIWAY_ACTIVE_DEPARTURE

DISTANCE_TO_RAMPS = 100             # meters, if closer that this to a ramp, assume departure, otherwise, assume arrival
TOO_FAR = 500                       # meters, if further than this from a taxiway, does not kick in.
WARNINGDISTANCE = 150               # When getting close to a STOP BAR, show main window.

PLANE_MONITOR_DURATION = 3          # sec, flight loop to monitor plane movements. No need to rush. Mainly turns lights off behind plane.

MINSEGMENTSBEFOREHOLD = 3           # on arrival, number of segments to travel before getting potential stop bar
DISTANCEBETWEENGREENLIGHTS = 20     # 20 meter, distance between lights on ground. I *think* that the standard for taxi cetner line lights is 60 meters.
DISTANCEBETWEENSTOPLIGHTS = 2       # meter, distance between lights on ground.
ADDLIGHTATVERTEX = False            # Add a light at each taxiway network vertex on the path
ADDLIGHTATLASTVERTEX = False        # Add a light at the last vertex, even if it is closer than DISTANCEBETWEENGREENLIGHTS
ADDSTOPBARATLASTVERTEX = False      # Add a stop bar at the end (artificial)

DISTANCEBETWEENTNLIGHTS = 5

LIGHTS_AHEAD = 0                    # Number of lights in front of rabbit. If 0, lights all lights up to next stopbar or destination.
RABBIT_TIMEON = 0.4                 # sec, set to 0 to cancel rabbit
RABBIT_TIMEOFF = 2                  # sec
RABBIT_PHASE = 0.3                  # sec
RABBIT_INTENSITY = 2.0              # ratio to current value
RABBIT_LENGTH = 12                  # number of lights
RABBIT_DURATION = 0.10              # sec

ATC = {
    "None",
    "Delivery",
    "Ground",
    "Tower",
    "Tracon",
    "Center"
}

GOOD = {
    "morning": 4,
    "day": 9,
    "afternoon": 12,
    "evening": 17,
    "night": 20
}
