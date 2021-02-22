# Aircraft data encapsulator
#
import xp
from .XPDref import XPDref


class Aircraft:
    def __init__(self, icaomodel, icaocategory, tailsign, callsign):
        self.icaomodel = XPDref("sim/aircraft/view/acf_ICAO")
        self.tailsign = XPDref("sim/aircraft/view/acf_tailnum")
        self.lat = XPDref("sim/flightmodel/position/latitude")
        self.lon = XPDref("sim/flightmodel/position/longitude")
        self.psi = XPDref("sim/flightmodel/position/psi")
        self.groundspeed = XPDref("sim/flightmodel/position/groundspeed")
        self.localTime = XPDref("sim/time/local_time_sec")
        self.callsign = callsign
        self.icaocat = icaocategory


    def position(self):
        return [self.lat.value, self.lon.value]

    def heading(self):
        return self.psi.value

    def speed(self):
        return self.groundspeed.value

    def airport(self, pos):
        next_airport_index = xp.findNavAid(None, None, pos[0], pos[1], None, xp.Nav_Airport)
        if next_airport_index:
            return xp.getNavAidInfo(next_airport_index)
        return None

    def hourOfDay(self):
        return int(self.localTime.value / 3600)  # seconds since midnight??