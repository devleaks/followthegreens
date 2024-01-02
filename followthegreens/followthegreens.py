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
from .flightloop import FlightLoop
from .globals import ARRIVAL, DEPARTURE
from .lightstring import LightString
from .ui import UIUtil

logger = logging.getLogger("follow_the_greens")


class FollowTheGreens:
    # Internal status
    STATUS = {"NEW": "NEW", "INITIALIZED": "INIT", "READY": "READY", "ACTIVE": "ACTIVE"}

    def __init__(self, pi):
        self.__status = FollowTheGreens.STATUS["NEW"]
        if pi is not None and pi.trace:
            logger.setLevel(logging.DEBUG)
        self.pi = pi
        self.airport = None
        self.aircraft = None
        self.lights = None
        self.segment = 0  # counter for green segments currently lit -0-----|-1-----|-2---------|-3---
        self.move = None  # departure or arrival, guessed first, can be changed by pilot.
        self.destination = None  # Handy
        self.ui = UIUtil(self)  # Where windows are built
        self.flightLoop = FlightLoop(self)  # where the magic is done

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
        return self.getDestination(airport.navAidID)

    def getDestination(self, airport):
        # Prompt for local destination at airport.
        # Either a runway for departure or a parking for arrival.
        if not self.airport or (self.airport.icao != airport):  # we may have changed airport since last call
            airport = Airport(airport)
            # Info 4 to 8 in airport.prepare()
            status = airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logger.warning("airport not ready: %s" % (status[1]))
                return self.ui.sorry(status[1])
            self.airport = airport
        else:
            logger.debug("airport already loaded")

        logger.debug("airport ready")
        self.move = self.airport.guessMove(self.aircraft.position())
        # Info 10
        logger.info("Guessing %s", self.move)

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
            return self.ui.promptForDestination("Destination %s not valid for %s." % (destination, self.move))

        # Info 11
        logger.info(f"Route to {destination}.")
        rerr, route = self.airport.mkRoute(self.aircraft, destination, self.move)

        if not rerr:
            logger.info(f"No route {route}")
            return self.ui.tryAgain(route)

        # Info 12
        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
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

        logger.debug("Got route: %s.", route)
        self.destination = destination
        onRwy = False
        if self.move == ARRIVAL:
            onRwy, runway = self.airport.onRunway(pos, 300)  # 150m either side of runway, return [True,Runway()] or [False, None]
        self.lights = LightString()
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
        self.__status = FollowTheGreens.STATUS["ACTIVE"]
        # Info 14
        logger.info("Flightloop started.")

        # Hint: distance and heading to first light
        if initdiff > 20 or initdist > 200:
            hdg_str = " ".join(f"{int(initbrgn):03d}")
            xp.speakString("Follow the greens. Taxiway is at about %d meters heading %s." % (initdist, hdg_str))
        else:
            xp.speakString("Follow the greens.")

        # self.segment = 0
        if self.lights.segments == 0:  # just one segment
            logger.debug(f"just one segment {self.move}")
            if self.move == ARRIVAL:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("just one segment on arrival")
                    return self.ui.promptForParked()
                if len(self.lights.stopbars) == 1:  # terminated with a stop bar, it is probably a departure...
                    logger.debug("1 segment with 1 stopbar on arrival?")
                    return self.ui.promptForClearance()
            if self.move == DEPARTURE:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logger.debug("1 segment with 0 stopbar on departure?")
                    return self.ui.promptForDeparture()

        return self.ui.promptForClearance()
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

        if self.move == DEPARTURE and self.segment == (self.lights.segments - 1):
            return self.ui.promptForDeparture()

        if self.move == DEPARTURE and self.segment == self.lights.segments:
            # Info 16.b
            logger.info("ready for take-off.")
            self.segment = 0  # reset
            return self.ui.bye()

        if self.move == ARRIVAL and self.segment == self.lights.segments:
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
        return [True, ""]

    def disable(self):
        # alias to cancel
        return self.cancel("disabled")

    def stop(self):
        # alias to cancel
        return self.cancel("stopped")
