# Follow the greens XPPYthon3 Plugin Interface
#
#
import os
import re
import tomllib
from random import randint
from datetime import datetime, timedelta, timezone
from textwrap import wrap

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .version import __VERSION__
from .globals import logger, get_global, INTERNAL_CONSTANTS, FTG_STATUS, MOVEMENT, AMBIANT_RWY_LIGHT_VALUE, RABBIT_MODE, RUNWAY_BUFFER_WIDTH, SAY_ROUTE
from .aircraft import Aircraft
from .airport import Airport
from .flightloop import FlightLoop
from .lightstring import LightString
from .ui import UIUtil
from .nato import phonetic, toml_dumps
from .cursor import Cursor

PREFERENCE_FILE_NAME = "followthegreens.prf"  # followthegreens.prf
STATS_FILE_NAME = "ftgstats.txt"
VERSION = "VERSION"


class FollowTheGreens:

    def __init__(self, pi):
        self.status = FTG_STATUS.NEW
        self.pi = pi
        self.airport: Airport | None = None
        self.aircraft: Aircraft | None = None
        self.lights: LightString | None = None
        self.cursor: Cursor | None = None
        self.segment = 0  # counter for green segments currently lit -0-----|-1-----|-2---------|-3---
        self.move: MOVEMENT | None = None  # departure or arrival, guessed first, can be changed by pilot.
        self.destination = None  # Handy

        self.airport_light_level = xp.findDataRef(AMBIANT_RWY_LIGHT_VALUE)  # [off, lo, med, hi] = [0, 0.25, 0.5, 0.75, 1]
        self.zuluTime = xp.findDataRef("sim/time/zulu_time_sec")
        self.localTime = xp.findDataRef("sim/time/local_time_sec")
        self.localDay = xp.findDataRef("sim/time/local_date_days")
        self.session = randint(1000, 9999)
        self.route = None

        logger.info("\n\n")
        logger.info("-=" * 50)
        logger.info(
            " ".join(
                [
                    "When sending session for debugging purpose,",
                    "you can cut the file above the 'Starting new FtG session'",
                    "and after 'FtG session ended' with matching session identifier",
                    f"(session id = {self.session})",
                ]
            )
        )
        logger.info(f"Starting new FtG session {__VERSION__} at {datetime.now().astimezone().isoformat()} (session id = {self.session})")
        logger.info(f"XPPython3 {xp.VERSION}, X-Plane {xp.getVersions()}\n")

        self.stats = {}
        self.load_stats()
        self.prefs = {}
        self.init_preferences()

        self.ui = UIUtil(self)  # Where windows are built
        self.flightLoop = FlightLoop(self)  # where the magic is done

        self.status = FTG_STATUS.INITIALIZED

    @property
    def is_holding(self) -> bool:
        return self.ui.waiting_for_clearance

    @property
    def status(self) -> FTG_STATUS:
        return self._status

    @status.setter
    def status(self, status):
        self._status = status
        logger.debug(f"FtG is now {status}")

    def inc(self, name: str, qty: int = 1):
        self.stats[name] = qty if name not in self.stats else self.stats[name] + qty

    def load_stats(self, filename: str = STATS_FILE_NAME):
        fn = os.path.join(".", "Output", "logbooks", filename)  # relative to X-Plane "rott/home" folder
        if os.path.exists(fn):
            with open(fn, "rb") as fp:
                try:
                    self.stats = tomllib.load(fp)
                    logger.info(f"loaded stats: {self.stats}")
                except:
                    logger.warning(f"stats file {fn} not loaded", exc_info=True)

    def save_stats(self, filename: str = STATS_FILE_NAME):
        fn = os.path.join(".", "Output", "logbooks", filename)  # relative to X-Plane "rott/home" folder
        with open(fn, "w") as fp:
            print(toml_dumps(self.stats), file=fp)
            logger.info(f"stats written: {self.stats}")

    def init_preferences(self, reloading: bool = False):
        # Load optional preferences file (Rel. 2 onwards)
        # Parameters in this file will overwrite (with constrain)
        # default values provided by FtG.
        loading = "reload" if reloading else "load"
        # restart from empty
        self.prefs = {}
        here = os.path.dirname(__file__)
        # I. "Developer" preferences PythonPlugins/followthegreens/followthegreens.prf
        filename = os.path.join(here, PREFERENCE_FILE_NAME)
        if os.path.exists(filename):
            with open(filename, "rb") as fp:
                try:
                    self.prefs = tomllib.load(fp)
                except:
                    logger.warning(f"preferences file {filename} not {loading}ed", exc_info=True)

            logger.info(f"developer preferences file {filename} {loading}ed")
            logger.debug(f"preferences: {self.prefs}")
        else:
            logger.debug("no developer preference")

        # II. "User" preferences output/preferences/followthegreens.prf
        if not self.prefs.get("DEVELOPER_PREFERENCE_ONLY", False):
            filename = os.path.join(".", "Output", "preferences", PREFERENCE_FILE_NAME)  # relative to X-Plane "rott/home" folder
            if os.path.exists(filename):
                with open(filename, "rb") as fp:
                    try:
                        prefs = tomllib.load(fp)
                        logger.info(f"preferences file {filename} {loading}ed")
                        if VERSION not in prefs:
                            logger.warning("preferences file contains no version information")
                        else:
                            logger.info(f"preferences file version {prefs.get(VERSION)}")
                        if len(self.prefs) > 0:
                            logger.warning("some user preferences may be overwritten by developer preferences")
                        if len(prefs) > 0:
                            # Order is important: We overwrite user preferences with developer preferences.
                            self.prefs = prefs | self.prefs
                        self.check_update_version(filename=filename, change=False)
                    except:
                        logger.warning(f"preferences file {filename} not {loading}ed", exc_info=True)
                # logger.debug(f"preferences: {self.prefs}")
            else:
                logger.debug(f"no preferences file {filename}")
                self.create_empty_prefs()
        else:
            logger.info("DEVELOPER_PREFERENCE_ONLY = true, user preferences ignored")

        logger.info(f"preferences: {self.prefs}")

        ll = get_global("LOGGING_LEVEL", self.prefs)
        if type(ll) is int:
            logger.debug(f"log level: current={logger.level}, requested={ll}")
            if logger.level != ll:
                logger.setLevel(ll)
                logger.log(ll, f"internal: debug level set to {ll}")
        else:
            logger.warning(f"invalid logging level {ll} ({type(ll)})")
        logger.info(f"LOGGING_LEVEL = {logger.level}")
        # logger.info("You can change the logging level in the preference file by setting a interger value like so: LOGGING_LEVEL = 10")

        try:
            logger.debug(f"internal:\n{ '\n'.join([f'{g}: {get_global(g, preferences=self.prefs)}' for g in INTERNAL_CONSTANTS]) }'\n=====")
        except:  # in case str(value) fails
            logger.debug("internal: some internals preference values don't print", exc_info=True)

    def create_empty_prefs(self):
        # Once, on first use, to help user
        filename = os.path.join(".", "Output", "preferences", PREFERENCE_FILE_NAME)  # relative to X-Plane "rott/home" folder
        if not os.path.exists(filename):
            with open(filename, "w") as fp:
                print(
                    f"""# Follow the greens Preference File
#
# Follow the greens is a XPPython3 plugin available
# in the PythonPlugins folder inside X-Plane plugin folder.
#
# See documentation at https://devleaks.github.io/followthegreens/.
#
# {PREFERENCE_FILE_NAME} (this file) is a TOML (https://toml.io/en/) formatted file.
# Please adhere to the TOML formatting/standard when adding preferences.
# For example, boolean values are true and false, lower case.
# If True or False is used, an error will be issued and the preference file ignored.
#
# Do not touch the following lines.
#
# Initially created version {__VERSION__} on {datetime.now(tz=timezone.utc)}.
#
VERSION = "{__VERSION__}"
#
#
# Lines that starts with # are comments.
# To set a preferred value, place the name of the preference = <value> on a new line.
# Example:
#LOGGING_LEVEL = 10
# Remove the # character from the above line to enable debugging information logging.
#
# Advanced: Lines/words between square brackets are called "tables" in TOML, like
#
#[Advanced]
#
# Sometimes, preferences need to be added under a [table] indication, like so:
#
#[Advanced]
#advanced_preference = false
#
#
# Taxi safely.
""",
                    file=fp,
                )
            logger.info(f"preference file {filename} created")

    def check_update_version(self, filename: str, change: bool = False):
        # Update version number in preference file if parameters still valid
        # and format is OK. This aims at auto-maintaining the preference file.
        # @todo: check parameters, if ok in new version.
        NO_VERSION = "none"
        v = self.prefs.get(VERSION, NO_VERSION)
        if v == __VERSION__:
            return
        logger.warning(f"preference file version {v} and current application version {__VERSION__} differ")
        if change:
            f = None
            with open(filename, "r") as fp:  # should replace literal...
                f = re.sub(r"^VERSION\s*=\s*\"([1-9]+\.[0-9]+\.[0-9]+)\"\s*$", f'{VERSION} = "{__VERSION__}"\n', fp.read(), flags=re.MULTILINE)
            if type(f) is str and f != "":
                with open(filename, "w") as fp:
                    print(f, file=fp)
                    if v == NO_VERSION:
                        print(f'\n{VERSION} = "{__VERSION__}"\n', file=fp)
                        logger.info(f"preference file added missing version {__VERSION__}")
                    logger.info(f"preference file updated to version {__VERSION__}")

        self.prefs[VERSION] = __VERSION__
        logger.debug(toml_dumps(self.prefs))
        # with open(filename, "w") as fp:
        #     print(toml_dumps(self.prefs))

    def start(self) -> int:
        # Toggles visibility of main window.
        # If it was simply closed for hiding, show it again as it was.
        # If it does not exist, creates it from start of process.
        # if self.status = ACTIVE:
        logger.debug(f"status: {self.status}, ui={self.ui.mainWindowExists()}")
        if self.ui.mainWindowExists():
            logger.debug(f"mainWindow exists, changing visibility {self.ui.isMainWindowVisible()}")
            self.ui.toggleVisibilityMainWindow()
            return 1

        # Info 1
        logger.info("starting..")
        self.inc("start")
        # BEGIN TEST : reloading preferences
        logger.debug("..reloading preferences..")
        self.init_preferences(reloading=True)
        logger.debug("..reloaded..")
        # END TEST
        mainWindow = self.getAirport()
        logger.debug("mainWindow created")
        if mainWindow and not xp.isWidgetVisible(mainWindow):
            xp.showWidget(mainWindow)
            logger.debug("mainWindow shown")
        self.status = FTG_STATUS.READY
        logger.info("..started.")
        return 1  # window displayed

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
        self.aircraft = Aircraft(prefs=self.prefs)

        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
        if pos is None:
            logger.debug("no aircraft position")
            return self.ui.sorry("We could not locate your aircraft.")

        if pos[0] == 0 and pos[1] == 0:
            logger.debug("no aircraft position")
            return self.ui.sorry("We could not locate your aircraft.")

        self.status = FTG_STATUS.AIRCRAFT
        self.inc(self.aircraft.icao)

        # Info 2
        logger.info(f"aircraft position ok: {pos}, heading {round(hdg, 1)}")
        airport = self.aircraft.airport(pos)
        if airport is None:
            logger.debug("no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logger.debug("no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        # Info 3
        logger.info(f"at {airport.name}")
        self.status = FTG_STATUS.AIRPORT
        return self.afterAirport(airport.navAidID)

    def afterAirport(self, airport):
        return self.getDestination(airport)

    def getDestination(self, airport):
        # Prompt for local destination at airport.
        # Either a runway for departure or a parking for arrival.
        if not self.airport or (self.airport.icao != airport):  # we may have changed airport since last call
            airport = Airport(icao=airport, prefs=self.prefs)
            # Info 4 to 9 in airport.prepare()
            status = airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning(f"airport not ready: {status[1]}")
                return self.ui.sorry(status[1])
            self.airport = airport
            self.inc(self.airport.icao)
        else:
            logger.debug(f"airport {self.airport.icao} already loaded")

        logger.info(f"airport {self.airport.icao} ready")

        # Info 10
        self.move = self.airport.guessMove(self.aircraft.position())
        return self.ui.promptForDestination()

    def newGreen(self, destination):
        # What is we had a green, and now we don't?!
        # so we first make sur we find a new green, and if we do, we cancel the previous one.
        self.inc("new_greens")
        return self.followTheGreen(destination, True)

    def followTheGreen(self, destination, newGreen: bool = False):
        # Destination is either
        #   the name of a runway for departure, or
        #   the name of a parking ramp for arrival.
        # We know where we are, we know where we want to go.
        # If we find a route, we light it.
        if destination not in self.airport.getDestinations(self.move):
            logger.debug(f"destination not valid {destination} for {self.move}")
            return self.ui.promptForDestination(f"Destination {destination} not valid for {self.move}")

        self.status = FTG_STATUS.DESTINATION

        # Info 11
        logger.info(f"destination {destination}")
        rerr, self.route = self.airport.mkRoute(self.aircraft, destination, self.move, get_global("RESPECT_CONSTRAINTS", preferences=self.prefs))

        if not rerr:
            logger.info(f"no route to destination {destination} (route  {self.route})")
            return self.ui.tryAgain(self.route)

        # Info 12
        logger.info(f"route to {destination}: {self.route}")

        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
        gsp = self.aircraft.speed()
        if pos is None or (pos[0] == 0 and pos[1] == 0):
            logger.debug("no aircraft position")
            return self.ui.sorry("We could not locate your aircraft.")

        if newGreen:  # We had a green, and we found a new one.
            # turn off previous lights
            self.terminate("new green requested")
            self.session = randint(1000, 9999)
            logger.info(f"Starting new FtG session for greener greens (session id = {self.session})")

        # logger.debug(f"got route: {route}.")
        self.destination = destination
        onRwy = False
        if self.move == MOVEMENT.ARRIVAL:
            onRwy, runway = self.airport.onRunway(pos, width=RUNWAY_BUFFER_WIDTH, heading=hdg)  # RUNWAY_BUFFER_WIDTH either side of runway, return [True,Runway()] or [False, None]

        self.status = FTG_STATUS.ROUTE

        self.lights = LightString(airport=self.airport, aircraft=self.aircraft, preferences=self.prefs)
        self.lights.populate(self.route, move=self.move, onRunway=onRwy)
        if len(self.lights.lights) == 0:
            logger.debug("no lights")
            return self.ui.sorry("We could not light a route to your destination.")
        self.inc("lights", qty=len(self.lights.lights))

        # Info 13
        self.lights.printSegments()

        self.segment = 0
        logger.info(f"current segment {self.segment + 1}/{self.lights.segments + 1}")
        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            return self.ui.sorry(ret[1])
        logger.debug(f"lights instanciated for segment {self.segment}")

        initbrgn, initdist, initdiff = self.lights.initial(pos, hdg)
        logger.debug(f"init ({initbrgn}, {initdist}, {initdiff})")

        self.status = FTG_STATUS.GREENS

        cursor = get_global("CURSOR", self.prefs)
        if type(cursor) is str and len(cursor) > 1:
            self.cursor = Cursor(cursor)

        logger.info(f"first light at {initdist} m, heading {initbrgn} DEG")
        self.flightLoop.startFlightLoop()
        self.status = FTG_STATUS.ACTIVE
        # Info 14
        logger.info("flightloop started")

        # Hint: distance and heading to first light
        intro = f"Follow the greens to {destination}"
        speak = f"Follow the greens to {phonetic(destination)}"
        intro_arr = []
        if SAY_ROUTE:
            rt = self.route.text()
            if len(rt) > 0:
                intro = intro + f" via taxiways {rt}"
                speak = speak + f" via taxiways {phonetic(rt)}"
            intro_arr = intro_arr + wrap(intro + ".", width=80)  # might be long
            speak = speak + "."
        if get_global("LEVEL4", self.prefs) > 0:
            intro_arr.append(f"Expect taxi ride of {round(self.route.dleft[0]/1000, 1)}km, about {round((self.route.tleft[0]+30)/60)} minutes.")
        if initdiff > 20 or initdist > 200:
            dist_str = " ".join(f"{int(initdist):d}")
            hdg_str = " ".join(f"{int(initbrgn):03d}")
            intro_arr.append(f"Start is at about {int(initdist):d} meters heading {int(initbrgn):03d}.")
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
        logger.info(f"segment {self.segment + 1}/{self.lights.segments + 1}")

        if self.segment > self.lights.segments:
            self.flightLoop.stopFlightLoop()
            self.lights.destroy()
            # Info 16.a
            logger.info("done")
            self.segment = 0  # reset
            return self.ui.bye()

        self.status = FTG_STATUS.GREENS
        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            self.terminate("issue with light segment illumination")
            return self.ui.sorry(ret[1])
        logger.debug(f"lights instanciated (segment={self.segment})")

        # re-authorize rabbit auto-tuning
        self.flightLoop.allowRabbitAutotune("next leg")
        self.status = FTG_STATUS.ACTIVE

        if self.move == MOVEMENT.DEPARTURE and self.segment == (self.lights.segments - 1):
            return self.ui.promptForDeparture()

        if self.move == MOVEMENT.DEPARTURE and self.segment == self.lights.segments:
            # Info 16.b
            logger.info("ready for take-off")
            self.segment = 0  # reset
            self.flightLoop.taxiEnd()
            return self.ui.bye()

        if self.move == MOVEMENT.ARRIVAL and self.segment == self.lights.segments:
            return self.ui.promptForParked()

        self.ui.canHide = True
        return self.ui.promptForClearance()

    def terminate(self, reason=""):
        # Abandon the FTG mission. Instruct subroutines to turn off FTG lights, remove them,
        # and restore the environment.
        self.status = FTG_STATUS.INACTIVE

        if self.flightLoop:
            self.flightLoop.stopFlightLoop()
            logger.info("flightloop stopped")

        if self.lights:
            self.lights.destroy()
            self.lights = None

        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()

        self.status = FTG_STATUS.TERMINATED

        self.inc("terminate")
        self.save_stats()

        # Info 16
        logger.info(f"terminated: {reason}")
        if reason == "new green requested":
            logger.info(f"FtG session ended at {datetime.now().astimezone().isoformat()} (session id = {self.session}) for greener greens")
        else:
            if self.cursor is not None:
                self.cursor.destroy()
                self.cursor = None
            logger.info(f"FtG session ended at {datetime.now().astimezone().isoformat()} (session id = {self.session})")
            logger.info("-=" * 50)
            logger.info("\n\n")
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
        self.inc("bookmark")

    def disable(self):
        # alias to cancel
        self.inc("disabled")
        return self.terminate("disabled")

    def stop(self):
        # alias to cancel
        self.inc("stopped")
        return self.terminate("stopped")
