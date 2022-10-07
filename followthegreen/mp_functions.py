# Utilities for Multiprocessing

import os
import logging
import multiprocessing
import re

try:
    import xp
    from .mp_flightloop import MyLoadingFlightLoop

except ImportError:
    pass


class Feedback:
    """Class to deliver the results from the separate process via the pipe to the flight loop"""

    def __init__(self):
        """Initialize Feedback class"""
        self.status = "not started"
        self.name = ""
        self.altitude = 0
        self.scenery_pack = False
        self.icao = ""
        self.loaded = False
        self.lines = []
        self.new_lines = []


class AptLine:
    """Similar Class definition like in airport package but need to defined here also for the check"""

    # APT.DAT line for this airport
    def __init__(self, line):
        self.arr = line.split()
        if len(self.arr) == 0:
            print("Empty line")
    # logging.debug("AptLine::linecode: empty line? '%s'", line)

    def linecode(self):
        if len(self.arr) > 0:
            return int(self.arr[0])
        return None

    def content(self):
        if len(self.arr) > 1:
            return " ".join(self.arr[1:])
        return None  # line has no content


class MultiProcessLoader:
    """Initiates the separate process to load the data"""

    def __init__(self, airport, ui):
        self.fl = None
        self.airport = airport
        self.ui = ui

    def start(self):
        """start the separate process and the flight loop"""
        logging.debug("mp_functions::MultiProcessLoader: started")
        multiprocessing.set_executable(xp.pythonExecutable)
        parent_conn, child_conn = multiprocessing.Pipe()
        logging.debug("mp_functions::MultiProcessLoader: start parent connection: " + str(parent_conn))
        logging.debug("mp_functions::MultiProcessLoader: start child connection: " + str(child_conn))
        p = multiprocessing.Process(target=function_frame, args=(child_conn, xp.getSystemPath(), self.airport.icao, ))
        p.start()
        logging.debug("mp_functions::process started: PID: " + str(p.pid))
        logging.debug("mp_functions::process started: conn " + str(child_conn.poll()))
        self.fl = MyLoadingFlightLoop(self.airport, parent_conn, p, self.ui)
        self.fl.startFlightLoop()
        if p.is_alive():
            logging.debug("mp_functions::MultiProcessLoader: second process alive")
        return 1


def function_frame(conn, path, icao):
    """Calling function for status management of the reader"""

    x = Feedback()
    x.status = 'Reading data'
    conn.send(x)
    fileread(conn, path, icao, x)
    x.status = 'Airport loaded'
    conn.send(x)
    conn.close()
    return


def fileread(conn, path, icao, x):
    """file reader similar to the load function in the airport package"""
    SCENERY_PACKS = os.path.join(path, "Custom Scenery", "scenery_packs.ini")
    scenery_packs = open(SCENERY_PACKS, "r")
    scenery = scenery_packs.readline()
    scenery = scenery.strip()
    x.loaded = False
    while not x.loaded and scenery:  # while we have not found our airport and there are more scenery packs
        if re.match("^SCENERY_PACK", scenery, flags=0):
            scenery_pack_dir = scenery[13:-1]
            if scenery_pack_dir == "*GLOBAL_AIRPORTS*":
                scenery_pack_dir = os.path.join(path,"Global Scenery", "Global Airports")
            x.status = "search : " + scenery_pack_dir
            conn.send(x)
            scenery_pack_apt = os.path.join(path, scenery_pack_dir, "Earth nav data", "apt.dat")
            if os.path.isfile(scenery_pack_apt):
                apt_dat = open(scenery_pack_apt, "r", encoding="utf-8", errors="ignore")
                line = apt_dat.readline()
                while not x.loaded and line:  # while we have not found our airport and there are more lines in this pack
                    if re.match("^1 ", line, flags=0):  # if it is a "startOfAirport" line
                        newparam = line.split()  # if no characters supplied to split(), multiple space characters as one
                        if newparam[4] == icao:  # it is the airport we are looking for
                            x.name = " ".join(newparam[5:])
                            x.altitude = newparam[1]
                            x.scenery_pack = scenery_pack_apt
                            x.lines.append(AptLine(line))
                            line = apt_dat.readline()
                            while line and not re.match("^1 ", line, flags=0):
                                testline = AptLine(line)
                                if testline.linecode() is not None:
                                    x.lines.append(testline)
                                else:
                                    print("Empty line")
                                line = apt_dat.readline()  # next line in apt.dat
                            x.loaded = True
                    if line:  # otherwize we reached the end of file
                        line = apt_dat.readline()  # next line in apt.dat
                apt_dat.close()
        scenery = scenery_packs.readline()
    scenery_packs.close()
    x.new_lines = x.lines
    return x.loaded


if __name__ == '__main__': # Only in case....
    pass

