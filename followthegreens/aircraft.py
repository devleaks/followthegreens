# Aircraft data encapsulator
#
import xp

from .globals import TAXIWAY_WIDTH_CODE, TAXI_SPEED, BRAKING_DISTANCE


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
        return TAXI_SPEED

    def braking_distance(self, target: float = 0.0):
        # @todo: Estimate braking distance from current speed to target
        # currently hardcoded to ~200m
        return BRAKING_DISTANCE
