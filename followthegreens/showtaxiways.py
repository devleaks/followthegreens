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
from .lights import LightString
from .globals import logger, NoError, FTG_STATUS


class ShowTaxiways(FollowTheGreens):

    def __init__(self, pi):
        FollowTheGreens.__init__(self, pi=pi)

    def afterAirport(self, airport):
        self.showTaxiways(airport)

    def showTaxiways(self, airport):
        if not self.airport:
            self.airport = Airport(airport)
            status = self.airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning(f"airport not ready: {status[1]}")
                self.ui2.createWindow(
                    report={
                        "text": [status[1]],
                        "error": "Airport not ready",
                        "cancel": True,
                    }
                )
                return
            self.inc("taxiways_" + self.airport.icao)
        else:
            # @todo: Should check that airport already loaded is current airport...
            logger.debug(f"airport {self.airport.icao} already loaded")

        logger.info(f"airport {self.airport.icao}  ready")
        self._status = FTG_STATUS.AIRPORT
        self.lights = LightString(airport=self.airport, aircraft=self.aircraft, ui=self.ui, preferences=self.prefs)
        self._status = FTG_STATUS.READY
        self.lights.showAll(self.airport)

        self.inc("show_taxiways")
        if len(self.lights.lights) == 0:
            logger.warning("no lights")
            self.ui2.createWindow(
                report={
                    "text": "We could not light taxiways",
                    "error": "No light",
                    "cancel": True,
                }
            )
            return

        self.inc("taxiway_lights", qty=len(self.lights.lights))
        self.lights.printSegments()
        self._status = FTG_STATUS.ACTIVE
        self.ui2.createWindow(
            report={
                "text": "All taxiways are lit. Press Continue to turn lights off.",
                "continue": True,
            }
        )

    def terminate(self, reason="unspecified"):
        if self.lights:
            self.lights.destroy()
            self.lights = None

        self._status = FTG_STATUS.INACTIVE
        self.ui2.deleteWindow()
        self._status = FTG_STATUS.TERMINATED
        self.inc("terminate_taxiways")
        self.save_stats()

        # Info 16
        logger.info(f"terminated, reason: {reason}.")
        return NoError("terminated")
