# X-Plane Interaction Class
# To allow multiprocessing in the background using pipes

import xp
import logging

from XPLMProcessing import xplm_FlightLoop_Phase_AfterFlightModel


FLIGHT_LOOPS = -5.0      # How many flight loops we check the results


class MyLoadingFlightLoop:
    """This flight loop is looking for messages coming from the pipe of the loader"""

    def __init__(self, airport, conn, process, ui):
        self.mc = airport # Reference to the caller
        self.ui = ui
        self.conn = conn # connection from the process
        self.process = process
        self.fl = None
        self.flname = 'followthegreen load airport flight loop'
        self.loopRunning = False
        self.status = 'Not started'
        logging.debug("mp_flightloop::init: initialized")
        logging.debug("mp_flightloop::init: " + str(self.conn))
        logging.debug("mp_flightloop::init: process started, PID: " + str(self.process.pid))


    def startFlightLoop(self):
        """Starts the loop in the AfterFlightModel sequence"""
        phase = xplm_FlightLoop_Phase_AfterFlightModel
        if not self.loopRunning:
            params = [phase, self.myFLCB, self.flname]
            self.fl = xp.createFlightLoop(params)
            xp.scheduleFlightLoop(self.fl, FLIGHT_LOOPS, 1)
            self.loopRunning = True
            logging.debug("mp_flightloop::startFlightLoop: Flight loop started")
            logging.debug("mp_flightloop::startFlightLoop: Process is alive " + str(self.process.is_alive()))
            logging.debug("mp_flightloop::startFlightLoop: conn " + str(self.conn.poll()))

    def stopFlightLoop(self):
        """Ends the loop when everything is loaded or the pipe is broken"""
        if self.loopRunning:
            xp.destroyFlightLoop(self.fl)
            self.loopRunning = False
            logging.debug("mp_flightloop::stopFlightLoop: Flight loop stopped")
        else:
            logging.debug("mp_flightloop::stopFlightLoop: Flight loop not running")

    def myFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
        """The loop it self, checks the pipe and if received data analyses the content"""
        logging.debug("mp_flightloop::FlightLoop: Flight loop - loop - Process is alive " + str(self.process.is_alive()))
        # logging.debug("mp_flightloop::FlightLoop: Flight loop - conn " + str(self.conn.poll()))
        try:
            if self.conn.poll():
                logging.debug("mp_flightloop::FlightLoop: Flight loop - pipe received message ")
                feedback = self.conn.recv()
                logging.debug("mp_flightloop::FlightLoop: Flight loop - message " + type(feedback).__name__)
                if type(feedback).__name__ == 'Feedback':
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message status " + feedback.status)
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message name " + feedback.name)
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message altitude " + str(feedback.altitude))
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message loaded " + str(feedback.loaded))
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message scenery_pack " + str(feedback.scenery_pack))
                    logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback message new_lines " + str(len(feedback.new_lines)))
                    self.status = feedback.status
                    self.mc.name = feedback.name
                    self.mc.altitude = feedback.altitude
                    self.mc.loaded = feedback.loaded
                    self.mc.scenery_pack = feedback.scenery_pack
                    if len(feedback.new_lines) > 0:
                        self.mc.lines = feedback.new_lines
                        logging.debug("mp_flightloop::FlightLoop: Flight loop - Feedback loaded lines " + str(len(self.mc.lines)))
        except IOError as e:
            logging.debug("mp_flightloop::myFLCB: Flight loop pipe closed or error " + str(e.errno))
            self.stopFlightLoop()
            self.mc.prepare()
            self.ui.ftg.getDestination_cont(self.mc)
            # self.ui.promptForDestination()
            self.ui.showMainWindow()
        return FLIGHT_LOOPS

