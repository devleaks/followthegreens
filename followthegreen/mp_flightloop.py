# X-Plane Interaction Class
# TO allow multiprocessing in the background using pipes
# @todo logging from xp.log to logging.debug
# @todo make it integrated from the nomenclature to work with Airport class

import xp
import logging

from XPLMProcessing import xplm_FlightLoop_Phase_AfterFlightModel


FLIGHT_LOOPS = -5.0      # How many flight loops we check the results


class MyLoadingFlightLoop:

    def __init__(self, airport, conn, process):
        self.mc = airport  # Reference to the caller
        # self.ftg = ftg     # Reference to the main caller
        # self.mc.icao = icao                       ## will be used to search
        # self.mc.name = ""                         ## will be filled from search
        # self.mc.atc_ground = None                 ## ignored
        # self.mc.altitude = 0  # ASL, in meters    ## will be filled from search
        # self.mc.loaded = False                    ## will be set from search if found
        # self.mc.scenery_pack = False              ## will be set from search if found
        # self.mc.lines = []                        ## will be filled from search
        # self.mc.graph = Graph()                   ## ignored
        # self.mc.runways = {}                      ## irnored
        # self.mc.holds = {}                        ## ignored
        # self.mc.ramps = {}                        ## ignored
        self.conn = conn     # connection from the process
        self.process = process
        self.fl = None
        self.flname = 'followthegreen load airport flight loop'
        self.loopRunning = False
        self.status = 'Not started'
        logging.debug("mp_flightloop::init: initialized")
        logging.debug("mp_flightloop::init: " + str(self.conn))
        logging.debug("mp_flightloop::init: process started, PID: " + str(self.process.pid))


    def startFlightLoop(self):
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
        if self.loopRunning:
            xp.destroyFlightLoop(self.fl)
            self.loopRunning = False
            logging.debug("mp_flightloop::stopFlightLoop: Flight loop stopped")
        else:
            logging.debug("mp_flightloop::stopFlightLoop: Flight loop not running")

    def myFLCB(self, elapsedSinceLastCall, elapsedTimeSinceLastFlightLoop, counter, inRefcon):
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
            self.mc
        return FLIGHT_LOOPS

