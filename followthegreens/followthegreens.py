# Follow the greens XPPYthon3 Plugin Interface
#
#
import xp
import os
import tomllib
from datetime import datetime, timedelta
from textwrap import wrap
from functools import reduce

from .version import __VERSION__
from .globals import logger, get_global, FTG_STATUS, MOVEMENT, AMBIANT_RWY_LIGHT_VALUE, RABBIT_MODE, RUNWAY_BUFFER_WIDTH, SAY_ROUTE
from .aircraft import Aircraft
from .airport import Airport
from .flightloop import FlightLoop
from .lightstring import LightString
from .ui import UIUtil
from .nato import phonetic


class FollowTheGreens:

    def __init__(self, pi):
        self.__status = FTG_STATUS.NEW
        self.pi = pi
        self.airport = None
        self.aircraft = None
        self.lights = None
        self.segment = 0  # counter for green segments currently lit -0-----|-1-----|-2---------|-3---
        self.move = None  # departure or arrival, guessed first, can be changed by pilot.
        self.destination = None  # Handy

        self.ui = UIUtil(self)  # Where windows are built
        self.flightLoop = FlightLoop(self)  # where the magic is done

        self.airport_light_level = xp.findDataRef(AMBIANT_RWY_LIGHT_VALUE)  # [off, lo, med, hi] = [0, 0.25, 0.5, 0.75, 1]
        self.zuluTime = xp.findDataRef("sim/time/zulu_time_sec")
        self.localTime = xp.findDataRef("sim/time/local_time_sec")
        self.localDay = xp.findDataRef("sim/time/local_date_days")

        logger.info("=-" * 50)
        logger.info(f"Starting new session FtG {__VERSION__} at {datetime.now().astimezone().isoformat()}")

        # Load optional config file (Rel. 2 onwards)
        # Parameters in this file will overwrite (with constrain)
        # default values provided by FtG.
        self.config = {}
        here = os.path.dirname(__file__)
        CONFIGILENAME = "ftgconfig.toml"
        filename = os.path.join(here, CONFIGILENAME)
        if os.path.exists(filename):
            with open(filename, "rb") as fp:
                self.config = tomllib.load(fp)
            logger.info(f"config file {filename} loaded")
            logger.debug(f"config: {self.config}")
        else:
            logger.debug(f"no config file {filename}")
            filename = os.path.join(".", "Output", "preferences", CONFIGILENAME)  # relative to X-Plane "rott/home" folder
            if os.path.exists(filename):
                with open(filename, "rb") as fp:
                    self.config = tomllib.load(fp)
                logger.info(f"config file {filename} loaded")
                logger.debug(f"config: {self.config}")
            else:
                logger.debug(f"no config file {filename}")

    @property
    def is_holding(self) -> bool:
        return self.ui.waiting_for_clearance

    def get_config(self, name):
        # Example: get_config("AMBIANT_RWY_LIGHT_VALUE")
        # return either the config value or the global value AMBIANT_RWY_LIGHT_VALUE.
        if name not in self.config:
            logger.info(f"no config for {name}, returning global {name}={get_global(name)})")
        return self.config.get(name, get_global(name))

    def start(self):
        # Toggles visibility of main window.
        # If it was simply closed for hiding, show it again as it was.
        # If it does not exist, creates it from start of process.
        # if self.__status = FollowTheGreens.STATUS["ACTIVE"]:
        logger.info(f"status: {self.__status}, {self.ui.mainWindowExists()}.")
        if self.ui.mainWindowExists():
            logger.debug(f"mainWindow exists, changing visibility {self.ui.isMainWindowVisible()}.")
            self.ui.toggleVisibilityMainWindow()
            return 1
        else:
            # Info 1
            logger.info("starting..")
            mainWindow = self.getAirport()
            logger.debug("mainWindow created")
            if mainWindow and not xp.isWidgetVisible(mainWindow):
                xp.showWidget(mainWindow)
                logger.debug("mainWindow shown")
            logger.info("..started.")
            return 1  # window displayed
        return 0

    def rabbitMode(self, mode: RABBIT_MODE):
        self.flightLoop.manualRabbitMode(mode)

    def rabbitModeAuto(self):
        self.flightLoop.automaticRabbitMode()

    def getAirport(self):
        # Search for airport or prompt for one.
        # If airport is not equiped, we loop here until we get a suitable airport.
        # When one is given and satisfies the condition for FTG
        # we go to next step: Find the end point of Follow the greens.
        # @todo: We need to guess those from dataref
        # Note: Aircraft should be "created" outside of FollowTheGreen
        # and passed to start or getAirport. That way, we can instanciate
        # individual FollowTheGreen for numerous aircrafts.
        self.aircraft = Aircraft()

        pos = self.aircraft.position()
        if pos is None:
            logger.debug("no plane position")
            return self.ui.sorry("We could not locate your plane.")

        if pos[0] == 0 and pos[1] == 0:
            logger.debug("no plane position")
            return self.ui.sorry("We could not locate your plane.")

        # Info 2
        logger.info(f"Plane postion {pos}")
        airport = self.aircraft.airport(pos)
        if airport is None:
            logger.debug("no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logger.debug("no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        # Info 3
        logger.info(f"At {airport.name}")
        return self.getDestination(airport.navAidID)

    def getDestination(self, airport):
        # Prompt for local destination at airport.
        # Either a runway for departure or a parking for arrival.
        if not self.airport or (self.airport.icao != airport):  # we may have changed airport since last call
            airport = Airport(airport)
            # Info 4 to 8 in airport.prepare()
            status = airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning(f"airport not ready: {status[1]}")
                return self.ui.sorry(status[1])
            self.airport = airport
        else:
            logger.debug("airport already loaded")

        logger.debug("airport ready")
        self.move = self.airport.guessMove(self.aircraft.position())
        # Info 10
        logger.info(f"Guessing {self.move}")

        return self.ui.promptForDestination()

    def newGreen(self, destination):
        # What is we had a green, and now we don't?!
        # so we first make sur we find a new green, and if we do, we cancel the previous one.
        return self.followTheGreen(destination, True)

    def followTheGreen(self, destination, newGreen=False):
        # Destination is either
        #   the name of a runway for departure, or
        #   the name of a parking ramp for arrival.
        # We know where we are, we know where we want to go.
        # If we find a route, we light it.
        if destination not in self.airport.getDestinations(self.move):
            logger.debug(f"destination not valid {destination} for {self.move}")
            return self.ui.promptForDestination(f"Destination {destination} not valid for {self.move}.")

        # Info 11
        logger.info(f"Route to {destination}.")
        rerr, route = self.airport.mkRoute(self.aircraft, destination, self.move)

        if not rerr:
            logger.info(f"No route {route}")
            return self.ui.tryAgain(route)

        # Info 12
        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
        gsp = self.aircraft.speed()
        if pos is None:
            logger.debug("no plane position")
            return self.ui.sorry("We could not locate your plane.")
        if pos[0] == 0 and pos[1] == 0:
            logger.debug("no plane position")
            return self.ui.sorry("We could not locate your plane.")

        if newGreen:  # We had a green, and we found a new one.
            # turn off previous lights
            self.cancel("new green requested")
            # now create new ones

        logger.debug(f"Got route: {route}.")
        self.destination = destination
        onRwy = False
        if self.move == MOVEMENT.ARRIVAL:
            onRwy, runway = self.airport.onRunway(
                pos, width=RUNWAY_BUFFER_WIDTH
            )  # RUNWAY_BUFFER_WIDTH either side of runway, return [True,Runway()] or [False, None]
        self.lights = LightString(config=self.config)
        self.lights.populate(route, onRwy)
        if len(self.lights.lights) == 0:
            logger.debug("no lights")
            return self.ui.sorry("We could not light a route to your destination.")

        # Info 13
        logger.info(f"Added {len(self.lights.lights)} lights, {self.lights.segments + 1} segments, {len(self.lights.stopbars)} stopbars.")
        self.segment = 0
        logger.info(f"Segment {self.segment + 1}/{self.lights.segments + 1}.")
        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            return self.ui.sorry(ret[1])
        logger.debug(f"lights instanciated for segment {self.segment}.")

        initbrgn, initdist, initdiff = self.lights.initial(pos, hdg)
        logger.debug(f"init ({initbrgn}, {initdist}, {initdiff}).")

        logger.info(f"first light at {initdist} m, heading {initbrgn} DEG.")
        self.flightLoop.startFlightLoop()
        self.__status = FTG_STATUS.ACTIVE
        # Info 14
        logger.info("Flightloop started.")

        # Hint: distance and heading to first light
        intro = f"Follow the greens to {destination}"
        speak = f"Follow the greens to {phonetic(destination)}"
        if SAY_ROUTE:
            rt = route.text()
            if len(rt) > 0:
                intro = intro + f" via taxiways {rt}"
                speak = speak + f" via taxiways {phonetic(rt)}"
            intro_arr = wrap(intro + ".", width=80)  # might be long
            speak = speak + "."
        if initdiff > 20 or initdist > 200:
            dist_str = " ".join(f"{int(initdist):d}")
            hdg_str = " ".join(f"{int(initbrgn):03d}")
            intro_arr = intro_arr + [f"Start is at about {int(initdist):d} meters heading {int(initbrgn):03d}."]
            speak = speak + f" Start is at about {phonetic(dist_str)} meters heading {phonetic(hdg_str)}."
        logger.debug(" ".join(intro_arr))
        xp.speakString(speak)

        # self.segment = 0
        if self.lights.segments == 0:  # just one segment
            logger.debug(f"just one segment {self.move}")
            if self.move == MOVEMENT.ARRIVAL:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("just one segment on arrival")
                    return self.ui.promptForParked()
                if len(self.lights.stopbars) == 1:  # terminated with a stop bar, it is probably a departure...
                    logger.debug("1 segment with 1 stopbar on arrival?")
                    return self.ui.promptForClearance()
            if self.move == MOVEMENT.DEPARTURE:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("1 segment with 0 stopbar on departure?")
                    return self.ui.promptForDeparture()

        return self.ui.promptForClearance(intro=intro_arr)
        # return self.ui.sorry("Follow the greens is not completed yet.")  # development

    def nextLeg(self):
        # Called when cleared by TOWER
        self.segment += 1
        # Info 15
        logger.info(f"Segment {self.segment + 1}/{self.lights.segments + 1}.")

        if self.segment > self.lights.segments:
            self.flightLoop.stopFlightLoop()
            self.lights.destroy()
            # Info 16.a
            logger.info("done.")
            self.segment = 0  # reset
            return self.ui.bye()

        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            self.cancel()
            return self.ui.sorry(ret[1])
        logger.debug(f"lights instanciated ({self.segment}).")

        # re-authorize rabbit auto-tuning
        self.flightLoop.allow_rabbit_autotune()

        if self.move == MOVEMENT.DEPARTURE and self.segment == (self.lights.segments - 1):
            return self.ui.promptForDeparture()

        if self.move == MOVEMENT.DEPARTURE and self.segment == self.lights.segments:
            # Info 16.b
            logger.info("ready for take-off.")
            self.segment = 0  # reset
            return self.ui.bye()

        if self.move == MOVEMENT.ARRIVAL and self.segment == self.lights.segments:
            return self.ui.promptForParked()

        return self.ui.promptForClearance()

    def cancel(self, reason=""):
        # Abandon the FTG mission. Instruct subroutines to turn off FTG lights, remove them,
        # and restore the environment.
        if self.flightLoop:
            self.flightLoop.stopFlightLoop()
            logger.info("Flightloop stopped.")

        if self.lights:
            self.lights.destroy()
            self.lights = None

        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()

        # Info 16
        logger.info(f"cancelled: {reason}.")
        logger.info(f"Ending new session at {datetime.now().astimezone().isoformat()}")
        logger.info("==" * 50)
        return [True, ""]

    def hourOfDay(self):
        return int(xp.getDataf(self.localTime) / 3600)  # seconds since midnight??

    def bookmark(self, message: str = ""):
        # @todo: fetch simulator date/time too
        zs = xp.getDataf(self.zuluTime)
        ls = xp.getDataf(self.localTime)
        d = xp.getDatai(self.localDay)
        u = datetime.utcnow()
        z = datetime(year=u.year, month=1, day=1) + timedelta(days=d, seconds=zs)
        l = datetime(year=u.year, month=1, day=1) + timedelta(days=d, seconds=ls)
        logger.info(f"BOOKMARK {u.isoformat()} {message}")
        logger.info(f"simulator zulu time is {z.isoformat()}, local time is {l.isoformat()}")

    def disable(self):
        # alias to cancel
        return self.cancel("disabled")

    def stop(self):
        # alias to cancel
        return self.cancel("stopped")
