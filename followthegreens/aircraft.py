# Aircraft data encapsulator
#
import xp

from .globals import logger, TAXIWAY_WIDTH_CODE, TAXI_SPEED

ICAO_AND_IATA_AIRLINERS_CODES = [
    "310", "312", "313", "318", "319", "31F", "31X", "31Y", "320", "321", "32S", "32S", "32S", "32S", "330", "330", "332", "333",
    "340", "340", "340", "340", "342", "343", "345", "346", "359", "380", "38F", "703", "707", "70F", "70M", "717", "722", "72A",
    "72F", "72S", "731", "732", "733", "734", "735", "736", "737", "738", "739", "73A", "73F", "73G", "73H", "73M", "73S", "73W",
    "73X", "73Y", "741", "742", "743", "744", "747", "74C", "74D", "74E", "74F", "74L", "74M", "74R", "74X", "74Y", "752", "753",
    "757", "75F", "75M", "762", "763", "764", "767", "767", "76F", "76F", "76X", "76Y", "772", "773", "777", "A225", "A25", "A306",
    "A30B", "A310", "A318", "A319", "A320", "A321", "A332", "A333", "A342", "A343", "A345", "A346", "A359", "A388", "AB3", "AB4",
    "AB6", "ABF", "ABX", "ABY", "ARJ", "ARX", "B701", "B703", "B712", "B72", "B72", "B720", "B722", "B731", "B732", "B733", "B734",
    "B735", "B736", "B737", "B738", "B739", "B741", "B742", "B743", "B744", "B74R", "B74S", "B752", "B753", "B762", "B763", "B764",
    "B772", "B773", "E170", "E70", "GLF5", "GRJ", "RJ1H"
] # PICK ONE ABOVE, ADD TO AIRCRAFTS LIST BELOW. EASY.

# Static definition for now, will soon be dynamically computed
AIRCRAFT_TYPES = {
    TAXIWAY_WIDTH_CODE.A: {  # General aviation
        "AIRCRAFTS": ["C172"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
    },
    TAXIWAY_WIDTH_CODE.B: {  # Business jet, small regional jet
        "AIRCRAFTS": ["FX8"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
    },
    TAXIWAY_WIDTH_CODE.C: {  # Large regional jet, single aisle
        "AIRCRAFTS": ["A320", "B737", "B738", "B739", "A321", "A21N", "A319", "A20N", "A318"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
    },
    TAXIWAY_WIDTH_CODE.D: {  # Large narrow body, small wide body
        "AIRCRAFTS": ["A300", "A310", "B757", "B767", "A338", "A339"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
    },
    TAXIWAY_WIDTH_CODE.E: {  # Large wide body
        "AIRCRAFTS": ["A330", "A340", "A350", "B777", "B787", "A358", "A359", "A35K"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
    },
    TAXIWAY_WIDTH_CODE.F: {  # Jumbo jets
        "AIRCRAFTS": ["A380", "A388", "B747"],
        "TAXI_SPEED": {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        "BRAKING_DISTANCE": 200.0,
        "WARNING_DISTANCE": 150.0,
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
