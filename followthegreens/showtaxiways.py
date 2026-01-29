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
try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .followthegreens import FollowTheGreens
from .airport import Airport
from .lightstring import LightString
from .globals import logger, FTG_STATUS


class ShowTaxiways(FollowTheGreens):

    def __init__(self, pi):
        FollowTheGreens.__init__(self, pi=pi)
        self._status = FTG_STATUS.INITIALIZED

    def afterAirport(self, airport):
        return self.showTaxiways(airport)

    def showTaxiways(self, airport):
        if not self.airport:
            self.airport = Airport(airport)
            status = self.airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning(f"airport not ready: {status[1]}")
                return self.ui.sorry(status[1])
            self.inc("taxiways_" + self.airport.icao)
        else:
            # @todo: Should check that airport already loaded is current airport...
            logger.debug(f"airport {self.airport.icao} already loaded")

        logger.info(f"airport {self.airport.icao}  ready")
        self._status = FTG_STATUS.AIRPORT
        self.lights = LightString(airport=self.airport, aircraft=self.aircraft, preferences=self.prefs)
        self._status = FTG_STATUS.READY
        self.lights.showAll(self.airport)

        self.inc("show_taxiways")
        if len(self.lights.lights) == 0:
            logger.warning("no lights")
            return self.ui.sorry("We could not light taxiways.")
        self.inc("taxiway_lights", qty=len(self.lights.lights))

        self.lights.printSegments()

        logger.info(f"should check menu item {self.pi.menuIdx_st}")
        # if self.pi is not None and self.pi.menuIdx_st is not None and self.pi.menuIdx_st >= 0:
        #     try:
        #         xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx_st, xp.Menu_Checked)
        #         logger.debug(f"menu checked ({self.pi.menuIdx_st})")
        #     except:
        #         logger.debug(
        #             f"menu not checked ({self.pi.menuIdx_st}, {xp.Menu_Unchecked})",
        #             exc_info=True,
        #         )
        # else:
        #     logger.debug(f"menu not checked ({self.pi.menuIdx_st})")

        self._status = FTG_STATUS.ACTIVE
        return self.ui.enjoy()
        # return self.ui.sorry("Follow the greens is not completed yet.")  # development

    def terminate(self, reason="unspecified"):
        if self.lights:
            self.lights.destroy()
            self.lights = None
            logger.info(f"should uncheck menu item {self.pi.menuIdx_st}")
            # if self.pi is not None and self.pi.menuIdx_st is not None and self.pi.menuIdx_st >= 0:
            #     try:
            #         xp.checkMenuItem(xp.findPluginsMenu(), self.pi.menuIdx_st, xp.Menu_Unchecked)
            #         logger.debug(f"menu unchecked ({self.pi.menuIdx_st})")
            #     except:
            #         logger.debug(
            #             f"menu not unchecked ({self.pi.menuIdx_st}, {xp.Menu_Unchecked})",
            #             exc_info=True,
            #         )
            # else:
            #     logger.debug(f"menu not unchecked ({self.pi.menuIdx_st})")

        self._status = FTG_STATUS.INACTIVE
        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()
            # self.ui = None
        self._status = FTG_STATUS.TERMINATED
        self.inc("terminate_taxiways")
        self.save_stats()

        # Info 16
        logger.info(f"terminated: reason {reason}.")
        return [True, ""]
