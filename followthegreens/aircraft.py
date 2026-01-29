# Aircraft data encapsulator
#
try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import logger, get_global, TAXIWAY_WIDTH_CODE, TAXI_SPEED, RABBIT, AIRCRAFT


# fmt: off
ICAO_AND_IATA_AIRLINERS_CODES = [
"310", "312", "313", "318", "319", "31F", "31X", "31Y", "320", "321", "32S", "32S", "32S", "32S",
"330", "330", "332", "333", "340", "340", "340", "340", "342", "343", "345", "346", "359", "380",
"38F", "703", "707", "70F", "70M", "717", "722", "72A", "72F", "72S", "731", "732", "733", "734",
"735", "736", "737", "738", "739", "73A", "73F", "73G", "73H", "73M", "73S", "73W", "73X", "73Y",
"741", "742", "743", "744", "747", "74C", "74D", "74E", "74F", "74L", "74M", "74R", "74X", "74Y",
"752", "753", "757", "75F", "75M", "762", "763", "764", "767", "767", "76F", "76F", "76X", "76Y",
"772", "773", "777", "A225", "A25", "A306", "A30B", "A310", "A318", "A319", "A320", "A321", "A332",
"A333", "A342", "A343", "A345", "A346", "A359", "A388", "AB3", "AB4", "AB6", "ABF", "ABX", "ABY",
"ARJ", "ARX", "B701", "B703", "B712", "B72", "B72", "B720", "B722", "B731", "B732", "B733", "B734",
"B735", "B736", "B737", "B738", "B739", "B741", "B742", "B743", "B744", "B74R", "B74S", "B752",
"B753","B762", "B763", "B764", "B772", "B773", "E170", "E70", "GLF5", "GRJ", "RJ1H",
]  # PICK ONE ABOVE, ADD TO AIRCRAFTS LIST BELOW. EASY.
ICAO_AND_IATA_AIRLINERS_CODES_UNASSIGNED = [
"310", "312", "313",
"703", "707", "70F", "70M", "717", "722", "72A", "72F", "72S",
"741", "742", "743", "744", "747", "74C", "74D", "74E", "74F", "74L", "74M", "74R", "74X", "74Y",
"772", "773", "777", "A225", "A25", "A306", "A30B", "A332",
"A333", "A342", "A343", "A345", "A346", "A359", "A388", "AB3", "AB4", "AB6", "ABF", "ABX", "ABY",
"ARJ", "ARX", "B701", "B703", "B712", "B72", "B72", "B720", "B722",
"B741", "B742", "B743", "B744", "B74R", "B74S", "E70", "GLF5", "GRJ", "RJ1H",
]  # PICK ONE ABOVE, ADD TO AIRCRAFTS LIST BELOW. EASY.
# fmt: on

# Static definition for now, will soon be dynamically computed
AIRCRAFT_TYPES = {
    TAXIWAY_WIDTH_CODE.A: {  # General aviation
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["C172"],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        AIRCRAFT.BRAKING_DISTANCE: 70.0,
        AIRCRAFT.WARNING_DISTANCE: 150.0,
        AIRCRAFT.AVG_LENGTH: 10,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 30,  # in METERS
            RABBIT.LENGTH: 40,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
    TAXIWAY_WIDTH_CODE.B: {  # Business jet, small regional jet
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["GLF5"],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        AIRCRAFT.BRAKING_DISTANCE: 150.0,
        AIRCRAFT.WARNING_DISTANCE: 200.0,
        AIRCRAFT.AVG_LENGTH: 25,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 50,  # in METERS
            RABBIT.LENGTH: 80,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
    TAXIWAY_WIDTH_CODE.C: {  # Large regional jet, single aisle
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["318", "319", "31F", "31X", "31Y", "320", "321", "32S", "32S", "32S", "32S",
            "A320", "A321", "A21N", "A319", "A20N", "A318", "731", "732", "733", "734",
            "735", "736", "737", "738", "739", "73A", "73F", "73G", "73H", "73M", "73S", "73W", "73X", "73Y",
            "B731", "B732", "B733", "B734", "B735", "B736", "B737", "B738", "B739",
            "E170",
        ],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [12, 18],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 5],
        },
        AIRCRAFT.BRAKING_DISTANCE: 200.0,
        AIRCRAFT.WARNING_DISTANCE: 200.0,
        AIRCRAFT.AVG_LENGTH: 40,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 120,  # in METERS
            RABBIT.LENGTH: 100,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
    TAXIWAY_WIDTH_CODE.D: {  # Large narrow body, small wide body
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["A300", "A310", "A338", "A339", "330", "330", "332", "333",
            "752", "753", "757", "75F", "75M", "762", "763", "764", "767", "767", "76F", "76F", "76X", "76Y",
            "B757", "B752", "B753","B762", "B763", "B764", "B767",
        ],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [10, 16],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 4],
        },
        AIRCRAFT.BRAKING_DISTANCE: 200.0,
        AIRCRAFT.WARNING_DISTANCE: 200.0,
        AIRCRAFT.AVG_LENGTH: 55,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 150,  # in METERS
            RABBIT.LENGTH: 150,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
    TAXIWAY_WIDTH_CODE.E: {  # Large wide body
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["359", "A330", "A332", "A333", "A338", "A339", "A340", "340", "340", "340", "340",
            "342", "343", "345", "346","A350", "A358", "A359", "A35K", "B777", "B772", "B773", "B787"
        ],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [10, 14],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        AIRCRAFT.BRAKING_DISTANCE: 200.0,
        AIRCRAFT.WARNING_DISTANCE: 200.0,
        AIRCRAFT.AVG_LENGTH: 70,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 200,  # in METERS
            RABBIT.LENGTH: 150,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
    TAXIWAY_WIDTH_CODE.F: {  # Jumbo jets
        # fmt: off
        AIRCRAFT.AIRCRAFTS: ["A380", "A388", "380", "38F", "B747"],
        # fmt: on
        AIRCRAFT.TAXI_SPEED: {
            TAXI_SPEED.FAST: [10, 14],
            TAXI_SPEED.MED: [7, 10],
            TAXI_SPEED.SLOW: [5, 8],
            TAXI_SPEED.CAUTION: [3, 6],
            TAXI_SPEED.TURN: [1, 3],
        },
        AIRCRAFT.BRAKING_DISTANCE: 200.0,
        AIRCRAFT.WARNING_DISTANCE: 200.0,
        AIRCRAFT.AVG_LENGTH: 85,
        AIRCRAFT.RABBIT: {
            RABBIT.LIGHTS_AHEAD: 200,  # in METERS
            RABBIT.LENGTH: 180,  # in **METERS**
            RABBIT.SPEED: 0.20,  # SECONDS
        },
    },
}


class Aircraft:

    def __init__(self, prefs: dict = {}):
        self.prefs = prefs
        self.icao = None
        self.icaomodel = xp.findDataRef("sim/aircraft/view/acf_ICAO")
        self.tailsign = xp.findDataRef("sim/aircraft/view/acf_tailnum")
        self.lat = xp.findDataRef("sim/flightmodel/position/latitude")
        self.lon = xp.findDataRef("sim/flightmodel/position/longitude")
        self.psi = xp.findDataRef("sim/flightmodel/position/psi")
        self.groundspeed = xp.findDataRef("sim/flightmodel/position/groundspeed")
        self.tiller = xp.findDataRef("ckpt/tiller")
        self.width_code = TAXIWAY_WIDTH_CODE.C  # init to default
        self.init()
        logger.info(f"aircraft type {self.icao}, category {self.width_code}")

        # PREFERENCES - Fetched by LightString
        # These preferences are specific for an aircraft
        a = self.aircaft_preferences()
        r = self.rabbit_preferences()
        acflength = a.get(AIRCRAFT.AVG_LENGTH, 50)  # meters
        self.lights_ahead = r.get(RABBIT.LIGHTS_AHEAD, 120)  # meters
        # self.lights_ahead = self.lights_ahead + acflength  # meters
        self.rabbit_length = r.get(RABBIT.LENGTH, 100)  # meters
        self.rabbit_length = self.rabbit_length + acflength  # meters
        self.rabbit_speed = r.get(RABBIT.SPEED, 0.2)  # seconds
        # If modified in preference file
        self.set_preferences()

    def init(self):
        self.icao = xp.getDatas(self.icaomodel)
        if self.icao is None:
            self.icao = "ZZZZ"
        for ty in TAXIWAY_WIDTH_CODE:
            if self.icao in AIRCRAFT_TYPES[ty][AIRCRAFT.AIRCRAFTS]:
                self.width_code = ty
                return
        logger.info(f"aircraft type {self.icao} not found in lists, using default category {self.width_code}")

    def set_preferences(self):
        a = self.aircaft_preferences()
        acflength = a.get(AIRCRAFT.AVG_LENGTH, 50)  # meters
        # note: light count starts at the center of the aircraft.
        #       if the aircraft is 40m in length, 16m between lights,
        #       2 or more lights are not visible since under the aircraft.
        #       we take that into account by adding a full aircraft length
        #       to the desired rabbit length.
        #       we do the same for light ahead if the rabbit length is 0.
        # May be, one day, we will allow for other preferences to be set:
        # AIRCRAFT.BRAKING_DISTANCE, AIRCRAFT.WARNING_DISTANCE
        #

        acf = self.prefs.get("Aircrafts", {})

        logger.debug(f"Aircraft preferences: {acf}")
        if acf is not None:
            if RABBIT.LIGHTS_AHEAD.value in acf:
                self.lights_ahead = acf[RABBIT.LIGHTS_AHEAD.value]
            if RABBIT.LENGTH.value in acf:
                self.rabbit_length = acf[RABBIT.LENGTH.value]
            if RABBIT.SPEED.value in acf:
                self.rabbit_speed = acf[RABBIT.SPEED.value]

        prefs = acf.get(self.width_code.value, {})
        logger.debug(f"Aircraft type {self.width_code.value} preferences: {prefs}")
        if prefs is not None:
            if RABBIT.LIGHTS_AHEAD.value in prefs:
                self.lights_ahead = prefs[RABBIT.LIGHTS_AHEAD.value]
            if RABBIT.LENGTH.value in prefs:
                self.rabbit_length = prefs[RABBIT.LENGTH.value]
            if RABBIT.SPEED.value in prefs:
                self.rabbit_speed = prefs[RABBIT.SPEED.value]

        prefs = acf.get(self.icao, {})
        logger.debug(f"Aircraft model {self.icao} preferences: {prefs}")
        if prefs is not None:
            if RABBIT.LIGHTS_AHEAD.value in prefs:
                self.lights_ahead = prefs[RABBIT.LIGHTS_AHEAD.value]
            if RABBIT.LENGTH.value in prefs:
                self.rabbit_length = prefs[RABBIT.LENGTH.value]
            if RABBIT.SPEED.value in prefs:
                self.rabbit_speed = prefs[RABBIT.SPEED.value]

        if self.rabbit_length == 0:  # no rabbit
            self.lights_ahead = self.lights_ahead + acflength  # meters
        else:
            self.rabbit_length = self.rabbit_length + acflength  # meters
        logger.debug(
            f"AIRCRAFT rabbit (physical): length={self.rabbit_length}m, speed={self.rabbit_speed}s, ahead={self.lights_ahead}m (avg acf length={acflength}m)"
        )

    def position(self) -> list:
        return [xp.getDataf(self.lat), xp.getDataf(self.lon)]

    def heading(self) -> float:
        return xp.getDataf(self.psi)

    def speed(self) -> float:
        return xp.getDataf(self.groundspeed)

    def tiller(self) -> float:
        # runs [-50, 50]
        return xp.getDataf(self.tiller)

    def airport(self, pos):
        next_airport_index = xp.findNavAid(None, None, pos[0], pos[1], None, xp.Nav_Airport)
        if next_airport_index:
            return xp.getNavAidInfo(next_airport_index)
        return None

    def lights_far(self, distance: float, lights: int) -> float:
        # Distance between lights to see lights at distance
        # Used to determine rabbit length
        return distance / lights

    def taxi_speed_ranges(self) -> dict:
        return AIRCRAFT_TYPES[self.width_code][AIRCRAFT.TAXI_SPEED]

    def aircaft_preferences(self) -> dict:
        # preferences for later user
        return AIRCRAFT_TYPES[self.width_code]

    def rabbit_preferences(self, preferences: dict = {}) -> dict:
        # preferences for later user
        return AIRCRAFT_TYPES[self.width_code][AIRCRAFT.RABBIT]

    def warning_distance(self, target: float = 0.0) -> float:
        # @todo: Estimate braking distance from current speed to target
        # currently hardcoded to ~200m
        return AIRCRAFT_TYPES[self.width_code][AIRCRAFT.WARNING_DISTANCE]

    def braking_distance(self, target: float = 0.0) -> float:
        # @todo: Estimate braking distance from current speed to target
        # currently hardcoded to ~200m
        return AIRCRAFT_TYPES[self.width_code][AIRCRAFT.BRAKING_DISTANCE]
