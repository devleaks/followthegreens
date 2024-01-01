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
from XPLMUtilities import XPLMSpeakString

from .aircraft import Aircraft
from .airport import Airport
from .flightloop import FlightLoop
from .globals import ARRIVAL, DEPARTURE
from .lightstring import LightString
from .ui import UIUtil

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - Follow The Green - %(levelname)s - %(message)s')  # filename=('FTG_log.txt')


class FollowTheGreen:

    # Internal status
    STATUS = {
        "NEW": "NEW",
        "INITIALIZED": "INIT",
        "READY": "READY",
        "ACTIVE": "ACTIVE"
    }

    def __init__(self, pi):
        self.__status = FollowTheGreen.STATUS["NEW"]
        self.pi = pi
        self.airport = None
        self.aircraft = None
        self.lights = None
        self.taxiway = {}
        self.segment = 0            # counter for green segments currently lit -0-----|-1-----|-2---------|-3---
        self.move = None            # departure or arrival, guessed first, can be changed by pilot.
        self.destination = None     # Handy
        self.ui = UIUtil(self)      # Where windows are built
        self.flightLoop = FlightLoop(self)  # where the magic is done


    def start(self):
        # Toggles visibility of main window.
        # If it was simply closed for hiding, show it again as it was.
        # If it does not exist, creates it from start of process.
        # if self.__status = FollowTheGreen.STATUS["ACTIVE"]:
        logging.info("FollowTheGreen::status: %s, %s.", self.__status, self.ui.mainWindowExists())
        if self.ui.mainWindowExists():
            logging.debug("FollowTheGreen::start: mainWindow exists, changing visibility %s.", self.ui.isMainWindowVisible())
            self.ui.toggleVisibilityMainWindow()
            return 1
        else:
            # Info 1
            logging.info("FollowTheGreen::start: starting..")
            mainWindow = self.getAirport()
            logging.debug("FollowTheGreen::start: mainWindow created")
            if mainWindow and not xp.isWidgetVisible(mainWindow):
                xp.showWidget(mainWindow)
                logging.debug("FollowTheGreen::start: mainWindow shown")
            logging.info("FollowTheGreen::start: ..started.")
            return 1  # window displayed
        return 0


    def getAirport(self):
        # Search for airport or prompt for one.
        # If airport is not equiped, we loop here until we get a suitable airport.
        # When one is given and satisfies the condition for FTG
        # we go to next step: Find the end point of follow the green.
        # @todo: We need to guess those from dataref
        # Note: Aircraft should be "created" outside of FollowTheGreen
        # and passed to start or getAirport. That way, we can instanciate
        # individual FollowTheGreen for numerous aircrafts.
        # DH: List of Aircrafts and icao categories available here:
        # https://www.faa.gov/airports/engineering/aircraft_char_database/
        # converted simply into a csv and using only the filds
        # ICAO code and AAC, implemented in aircraft module, simplified __init__ for
        # callsign only, rest comes from X-Plane dataref
        self.aircraft = Aircraft("PO-123")

        pos = self.aircraft.position()
        if pos is None:
            logging.debug("FollowTheGreen::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")

        if pos[0] == 0 and pos[1] == 0:
            logging.debug("FollowTheGreen::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")

        # Info 2
        logging.info("FollowTheGreen::getAirport: Plane postion %s" % pos)
        airport = self.aircraft.airport(pos)
        if airport is None:
            logging.debug("FollowTheGreen::getAirport: no airport")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        if airport.name == "NOT FOUND":
            logging.debug("FollowTheGreen::getAirport: no airport (not found)")
            return self.ui.promptForAirport()  # prompt for airport will continue with getDestination(airport)

        # Info 3
        logging.info("FollowTheGreen::getAirport: At %s" % airport.name)
        return self.getDestination(airport.navAidID)


    def getDestination(self, airport):
        # Prompt for local destination at airport.
        # Either a runway for departure or a parking for arrival.
        if not self.airport or (self.airport.icao != airport):  # we may have changed airport since last call
            self.airport = Airport(airport)
            # Info 4 to 8 in airport.prepare()
            status = self.airport.prepare_new(self.ui)  # [ok, errmsg] ==> loading in flight loop!
        else:
            return self.getDestination_cont(self.airport)
        return self.ui.promptForWindow()

    def getDestination_cont(self, airport):
        self.airport = airport
        logging.debug("FollowTheGreen::getDestination: airport ready")
        self.move = self.airport.guessMove(self.aircraft.position())
        # Info 10
        logging.info("FollowTheGreen::getDestination: Guessing %s", self.move)

        return self.ui.promptForDestination()

    def getDestination_old(self, airport):
        # Prompt for local destination at airport.
        # Either a runway for departure or a parking for arrival.
        if not self.airport or (self.airport.icao != airport):  # we may have changed airport since last call
            airport = Airport(airport)
            # Info 4 to 8 in airport.prepare()
            status = airport.prepare()  # [ok, errmsg]
            if not status[0]:
                logging.warn("FollowTheGreen::getDestination: airport not ready: %s" % (status[1]))
                return self.ui.sorry(status[1])
            self.airport = airport
        else:
            logging.debug("FollowTheGreen::getDestination: airport already loaded")

        logging.debug("FollowTheGreen::getDestination: airport ready")
        self.move = self.airport.guessMove(self.aircraft.position())
        # Info 10
        logging.info("FollowTheGreen::getDestination: Guessing %s", self.move)

        return self.ui.promptForDestination()


    def newGreen(self, destination):
        # What is we had a green, and now we don't?!
        # so we first make sur we find a new green, and if we do, we cancel the previous one.
        return self.followTheGreen(destination, True)


    def printTaxiInstructions(self, route):
        """Assuming a route has been found
        first only for debugging the Taxiway in clear letters"""
        # Example Cologne if you come from W and need to go to 24 you will taxi via
        # T D A A3 and D
        # so, D will be in 2 times.
        graph = route.graph
        currVertex = graph.get_vertex(route.route[0])
        stopVertexes = []
        logging.debug("FollowTheGreen::printTaxiInstructions: Stoppbars %s", len(self.lights.stopbars))
        # if len(self.lights.stopbars) > 0:
        #     for stopVertex in self.lights.stopbars:
        #         logging.debug("FollowTheGreen::printTaxiInstructions: Stoppbar at position %s", vars(stopVertex))
        #         # stopVertexes.add(stopVertex["position"])
        taxiway = {}
        key = 1
        for i in range(1, len(route.route)):
            nextVertex = graph.get_vertex(route.route[i])
            thisEdge = graph.get_edge(currVertex.id, nextVertex.id)
            if nextVertex in stopVertexes:
                key += 1
                taxiway[key] = [thisEdge.name, currVertex.id, nextVertex.id, ""]
            if "taxiway" in thisEdge.usage:
                taxiway_type = thisEdge.usage.removeprefix("taxiway_")
                if len(taxiway) > 0:
                    # logging.debug("FollowTheGreen::printTaxiInstructions: Key: %s", taxiway[key])
                    if thisEdge.name != taxiway[key][0]:
                        key += 1
                        taxiway[key] = [thisEdge.name, currVertex.id, nextVertex.id, taxiway_type]
                    else:
                        taxiway[key] = [thisEdge.name, taxiway[key][1], nextVertex.id, taxiway_type]
                else:
                    taxiway[key] = [thisEdge.name, currVertex.id, nextVertex.id, taxiway_type]
                    # logging.debug("FollowTheGreen::printTaxiInstructions: Taxiway %s", taxiway)
                    # logging.debug("FollowTheGreen::printTaxiInstructions: Taxiway 1st %s", taxiway[1][0])
            currVertex = nextVertex
        if len(taxiway) > 0:
            logging.debug("FollowTheGreen::printTaxiInstructions: Taxiway %s", taxiway)


    def followTheGreen(self, destination, newGreen=False):
        # Destination is either
        #   the name of a runway for departure, or
        #   the name of a parking ramp for arrival.
        # We know where we are, we know where we want to go.
        # If we find a route, we light it.
        if destination not in self.airport.getDestinations(self.move):
            logging.debug("FollowTheGreen::followTheGreen: destination not valid %s for %s", destination, self.move)
            return self.ui.promptForDestination("Destination %s not valid for %s." % (destination, self.move))

        # Info 11
        logging.info("FollowTheGreen::followTheGreen: Route to %s.", destination)
        rerr, route = self.airport.mkRoute(self.aircraft, destination, self.move)

        if not rerr:
            logging.info("FollowTheGreen::getDestination: No route %s", route)
            return self.ui.tryAgain(route)


        # Info 12
        pos = self.aircraft.position()
        hdg = self.aircraft.heading()
        if pos is None:
            logging.debug("FollowTheGreen::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")
        if pos[0] == 0 and pos[1] == 0:
            logging.debug("FollowTheGreen::getAirport: no plane position")
            return self.ui.sorry("We could not locate your plane.")

        if newGreen:  # We had a green, and we found a new one.
            # turn off previous lights
            self.cancel("new green requested")
            # now create new ones

        logging.info("FollowTheGreen::followTheGreen: Got route: %s.", route)
        self.destination = destination
        onRwy = False
        if self.move == ARRIVAL:
            onRwy, runway = self.airport.onRunway(pos, 300)  # 150m either side of runway, return [True,Runway()] or [False, None]
        self.lights = LightString()
        self.lights.populate(route, onRwy)
        if len(self.lights.lights) == 0:
            logging.debug("FollowTheGreen::getDestination: no lights")
            return self.ui.sorry("We could not light a route to your destination.")

        # Info 13
        logging.info("FollowTheGreen::followTheGreen: Added %d lights, %d segments, %s stopbars.", len(self.lights.lights), self.lights.segments + 1, len(self.lights.stopbars))
        self.segment = 0
        logging.info("FollowTheGreen::followTheGreen: Segment %d/%d.", self.segment + 1, self.lights.segments + 1)
        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            return self.ui.sorry(ret[1])
        logging.debug("FollowTheGreen::followTheGreen: lights instanciated for segment %d.", self.segment)

        initbrgn, initdist, initdiff = self.lights.initial(pos, hdg)
        logging.debug("FollowTheGreen::followTheGreen: init (%d, %d, %d).", initbrgn, initdist, initdiff)

        logging.info("FollowTheGreen::followTheGreen: first light at %d m, heading %d DEG.", initdist, initbrgn)
        self.flightLoop.startFlightLoop()
        self.__status = FollowTheGreen.STATUS["ACTIVE"]
        # Info 14
        logging.info("FollowTheGreen::followTheGreen: Flightloop started.")

        self.printTaxiInstructions(route)  # DH - Test

        # Hint: distance and heading to first light
        if initdiff > 20 or initdist > 200:
            XPLMSpeakString("Follow the green. Taxiway is at about %d meters heading %d." % (initdist, initbrgn))
        else:
            XPLMSpeakString("Follow the green.")

        # self.segment = 0
        if self.lights.segments == 0:  # just one segment
            logging.debug("FollowTheGreen::followTheGreen: just one segment %s", self.move)
            if self.move == ARRIVAL:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logging.debug("FollowTheGreen::followTheGreen: just one segment on arrival")
                    return self.ui.promptForParked()
                if len(self.lights.stopbars) == 1:  # terminated with a stop bar, it is probably a departure...
                    logging.debug("FollowTheGreen::followTheGreen: 1 segment with 1 stopbar on arrival?")
                    return self.ui.promptForClearance()
            if self.move == DEPARTURE:
                if len(self.lights.stopbars) == 0:  # not terminated by a stop bar, it is probably an arrival...
                    logging.debug("FollowTheGreen::followTheGreen: 1 segment with 0 stopbar on departure?")
                    return self.ui.promptForDeparture()

        return self.ui.promptForClearance()
        # return self.ui.sorry("Follow the green is not completed yet.")  # development


    def nextLeg(self):
        # Called when cleared by TOWER
        self.segment += 1
        # Info 15
        logging.info("FollowTheGreen::nextLeg: Segment %d/%d.", self.segment + 1, self.lights.segments + 1)

        if self.segment > self.lights.segments:
            self.flightLoop.stopFlightLoop()
            self.lights.destroy()
            # Info 16.a
            logging.info("FollowTheGreen::nextLeg: done.")
            self.segment = 0  # reset
            return self.ui.bye()

        ret = self.lights.illuminateSegment(self.segment)
        if not ret[0]:
            self.cancel()
            return self.ui.sorry(ret[1])
        logging.debug("FollowTheGreen::followTheGreen: lights instanciated (%d).", self.segment)

        if self.move == DEPARTURE and self.segment == (self.lights.segments - 1):
            return self.ui.promptForDeparture()

        if self.move == DEPARTURE and self.segment == self.lights.segments:
            # Info 16.b
            logging.info("FollowTheGreen::nextLeg: ready for take-off.")
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
            logging.info("FollowTheGreen::cancel: Flightloop stopped.")

        if self.lights:
            self.lights.destroy()
            self.lights = None

        if self.ui.mainWindowExists():
            self.ui.destroyMainWindow()

        # Info 16
        logging.info("FollowTheGreen::cancel: cancelled: %s.", reason)
        return [True, ""]


    def disable(self):
        # alias to cancel
        return self.cancel("disabled")


    def stop(self):
        # alias to cancel
        return self.cancel("stopped")
