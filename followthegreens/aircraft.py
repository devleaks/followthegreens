# Aircraft data encapsulator
#
import xp

from .globals import logger, TAXIWAY_WIDTH_CODE

# Static definition for now, will soon be dynamically computed
AIRCRAFT_TYPES = {
    TAXIWAY_WIDTH_CODE.A: { # General aviation
        "AIRCRAFTS": ["C172"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
    TAXIWAY_WIDTH_CODE.B: { # Business jet, small regional jet
        "AIRCRAFTS": ["FX8"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
    TAXIWAY_WIDTH_CODE.C: { # Large regional jet, single aisle
        "AIRCRAFTS": ["A320", "B737", "B738", "B739", "A321", "A21N", "A319", "A20N", "A318"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
    TAXIWAY_WIDTH_CODE.D: { # Large narrow body, small wide body
        "AIRCRAFTS": ["A330", "B787", "A338", "A339"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
    TAXIWAY_WIDTH_CODE.E: {  # Large wide body
        "AIRCRAFTS": ["A350", "B777", "A358", "A359", "A35K"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
    TAXIWAY_WIDTH_CODE.F: {  # Jumbo jets
        "AIRCRAFTS": ["A380", "A388", "B747"],
        "TAXI_SPEED": {
            "FAST":  [12, 18],
            "MED":  [7, 10],
            "SLOW":  [5, 8],
            "CAUTION":  [3, 6],
            "TURN":  [1, 3],
        },
        "BRAKING_DISTANCE":  200.0,
        "WARNING_DISTANCE":  150.0,
    },
}

class Aircraft:
    def __init__(self):
        self.icaomodel = xp.findDataRef("sim/aircraft/view/acf_ICAO")
        self.tailsign = xp.findDataRef("sim/aircraft/view/acf_tailnum")
        self.width_code = TAXIWAY_WIDTH_CODE.C
        self.lat = xp.findDataRef("sim/flightmodel/position/latitude")
        self.lon = xp.findDataRef("sim/flightmodel/position/longitude")
        self.psi = xp.findDataRef("sim/flightmodel/position/psi")
        self.groundspeed = xp.findDataRef("sim/flightmodel/position/groundspeed")
        self.localTime = xp.findDataRef("sim/time/local_time_sec")
        self.tiller = xp.findDataRef("ckpt/tiller")
        self.init()
        logger.debug(f"new aircraft type {xp.getDatas(self.icaomodel)}, category {self.width_code}")

    def init(self):
        self.width_code = TAXIWAY_WIDTH_CODE.C
        ac = xp.getDatas(self.icaomodel)
        for ty in TAXIWAY_WIDTH_CODE:
            if ac in AIRCRAFT_TYPES[ty]["AIRCRAFTS"]:
                self.width_code = ty
                return
        logger.debug(f"aircraft type {ac} not found in lists, using default category {self.width_code}")

    def position(self):
        return [xp.getDataf(self.lat), xp.getDataf(self.lon)]

    def heading(self):
        return xp.getDataf(self.psi)

    def speed(self):
        return xp.getDataf(self.groundspeed)

    def tiller(self):
        # runs [-50, 50]
        return xp.getDataf(self.tiller)

    def airport(self, pos):
        next_airport_index = xp.findNavAid(None, None, pos[0], pos[1], None, xp.Nav_Airport)
        if next_airport_index:
            return xp.getNavAidInfo(next_airport_index)
        return None

    def hourOfDay(self):
        return int(xp.getDataf(self.localTime) / 3600)  # seconds since midnight??

    def taxi_speed_ranges(self):
        return AIRCRAFT_TYPES[self.width_code]["TAXI_SPEED"]

    def warning_distance(self, target: float = 0.0):
        # @todo: Estimate braking distance from current speed to target
        # currently hardcoded to ~200m
        return AIRCRAFT_TYPES[self.width_code]["WARNING_DISTANCE"]

    def braking_distance(self, target: float = 0.0):
        # @todo: Estimate braking distance from current speed to target
        # currently hardcoded to ~200m
        return AIRCRAFT_TYPES[self.width_code]["BRAKING_DISTANCE"]
