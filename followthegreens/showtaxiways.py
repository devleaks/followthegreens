# Follow The Green mission container Class
# Keeps all information handy. Dispatches intruction to do things.
#
# Cannot use Follow the green.
# We are sorry. We cannot provide Follow The Green service at this airport.
# Reasons:
# This airport does not have a routing network of taxiway.
#
# Can use Follow the green, but other issue:
# We are sorry. We cannot provide Follow The Green service now.
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

logging.basicConfig(level=logging.DEBUG)  # filename=('FTG_log.txt')


class ShowTaxiways:

    # Internal status
    STATUS = {
        "NEW": "NEW",
        "INITIALIZED": "INIT",
        "READY": "READY",
        "ACTIVE": "ACTIVE"
    }

    def __init__(self, pi):
        self.__status = ShowTaxiways.STATUS["NEW"]
        self.pi = pi
        self.airport = None
        self.aircraft = None
        self.lights = None
        self.ui = UIUtil(self)      # Where windows are built


    def start(self):
        logging.info("ShowTaxiways::status: %s, %s.", self.__status, self.ui.mainWindowExists())

        if self.ui.mainWindowExists():
            logging.debug("ShowTaxiways::start: mainWindow exists, changing visibility %s.", self.ui.isMainWindowVisible())
            self.ui.toggleVisibilityMainWindow()
            return 1

        # Info 1
        logging.info("ShowTaxiways::start: starting..")
        mainWindow = self.getAirport()
        logging.debug("ShowTaxiways::start: mainWindow created")
        if mainWindow and not xp.isWidgetVisible(mainWindow):
            xp.showWidget(mainWindow)
            logging.debug("ShowTaxiways::start: mainWindow shown")
        logging.info("ShowTaxiways::start: ..started.")
        return 1  # window displayed


    def getAirport(self):
        # Search for airport or prompt for one.
        # If airport is not equiped, we loop here until we get a suitable airport.
        # When one is given and satisfies the condition for FTG
        # we go to next step: Find the end point of follow the green.
        # @todo: We need to guess those from dataref
        # Note: Aircraft should be "created" outside of FollowTheGreen
        # and passed to start or getAirport. That way, we can instanciate
        # individual FollowTheGreen for numerous aircrafts.
        self.aircraft = Aircraft("PO-123")

        pos = self.aircraft.position()
        if pos is None:
            logging.debug("ShowTaxiways::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")

        if pos[0] == 0 and pos[1] == 0:
            logging.debug("ShowTaxiways::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")

        # Info 2
        logging.info("ShowTaxiways::getAirport: Plane postion %s" % pos)
        airport = self.aircraft.airport(pos)
        if airport is None:
            logging.debug("ShowTaxiways::getAirport: no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logging.debug("ShowTaxiways::getAirport: no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        # Info 3
        logging.info("ShowTaxiways::getAirport: At %s" % airport.name)
        return self.showTaxiways(airport.navAidID)


    def showTaxiways(self, airport):
        if not self.airport:
            self.airport = Airport(airport)
            status = self.airport.prepare_old()  # [ok, errmsg]
            if not status[0]:
                logging.debug("ShowTaxiways::showTaxiways: airport not ready: %s" % (status[1]))
                return self.ui.sorry(status[1])
        else:
            logging.debug("ShowTaxiways::showTaxiways: airport already loaded")

        logging.debug("ShowTaxiways::showTaxiways: airport ready")

        self.lights = LightString()
        self.lights.showAll(self.airport)
        if len(self.lights.lights) == 0:
            logging.debug("ShowTaxiways::showTaxiways: no lights")
            return self.ui.sorry("We could not light taxiways.")

        # Info 13
        logging.info("ShowTaxiways::showTaxiways: Added %d lights.", len(self.lights.lights))
        if self.pi is not None and self.pi.menuIdx is not None and self.pi.menuIdx >= 0:
            xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx, xp.Menu_Checked)
            logging.debug(f"ShowTaxiways::showTaxiways: menu checked ({self.pi.menuIdx})")
        else:
            logging.debug(f"ShowTaxiways::showTaxiways: menu not checked ({self.pi.menuIdx})")

        return self.ui.enjoy()


        return self.ui.enjoy()
        # return self.ui.sorry("Follow the green is not completed yet.")  # development


    def cancel(self, reason=""):
        if self.lights:
            self.lights.destroy()
            self.lights = None
            if self.pi is not None and self.pi.menuIdx is not None and self.pi.menuIdx >= 0:
                try:
                    xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx, xp.Menu_Unchecked)
                    logging.debug(f"ShowTaxiways::cancel: menu unchecked ({self.pi.menuIdx})")
                except:
                    logging.debug(f"ShowTaxiways::cancel: menu not unchecked ({self.pi.menuIdx}, {xp.Menu_Unchecked})", exc_info=True)

        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()
            # self.ui = None

        # Info 16
        logging.info("ShowTaxiways::cancel: cancelled: %s.", reason)
        return [True, ""]


    def disable(self):
        # alias to cancel
        return self.cancel("disabled")


    def stop(self):
        # alias to cancel
        return self.cancel("stopped")
