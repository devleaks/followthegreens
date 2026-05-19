# Follow the greens XPPYthon3 Plugin Interface
#
#
import os
import re
import tomllib
import json
from random import randint
from datetime import datetime, timedelta, timezone
from textwrap import wrap
from pprint import pformat

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .version import __VERSION__
from .globals import logger, get_global, INTERNAL_CONSTANTS, FTG_STATUS, MOVEMENT, AMBIANT_RWY_LIGHT_VALUE, RABBIT_MODE, RUNWAY_BUFFER_WIDTH, SAY_ROUTE, DISTANCE_TO_RAMPS
from .aircraft import Aircraft
from .airport import Airport
from .flightloop import FlightLoop
from .lightstring import LightString
from .ui import UIUtil
from .ui2 import UIIM
from .nato import phonetic, toml_dumps

PREFERENCE_FILE_NAME = "followthegreens.prf"  # followthegreens.prf
STATS_FILE_NAME = "ftgstats.txt"
VERSION = "VERSION"


class FollowTheGreens:

    def __init__(self, pi):
        self._status = FTG_STATUS.NEW
        self.pi = pi
        self.alternate = False
        self.airport: Airport | None = None
        self.aircraft: Aircraft | None = None
        self.lights: LightString | None = None
        self.fmcar = None
        self.segment = 0  # counter for green segments currently lit -0-----|-1-----|-2---------|-3---
        self.move: MOVEMENT | None = None  # departure or arrival, guessed first, can be changed by pilot.
        self.destination = None  # Handy

        self.airport_light_level = xp.findDataRef(AMBIANT_RWY_LIGHT_VALUE)  # [off, lo, med, hi] = [0, 0.25, 0.5, 0.75, 1]
        self.zuluTime = xp.findDataRef("sim/time/zulu_time_sec")
        self.zuluHours = xp.findDataRef("sim/cockpit2/clock_timer/zulu_time_hours")

        self.localDay = xp.findDataRef("sim/time/local_date_days")
        self.localTime = xp.findDataRef("sim/time/local_time_sec")
        self.localHours = xp.findDataRef("sim/cockpit2/clock_timer/local_time_hours")
        self.session = None
        self.route = None
        self.stats = {}
        self.prefs = {}
        self.extconfig = {}
        self.ui = None
        # test IMGUI
        self.ui2 = UIIM()
        self._last_ui_shown = None
        self.flightLoop = None
        # frame rate estimates
        self.frp = xp.findDataRef("sim/time/framerate_period")
        self.fr = 1.0
        self.xp_log_dir = os.path.join(".", "Output", "caches", "followthegreens")  # relative to X-Plane "root/home" folder, needs to be created first
        logger.info(f"created {type(self).__name__} {__VERSION__} at {datetime.now().astimezone().isoformat()}")
        # logger.info(f"XPPython3 {xp.VERSION}, X-Plane {xp.getVersions()}")

    def __del__(self):
        # alias to cancel
        self.inc("delete")
        ret = self.terminate("delete")
        self.status = FTG_STATUS.DELETED
        logger.info(f"deleted {type(self).__name__} {__VERSION__} at {datetime.now().astimezone().isoformat()}")
        logger.info("<=" * 50)
        logger.info("\n\n")

    @property
    def is_holding(self) -> bool:
        return self.ui.waiting_for_clearance

    @property
    def status(self) -> FTG_STATUS:
        return self._status

    @status.setter
    def status(self, status: FTG_STATUS):
        if status != self._status:
            self._status = status
            self.inc(status.value)
            logger.info(f"{type(self).__name__} is now {status}")

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

    def init(self):
        self.stats = {}
        self.load_stats()
        self.prefs = {}
        self.init_preferences()
        self.ui = UIUtil(self)  # Where windows are built
        self.flightLoop = FlightLoop(self)  # where the magic is done
        # logger.info(f"initialized {type(self).__name__}")
        self.status = FTG_STATUS.INITIALIZED

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
                    with open(filename, "rb") as ferr:
                        logger.warning(f"file:\n{ferr.readlines()}\n")

            logger.info(f"developer preferences file {filename} {loading}ed")
            logger.debug(f"preferences:\n{pformat(self.prefs)}")
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
                        with open(filename, "rb") as ferr:
                            logger.warning(f"file:\n{ferr.readlines()}\n")
            else:
                logger.debug(f"no preferences file {filename}")
                self.create_empty_prefs()
        else:
            logger.info("DEVELOPER_PREFERENCE_ONLY = true, user preferences ignored")

        logger.info(f"preferences:\n{pformat(self.prefs)}")

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
            logger.debug(f"internal:\n{ '\n'.join([f'{g}: {get_global(g, preferences=self.prefs)}' for g in INTERNAL_CONSTANTS]) }\n=====")
        except:  # in case str(value) fails
            logger.debug("internal: some internals preference values don't print", exc_info=True)

    def init_external(self, reloading: bool = False) -> bool:
        # checks for external file, if found, build from there
        # return False if failed to build route or prompt to continue
        loading = "reload" if reloading else "load"
        here = os.path.dirname(__file__)
        filename = os.path.join("Output", "x-dispatch", "route.json")
        if self.prefs.get("DEVELOPER_PREFERENCE_ONLY", False):
            filename = os.path.join(here, "route.json")
        if os.path.exists(filename):
            with open(filename, "rb") as fp:
                try:
                    self.extconfig = json.load(fp)
                    logger.info(f"external configuration file {filename} {loading}ed")
                    logger.debug(f"external configuration file:\n{pformat(self.extconfig)}")
                except:
                    logger.warning(f"external configuration file {filename} not {loading}ed", exc_info=True)
                    with open(filename, "rb") as ferr:
                        logger.warning(f"file:\n{ferr.readlines()}\n")
        else:
            logger.debug(f"no external configuration file {filename}")
            return False

        destination = self.extconfig["dest"]
        logger.info(f"external configuration file {filename} read")
        logger.info(f"route exported with X-Dispatch {self.extconfig.get('x-dispatch-version')} on {self.extconfig.get('timestamp')}")
        logger.info(f"From {self.extconfig.get('apt')}/{self.extconfig.get('start')} to runway {destination}")
        logger.info(f"Route {" ".join(self.extconfig.get('taxiway_names'))}")
        # logger.info("external configuration not implemented yet, ignored")
        # return False

        # Checks for file date
        TOO_OLD = 1800  # secs
        dt = self.extconfig.get("timestamp")
        if dt is None:
            logger.info("external configuration file has no date, assuming ethernal validity")
        else:
            config_date = datetime.fromisoformat(dt)
            long_ago = (datetime.now(tz=timezone.utc) - config_date).total_seconds()
            logger.debug(f"external configuration file {long_ago}s ago ({config_date}, {datetime.now(tz=timezone.utc)})")
            if long_ago > TOO_OLD:  # 1800 secs = 1/2h
                logger.warning(f"external configuration file created too long ago (created at {dt}, more than {TOO_OLD}s ago")
                return False

        # 1. Create aircraft (+ set start position)
        self.aircraft = Aircraft(prefs=self.prefs)
        self.status = FTG_STATUS.AIRCRAFT
        self.inc(self.aircraft.icao)

        # 2. Create airport from apt.dat (+ set destination)
        self.airport = None
        pos = self.aircraft.position()
        airport_navaid = self.aircraft.airport(pos)
        if airport_navaid is None:
            logger.warning("cannot find airport")
            return False

        if airport_navaid.name == "NOT FOUND":
            logger.warning("no airport (not found)")
            return False

        current_airport = airport_navaid.navAidID

        airport_name = self.extconfig["apt"]
        if current_airport != airport_name:
            logger.info(f"not the same airport, external configuration file ignored ({current_airport} vs. {airport_name})")
            return False

        airport_data = Airport(icao=airport_name, prefs=self.prefs)
        apt_dat = self.extconfig["apt.dat"]
        status = airport_data.prepare(filename=apt_dat)  # [ok, errmsg]
        if not status[0]:
            logger.warning(f"airport not ready: {status[1]}")
            return False
        self.airport = airport_data
        if self.ui2 is not None:
            self.ui2.setAirport(self.airport)
        self.status = FTG_STATUS.AIRPORT

        # 2.1 Check runway
        if destination not in self.airport.getDestinations(move=MOVEMENT.DEPARTURE):
            logger.warning(f"destination runway {destination} not in airport list {self.airport.getDestinations(move=MOVEMENT.DEPARTURE)}")

        # 2.2 Check stand
        closest_stand = self.airport.findClosestRamp(pos)
        if closest_stand[1] < DISTANCE_TO_RAMPS:  # meters, we are close to a ramp.
            closest_stand_str = closest_stand[0] if type(closest_stand[0]) is str else ""
            stand = self.extconfig.get("start")
            if stand is not None and closest_stand_str != "" and closest_stand_str != stand:
                logger.warning(f"stand in external configuration file {stand} does not match stand closest to aircraft {closest_stand_str}")

        # 3. Start FtG (create lights, light them, etc.)
        self.move = MOVEMENT.DEPARTURE
        logger.info(f"external config going to {destination}")
        return self.followTheGreen(destination, external=True)

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
# Its file extension is .prf to conform to X-Plane usage.
# Please adhere to the TOML formatting/standard when adding preferences.
# For example, boolean values are true and false, lower case, not quoted.
# If True or False is used, an error will be issued and the whole preference file ignored.
# Please refer to the log file ftg_log.txt located in
#    <X-Plane Folder> -> Resources -> plugins -> PythonPlugins -> followthegreens
# It is a human readable plain text file.
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
#
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

    @property
    def thing(self) -> str:
        # f"{ftg.things}"
        return "car" if self.alternate else "greens"

    def rabbitMode(self, mode: RABBIT_MODE):
        self.flightLoop.manualRabbitMode(mode)

    def rabbitModeAuto(self):
        self.flightLoop.automaticRabbitMode()

    def newLocation(self) -> bool:
        # called when
        # XPLM_MSG_SCENERY_LOADED = 104
        # XPLM_MSG_AIRPORT_LOADED = 107
        # plugin message received
        if self.lights is not None:
            self.lights.destroy()
            self.lights = None
            logger.debug("light instances destroyed")
        return self.getAirport(after=False)

    def newAircraft(self) -> bool:
        # called when
        # XPLM_MSG_AIRPORT_LOADED = 107
        # plugin message received
        self.aircraft = Aircraft(prefs=self.prefs)
        self.status = FTG_STATUS.AIRCRAFT
        self.inc(self.aircraft.icao)
        return True

    def hideWindow(self, elapsedSinceLastCall):
        self.ui.hideMainWindowIfOk(elapsedSinceLastCall)
        if self.ui2 is not None:
            self.ui2.hideWindowIfTimedout(elapsedSinceLastCall)

    def start(self, alternate: bool = False) -> int:
        # Toggles visibility of main window.
        # If it was simply closed for hiding, show it again as it was.
        # If it does not exist, creates it from start of process.
        if self.status == FTG_STATUS.NEW:
            self.init()

        # if self.status = ACTIVE:

        logger.debug(f"current status: {self.status}, ui={self.ui.mainWindowExists()}, alt={self.alternate}")
        if self.ui.mainWindowExists():
            logger.debug(f"mainWindow exists, changing visibility {self.ui.isMainWindowVisible()}")
            # @todo? Widget was hidden, it is popped up again;
            # may be situation has changed, we should at least may be check
            # we still are at the same airport as before?
            # May be other checks depending on self.status?
            # May be session should reset when not gone through everything and still not running?
            if not self.ui.isMainWindowVisible():
                self._last_ui_shown = datetime.now()  # becomes visible aster next call
            self.ui.toggleVisibilityMainWindow()
            if self.ui2 is not None:
                self.ui2.toggleVisibility()
            return 1

        # there is no existing window, we create a new session
        if self.session is None:
            self.session = randint(1000, 9999)
        logger.info(
            "\n\n"
            + "-=" * 50
            + "\n"
            + " ".join(
                [
                    "When sending session for debugging purpose,",
                    "you can cut the file above the 'starting new green session'",
                    "and after 'green session ended' with matching session identifier",
                    f"(session id = {self.session})",
                ]
            )
            + "\n"
        )
        logger.info(f"starting new green session at {datetime.now().astimezone().isoformat()} (session id = {self.session})..")

        # Info 1
        # logger.info("starting..")
        self.alternate = alternate

        self.status = FTG_STATUS.START

        logger.debug("..reloading preferences..")
        self.init_preferences(reloading=True)
        logger.debug("..reloaded..")

        # test IMGUI
        if self.ui2 is not None:
            self.ui2.createWindow()

        mainWindow = self.init_external()
        if not mainWindow:
            mainWindow = self.getAirport()
        logger.debug("mainWindow created")
        if mainWindow and not xp.isWidgetVisible(mainWindow):
            xp.showWidget(mainWindow)
            self._last_ui_shown = datetime.now()
            logger.debug("mainWindow shown")
        self.status = FTG_STATUS.READY
        logger.info("..started.")
        return 1  # window displayed

    def getAirport(self, after: bool = True):
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
        if pos is None or (pos[0] == 0 and pos[1] == 0):
            logger.debug("no aircraft position")
            return self.ui.sorry("We could not locate your aircraft.")

        hdg = self.aircraft.heading()
        logger.info(f"aircraft position ok: {pos}, heading {round(hdg, 1)}")
        self.status = FTG_STATUS.AIRCRAFT
        self.inc(self.aircraft.icao)

        # Info 2
        airport = self.aircraft.airport(pos)
        if airport is None:
            logger.debug("no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logger.debug("no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        airport_name = airport.navAidID
        if not self.airport or (self.airport.icao != airport_name):  # we may have changed airport since last call
            airport_data = Airport(icao=airport_name, prefs=self.prefs)
            # Info 4 to 9 in airport.prepare()
            status = airport_data.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning(f"airport not ready: {status[1]}")
                return self.ui.promptForAirport()
            self.airport = airport_data
            if self.ui2 is not None:
                self.ui2.setAirport(airport=self.airport)
            self.inc(self.airport.icao)
        else:
            logger.debug(f"airport {self.airport.icao} already loaded")

        logger.info(f"airport {self.airport.icao} ready")
        # Info 3
        logger.info(f"at {airport.name}")
        self.status = FTG_STATUS.AIRPORT
        if after:
            return self.afterAirport(airport.navAidID)
        return True

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
                return self.ui.sorry(status[1])  # could loop on getAirport? return self.getAirport()
            self.airport = airport
            if self.ui2 is not None:
                self.ui2.setAirport(self.airport)
            self.inc(self.airport.icao)
        else:
            logger.debug(f"airport {self.airport.icao} already loaded")

        logger.info(f"airport {self.airport.icao} ready")

        # Info 10
        self.move = self.airport.guessMove(self.aircraft.position())
        return self.ui.promptForDestination(location=f"airport {self.airport.icao}")

    def newGreen(self, destination):
        # What is we had a green, and now we don't?!
        # so we first make sur we find a new green, and if we do, we cancel the previous one.
        self.inc("new_greens")
        return self.followTheGreen(destination=destination, newGreen=True)

    def followTheGreen(self, destination, newGreen: bool = False, external: bool = False):
        # Destination is either
        #   the name of a runway for departure, or
        #   the name of a parking ramp for arrival.
        # We know where we are, we know where we want to go.
        # If we find a route, we light it.
        if newGreen:
            logger.info("new green requested")

        if destination not in self.airport.getDestinations(move=self.move):
            logger.debug(f"destination not valid {destination} for {self.move}")
            return self.ui.promptForDestination(status=f"Destination {destination} not valid for {self.move}.")

        if self.ui2 is not None:
            self.ui2.deleteWindow()

        frp = xp.getDataf(self.frp)
        if frp != 0:
            self.fr = 1 / frp
            logger.info(f"estimated frame rate {round(self.fr, 1)} fps")

        # Info 11
        intro_arr = []
        rerr = False
        stand = self.extconfig.get("start", "the stand")
        if external:
            route_free = self.extconfig.get("route-geojson")
            if route_free is not None and len(route_free) > 0:
                logger.info("creating adhoc route from external source..")
                rerr, self.route = self.airport.mkAdhocRouteExternalDeparture(self.aircraft, stand, destination, route_free)
                if rerr:
                    intro_arr.append(f"X-Dispatch kindly provided sufficient information to follow the {self.thing}.")
                else:
                    logger.info("could not create adhoc route from external configuration file")
            if not rerr:
                route = self.extconfig.get("route")
                if route is not None and len(route) > 0:
                    logger.info("using route from external source..")
                    rerr, self.route = self.airport.mkRouteExternalDeparture(self.aircraft, stand, destination, route)
                    if rerr:
                        intro_arr.append(f"X-Dispatch kindly provided sufficient information to follow the {self.thing}.")
                    else:
                        logger.info("could not create route from external configuration file")
                # if no route provided or creation failed, we try through mkRoute()

        if not rerr:
            logger.info(f"trying route to destination {destination}..")
            rerr, self.route = self.airport.mkRoute(self.aircraft, destination, self.move, get_global("RESPECT_CONSTRAINTS", preferences=self.prefs))

        if not rerr:
            logger.info(f"..no route to destination {destination} (route {self.route})")
            return self.ui.tryAgain(self.route)

        # Info 12
        logger.info(f"..route to {destination}: {self.route}")
        self.destination = destination
        logger.info(f"destination {destination}")
        self.status = FTG_STATUS.DESTINATION

        if newGreen:  # We had a green, and we found a new one.
            # turn off previous lights
            self.terminate("new green requested")
            self.flightLoop.newRoute()
            self.session = randint(1000, 9999)
            logger.info(f"Starting new FtG session for greener greens (session id = {self.session})")

        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
        # gsp = self.aircraft.speed()

        # collect environmental data for this session
        # currently only reports it
        now = self.getSimulatorDatetime()
        day = self.aircraft.daylight(now=now)
        viz = self.aircraft.visibility()
        brt = self.aircraft.brightness()
        ahr = self.aircraft.aheadRangeBase()
        logger.info(f"environment at {now}: day={day}, visibility={round(viz, 0)}m, brt={brt}, vra={ahr}m")

        #
        self.airport.resetPreferences()  # necessary if a previous session requested a car

        # sets a reduced distance between lights
        has_light = not self.alternate
        new_fmcar = False
        if self.fmcar is None:
            self.fmcar = self.airport.fmcar(ftg=self)
            new_fmcar = True
        else:
            has_light = self.airport.ensureDev()  # may force both fmcar and lights on dev

        onRwy = False
        if self.move == MOVEMENT.ARRIVAL:
            onRwy, runway = self.airport.onRunway(pos, width=RUNWAY_BUFFER_WIDTH, heading=hdg)  # RUNWAY_BUFFER_WIDTH either side of runway, return [True,Runway()] or [False, None]

        self.lights = LightString(airport=self.airport, aircraft=self.aircraft, preferences=self.prefs, has_light=has_light)
        self.lights._days = self.dayOfYear()
        self.lights.populate(self.route, move=self.move, onRunway=onRwy)
        if len(self.lights.lights) == 0:
            logger.debug("no lights")
            return self.ui.sorry("We could not light a route to your destination.")
        self.inc("lights", qty=len(self.lights.lights))

        # Info 13
        self.lights.printSegments()
        self.status = FTG_STATUS.ROUTE

        if not new_fmcar and self.fmcar is not None:
            if self.fmcar is not None:
                try:
                    self.fmcar.changeRoute()
                except:
                    logger.error("change route", exc_info=True)

        self.segment = 0
        logger.info(f"current segment {self.segment + 1}/{self.lights.segments + 1}")
        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            return self.ui.sorry(ret[1])
        logger.debug(f"lights instanciated for segment {self.segment}")

        initbrgn, initdist, initdiff = self.lights.initial(pos, hdg)
        logger.debug(f"init ({initbrgn}, {initdist}, {initdiff})")

        self.status = FTG_STATUS.GREENS

        logger.info(f"first light at {initdist} m, heading {initbrgn} DEG")
        self.flightLoop.startFlightLoop()
        self.status = FTG_STATUS.ACTIVE
        # Info 14
        logger.info("flightloop started")

        # Hint: distance and heading to first light
        intro = f"Follow the {self.thing} to {destination}"
        speak = f"Follow the {self.thing} to {phonetic(destination)}"
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
            if self.alternate:
                intro_arr.append("Follow me car is in front of you.")
                speak = speak + " Follow me car is in front of you."
            else:
                intro_arr.append(f"Start is at about {int(initdist):d} meters heading {int(initbrgn):03d}.")
                speak = speak + f" Start is at about {phonetic(dist_str)} meters heading {phonetic(hdg_str)}."
        logger.debug(" ".join(intro_arr))
        xp.speakString(speak)

        if self.ui2 is not None:
            self.ui2.createWindow(
                report=intro_arr
                + [
                    "",
                    self.situation(),
                    f"{intro} until you encounter red stop lights across the taxiway.",
                    "At the stop lights, contact ATC for clearance. Press Clearance received when cleared.",
                    "",
                ]
            )

        # self.segment = 0
        if self.lights.segments == 0:  # just one segment
            logger.debug(f"just one segment {self.move}")
            if self.move == MOVEMENT.ARRIVAL:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("just one segment on arrival")
                    return self.ui.promptForParked(destination=destination)
                if len(self.lights.stopbars) == 1:  # terminated with a stop bar, it is probably a departure...
                    logger.debug("1 segment with 1 stopbar on arrival?")
                    return self.ui.promptForClearance(destination=self.destination)
            if self.move == MOVEMENT.DEPARTURE:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("1 segment with 0 stopbar on departure?")
                    return self.ui.promptForDeparture()

        return self.ui.promptForClearance(intro=intro_arr, destination=self.destination)
        # return self.ui.sorry("Follow the greens is not completed yet.")  # development

    def situation(self) -> str:
        s = "runway" if self.move == MOVEMENT.DEPARTURE else "ramp"
        return f"We are at {self.airport.icao}, taxiing to {s} {self.destination}."

    def nextLeg(self):
        # Called when cleared by TOWER
        self.segment += 1
        # Info 15
        logger.info(f"segment {self.segment + 1}/{self.lights.segments + 1}")

        if self.fmcar is not None:
            try:
                self.fmcar.canContinue()
            except:
                logger.error("can continue", exc_info=True)

        if self.segment > self.lights.segments:
            # Info 16.a
            self.status = FTG_STATUS.FINISHED
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
            self.status = FTG_STATUS.FINISHED
            logger.info("ready for take-off")
            self.segment = 0  # reset
            return self.ui.bye()

        if self.move == MOVEMENT.ARRIVAL and self.segment == self.lights.segments:
            return self.ui.promptForParked(destination=self.destination)

        self.ui.canHide = True
        return self.ui.promptForClearance(destination=self.destination)

    def terminate(self, reason=""):
        # Abandon the FTG mission. Instruct subroutines to turn off FTG lights, remove them,
        # and restore the environment.

        # test IMGUI
        if self.ui2 is not None:
            self.ui2.deleteWindow()

        if self.status in [FTG_STATUS.TERMINATED, FTG_STATUS.DELETED]:
            logger.warning(f"{type(self).__name__} already terminated")
            return [True, "already terminated"]

        self.status = FTG_STATUS.INACTIVE

        if self.flightLoop is not None:
            self.flightLoop.stopFlightLoop()
            logger.info("flightloop stopped")

        if self.lights is not None:
            self.lights.destroy()
            self.lights = None

        if self.ui is not None and self.ui.mainWindowExists():
            self.ui.destroyMainWindow()

        self.status = FTG_STATUS.TERMINATED
        self.save_stats()

        if reason == "delete":
            return [True, "delete"]

        # Info 16
        logger.info(f"terminated: {reason}")
        if reason == "new green requested":
            logger.info(f"green session ended at {datetime.now().astimezone().isoformat()} (session id = {self.session}) for greener greens")
            # do not delete fmcar
        else:
            if self.fmcar is not None:
                self.fmcar.destroy()
                self.fmcar = None
            logger.info(f"green session ended at {datetime.now().astimezone().isoformat()} (session id = {self.session})")
            logger.info("-=" * 50)
            logger.info("\n\n")
        self.session = None
        return [True, ""]

    def hourOfDay(self) -> float:
        return int(xp.getDataf(self.localTime) / 3600)  # seconds since midnight??

    def dayOfYear(self) -> int:
        return int(xp.getDatai(self.localDay))

    def getSimulatorDatetime(self, zulu: bool = True) -> datetime:
        s = 0
        t = timezone.utc
        if zulu:
            s = xp.getDataf(self.zuluTime)  # seconds in day
        else:
            s = xp.getDataf(self.localTime)
            zh = xp.getDatai(self.zuluHours)
            lh = xp.getDatai(self.localHours)
            dh = lh - zh
            t = timezone(timedelta(hours=dh), "xp-zone")
        d = xp.getDatai(self.localDay)  # day in year
        u = datetime.utcnow()  # year
        return datetime(year=u.year, month=1, day=1, tzinfo=t) + timedelta(days=d, seconds=s)

    def bookmark(self, message: str = ""):
        # @todo: fetch simulator date/time too
        z = self.getSimulatorDatetime()
        l = self.getSimulatorDatetime(zulu=False)
        logger.info(f"BOOKMARK {datetime.utcnow().isoformat()} {message}")
        logger.info(f"simulator zulu time is {z.replace(microsecond=0).isoformat()}, local time is {l.replace(microsecond=0).isoformat()}")
        self.inc("bookmark")

    def enable(self):
        if self.status == FTG_STATUS.NEW:
            self.init()
        self.status = FTG_STATUS.ENABLED
        return [True, ""]

    def disable(self):
        # alias to cancel
        self.status = FTG_STATUS.DISABLED
        return self.terminate("disabled")

    def stop(self):
        # alias to cancel
        self.inc("stopped")
        return self.terminate("stopped")

    def toExit(self):
        logger.error(f"""If error from FollowTheGreens persist, in X-Plane, select Plugin -> XPPython3 -> Reload scripts
to stop and reload python scripts and effectively stop FollowTheGreens (this will also stop other python scripts.).
FollowTheGreens will not restart unless you reactivate it.
Please send file {os.path.join(os.path.dirname(__file__), '..', 'ftg_log.txt')} along with log.txt and XPPython3Log.txt
to the author of the plugin to investigate the issue and fix it. Sorry for the inconvenience. Thank you.""")
