# X-Plane Interaction Class
# We currently have two loops, one for rabbit, one to monitor plane position.
#
import logging

from XPLMProcessing import XPLMCreateFlightLoop, XPLMScheduleFlightLoop, XPLMDestroyFlightLoop
from XPLMProcessing import xplm_FlightLoop_Phase_AfterFlightModel
from .globals import PLANE_MONITOR_DURATION, DISTANCEBETWEENGREENLIGHTS, WARNINGDISTANCE


class FlightLoop:

    def __init__(self, ftg):
        self.ftg = ftg
        self.refrabbit = 'FollowTheGreen:rabbit'
        self.flrabbit = None
        self.rabbitRunning = False
        self.refplane = 'FollowTheGreen:plane'
        self.flplane = None
        self.planeRunning = False
        self.nextIter = PLANE_MONITOR_DURATION  # seconds
        self.lastLit = 0
        self.distance = 39940653000  # Earth circumference, in meter :-)
        self.diftingLimit = 5 * DISTANCEBETWEENGREENLIGHTS  # After that, we send a warning, and we may cancel FTG.


    def startFlightLoop(self):
        # @todo schedule/unschedule without destroying
        phase = xplm_FlightLoop_Phase_AfterFlightModel
        # @todo: make function to reset lastLit counter
        self.lastLit = 0
        if not self.rabbitRunning:
            params = [phase, self.rabbitFLCB, self.refrabbit]
            self.flrabbit = XPLMCreateFlightLoop(params)
            XPLMScheduleFlightLoop(self.flrabbit, 1.0, 1)
            self.rabbitRunning = True
            logging.debug("FlightLoop::startFlightLoop: rabbit started.")
        else:
            logging.debug("FlightLoop::startFlightLoop: rabbit running.")
        if not self.planeRunning:
            params = [phase, self.planeFLCB, self.refplane]
            self.flplane = XPLMCreateFlightLoop(params)
            XPLMScheduleFlightLoop(self.flplane, 10.0, 1)
            self.planeRunning = True
            logging.debug("FlightLoop::startFlightLoop: plane tracking started.")
        else:
            logging.debug("FlightLoop::startFlightLoop: plane tracked.")


    def stopFlightLoop(self):
        if self.rabbitRunning:
            XPLMDestroyFlightLoop(self.flrabbit)
            self.rabbitRunning = False
            logging.debug("FlightLoop::stopFlightLoop: rabbit stopped.")
        else:
            logging.debug("FlightLoop::stopFlightLoop: rabbit not running.")
        if self.planeRunning:
            XPLMDestroyFlightLoop(self.flplane)
            self.planeRunning = False
            logging.debug("FlightLoop::stopFlightLoop: plane tracking stopped.")
        else:
            logging.debug("FlightLoop::stopFlightLoop: plane not tracked.")


    def rabbitFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # show rabbit in front of plane.
        # plane is supposed to Follow the greens and it close to green light index self.lastLit.
        # We cannot use XP's counter because it does not increment by 1 just for us.
        return self.ftg.lights.rabbit(self.lastLit)


    def planeFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        # pylint: disable=unused-argument
        # monitor progress of plane on the green. Turns lights off as it does no longer needs them.
        # logging.debug('FlightLoop::flightLoopCallback %2f, %2f, %d', elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter)
        self.ftg.ui.hideMainWindowIfOk(elapsedSinceLastCall)

        pos = self.ftg.aircraft.position()
        if not pos or (pos[0] == 0 and pos[1] == 0):
            logging.debug("FlightLoop::planeFLCB: no position.")
            return self.nextIter

        nextStop, warn = self.ftg.lights.toNextStop(pos)
        if nextStop and warn < WARNINGDISTANCE:
            logging.debug("FlightLoop::planeFLCB: closing to stop.")
            if not self.ftg.ui.isMainWindowVisible():
                logging.debug("FlightLoop::planeFLCB: showing UI.")
                self.ftg.ui.showMainWindow(False)

        closestLight, distance = self.ftg.lights.closest(pos)
        if not closestLight:
            logging.debug("FlightLoop::planeFLCB: no close light.")
            return self.nextIter

        # logging.debug("FlightLoop::planeFLCB: closest %d %f", closestLight, distance)
        if closestLight > self.lastLit and distance < self.diftingLimit:  # Progress OK
            # logging.debug("FlightLoop::planeFLCB: moving %d %d", closestLight, self.lastLit)
            self.lastLit = closestLight
            self.distance = distance
            return self.nextIter

        if self.lastLit == closestLight and (abs(self.distance - distance) < DISTANCEBETWEENGREENLIGHTS):  # not moved enought, may even be stopped
            return self.nextIter

        # @todo
        # Need to send warning when pilot moves away from the green.

        self.distance = distance
        return self.nextIter