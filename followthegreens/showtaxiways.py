# Follow the greens mission container Class
# Keeps all information handy. Dispatches intruction to do things.
#
# Cannot use Follow the greens.
# We are sorry. We cannot provide Follow the greens service at this airport.
# Reasons:
# This airport does not have a routing network of taxiway.
#
# Can use Follow the greens, but other issue:
# We are sorry. We cannot provide Follow the greens service now.
# Reasons:
# You are too far from the taxiways.
# We could not find a suitable route to your destination.
#
import logging
import xp

from .aircraft import Aircraft
from .airport import Airport
from .lightstring import LightString
from .ui import UIUtil

logger = logging.getLogger(__name__)


class ShowTaxiways:
    # Internal status
    STATUS = {"NEW": "NEW", "INITIALIZED": "INIT", "READY": "READY", "ACTIVE": "ACTIVE"}

    def __init__(self, pi):
        self.__status = ShowTaxiways.STATUS["NEW"]
        self.pi = pi
        self.airport = None
        self.aircraft = None
        self.lights = None
        self.ui = UIUtil(self)  # Where windows are built

    def start(self):
        logger.info(f"status: {self.__status}, {self.ui.mainWindowExists()}.")

        if self.ui.mainWindowExists():
            logger.debug(f"mainWindow exists, changing visibility {self.ui.isMainWindowVisible()}.")
            self.ui.toggleVisibilityMainWindow()
            return 1

        # Info 1
        logger.info("starting..")
        mainWindow = self.getAirport()
        logger.debug("mainWindow created")
        if mainWindow and not xp.isWidgetVisible(mainWindow):
            xp.showWidget(mainWindow)
            logger.debug("mainWindow shown")
        logger.info("..started.")
        return 1  # window displayed

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
        logger.info("Plane postion %s" % pos)
        airport = self.aircraft.airport(pos)
        if airport is None:
            logger.debug("no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logger.debug("no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        # Info 3
        logger.info("At %s" % airport.name)
        return self.showTaxiways(airport.navAidID)

    def showTaxiways(self, airport):
        if not self.airport:
            self.airport = Airport(airport)
            status = self.airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.debug("airport not ready: %s" % (status[1]))
                return self.ui.sorry(status[1])
        else:
            logger.debug("airport already loaded")

        logger.debug("airport ready")

        self.lights = LightString()
        self.lights.showAll(self.airport)
        if len(self.lights.lights) == 0:
            logger.debug("no lights")
            return self.ui.sorry("We could not light taxiways.")

        # Info 13
        logger.info(f"Added {len(self.lights.lights)} lights.")

        # if self.pi is not None and self.pi.menuIdx is not None and self.pi.menuIdx >= 0:
        #     xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx, xp.Menu_Checked)
        #     logger.debug(f"menu checked ({self.pi.menuIdx})")
        # else:
        #     logger.debug(f"menu not checked ({self.pi.menuIdx})")

        return self.ui.enjoy()
        # return self.ui.sorry("Follow the greens is not completed yet.")  # development

    def cancel(self, reason="unspecified"):
        if self.lights:
            self.lights.destroy()
            self.lights = None
            # if self.pi is not None and self.pi.menuIdx is not None and self.pi.menuIdx >= 0:
            #     try:
            #         xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx, xp.Menu_Unchecked)
            #         logger.debug(f"menu unchecked ({self.pi.menuIdx})")
            #     except:
            #         logger.debug(f"menu not unchecked ({self.pi.menuIdx}, {xp.Menu_Unchecked})", exc_info=True)

        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()
            # self.ui = None

        # Info 16
        logger.info(f"cancelled: reason {reason}.")
        return [True, ""]

    def disable(self):
        # alias to cancel
        return self.cancel("disabled")

    def stop(self):
        # alias to cancel
        return self.cancel("stopped")
