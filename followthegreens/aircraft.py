# Aircraft data encapsulator
#
import xp
import csv
import logging
import os
from .XPDref import XPDref

FILENAME = "ICAO Code extractor.csv"


def load_aircrafts():
    """Loading Aircraft ICAO codes for AAC
     FAA Aircraft Design Group = ADG this is what we use, but
     As the database only has the FAA Airport Design Airplane Design Group (ADG) and not
     ICAO Airport Reference Code (ARC) we translate FAA ADG into ICAO ARC
     FAA ADG    ICAO ARC
     Group I    Code A
     Group II   Code B
     Group III  Code C
     Group IV   Code D
     Group V    Code E
     Group VI   Code F
     Group >VI  Code F
          """
    transform = {"I": "A", "II": "B", "III": "C", "IV": "D", "V": "E", "VI": "F"}
    curr_dir = os.path.dirname(os.path.realpath(__file__))
    real_path = os.path.join(curr_dir, FILENAME)
    diction = {}
    with open(real_path, newline="", encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";", quotechar='"')
        for row in reader:
            if row["ADG"] not in transform:
                transform[row["ADG"]] = "F"
            diction[row["ICAO Code"]] = transform[row["ADG"]]
    Aircraft.aircrafts = dict(sorted(diction.items()))
    logging.info("Aircraft::load_aircrafts: We found {} aircraft design codes".format(len(Aircraft.aircrafts)))


class Aircraft:
    aircrafts = {}

    def __init__(self, callsign):
        self.icaomodel = XPDref("sim/aircraft/view/acf_ICAO", "string[0:10]")
        self.tailsign = XPDref("sim/aircraft/view/acf_tailnum", "string[0:10]")
        self.lat = XPDref("sim/flightmodel/position/latitude")
        self.lon = XPDref("sim/flightmodel/position/longitude")
        self.psi = XPDref("sim/flightmodel/position/psi")
        self.groundspeed = XPDref("sim/flightmodel/position/groundspeed")
        self.localTime = XPDref("sim/time/local_time_sec")
        self.callsign = callsign
        logging.info("Aircraft::Aircraft Tailsign: {}".format(self.tailsign.value))
        if len(Aircraft.aircrafts) == 0:
            load_aircrafts()
        logging.info("Aircraft::Aircraft ICAOMODEL: {}".format(self.icaomodel.value))
        if self.icaomodel.value and \
                self.icaomodel.value in Aircraft.aircrafts and \
                Aircraft.aircrafts[self.icaomodel.value] != "No Value":
            self.icaocat = Aircraft.aircrafts[self.icaomodel.value]
        else:
            self.icaocat = "A"  # All not listed ones are A !!!
            # @todo Dialog showing that the icaocat is not found and which to select
        # for testing purposes
        # self.icaocat = "F"
        logging.info("Aircraft::Aircraft ICAOCAT: {}".format(self.icaocat))

    def position(self):
        return [self.lat.value, self.lon.value]

    def heading(self):
        return self.psi.value

    def speed(self):
        return self.groundspeed.value

    def airport(self, pos):
        next_airport_index = xp.findNavAid(
            None, None, pos[0], pos[1], None, xp.Nav_Airport
        )
        if next_airport_index:
            return xp.getNavAidInfo(next_airport_index)
        return None

    def hourOfDay(self):
        return int(self.localTime.value / 3600)  # seconds since midnight??
