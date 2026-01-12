# Follow the greens XP Python3 Plugin Interface
#
# See README file in followhtegreens folder.
# Enjoy.
#
#
from traceback import print_exc
from typing import Any

import xp

from followthegreens import __VERSION__, __NAME__, __SIGNATURE__, __DESCRIPTION__
from followthegreens import (
    FollowTheGreens,
    ShowTaxiways,
    RABBIT_MODE,
    SHOW_TRACE,
    FTG_CANCEL_COMMAND,
    FTG_CANCEL_COMMAND_DESC,
    FTG_OK_COMMAND,
    FTG_CLEARANCE_COMMAND,
    FTG_CLEARANCE_COMMAND_DESC,
    FTG_IS_RUNNING,
    FTG_OK_COMMAND_DESC,
    FTG_SPEED_COMMAND,
    FTG_SPEED_COMMAND_DESC,
    FTG_COMMAND,
    FTG_COMMAND_DESC,
    FTG_BOOKMARK_COMMAND,
    FTG_BOOKMARK_COMMAND_DESC,
    FTG_MENU,
    STW_COMMAND,
    STW_COMMAND_DESC,
    STW_MENU,
)


class PythonInterface:

    def __init__(self):
        self.Name = __NAME__
        self.Sig = __SIGNATURE__
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" {__VERSION__}"

        self.trace = SHOW_TRACE  # produces extra debugging in XPPython3.log for this class

        self.followTheGreens = None
        self.enabled = False

        self.isRunningRef = None

        # 1. Follow The Greens
        self.menuIdx = None
        self.CmdRefs = {}
        self.followTheGreensCmdRef = None
        self.clearanceCmdRef = None
        self.cancelCmdRef = None
        self.okCmdRef = None

        # 2. Show Taxiways
        self.menuIdx_st = None
        self.showTaxiways = None
        self.showTaxiwaysCmdRef = None
        self.rabbitModeCmdRefs = {}

        self.commands = {  # {cmd: desc, callback}
            FTG_COMMAND: [FTG_COMMAND_DESC, self.followTheGreensCmd],
            FTG_CLEARANCE_COMMAND: [
                FTG_CLEARANCE_COMMAND_DESC,
                self.clearanceCmd,
            ],
            FTG_CANCEL_COMMAND: [FTG_CANCEL_COMMAND_DESC, self.cancelCmd],
            FTG_OK_COMMAND: [FTG_OK_COMMAND_DESC, self.okCmd],
            FTG_BOOKMARK_COMMAND: [FTG_BOOKMARK_COMMAND_DESC, self.bookmarkCmd],
            STW_COMMAND: [STW_COMMAND_DESC, self.showTaxiwaysCmd],
        }
        self.commands = self.commands | {
            FTG_SPEED_COMMAND
            + mode: [
                FTG_SPEED_COMMAND_DESC + mode,
                getattr(self, "rabbitMode" + mode.title()),
            ]
            for mode in RABBIT_MODE
        }

    def debug(self, message, force: bool = False):
        if self.trace or force:
            print(self.Info, message)

    # Plugin Interface
    def XPluginStart(self):
        self.debug("XPluginStart: starting..", force=True)

        for cmd, what in self.commands.items():
            self.CmdRefs[cmd] = xp.createCommand(cmd, what[0])
            if self.CmdRefs[cmd] is not None:
                xp.registerCommandHandler(self.CmdRefs[cmd], what[1], 1, None)
                self.debug(f"XPluginStart: {cmd} command registered")
            else:
                self.debug(f"XPluginStart: {cmd} not registered")

        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), FTG_MENU, self.CmdRefs[FTG_COMMAND])
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            self.debug("XPluginStart: menu not added")
        else:
            self.debug(f"XPluginStart: menu item «{FTG_MENU}» added (index {self.menuIdx})")

        if STW_MENU is not None:
            self.menuIdx_st = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), STW_MENU, self.CmdRefs[STW_COMMAND])
            if self.menuIdx_st is None or (self.menuIdx_st is not None and self.menuIdx_st < 0):
                self.debug("XPluginStart: Show Taxiways menu not added")
            else:
                self.debug(f"XPluginStart: menu item «{STW_MENU}» added (index={self.menuIdx_st})")

        self.isRunningRef = xp.registerDataAccessor(
            FTG_IS_RUNNING,
            xp.Type_Int,  # The types we support
            0,  # Read-Only
            self.getRunningStatusCallback,
            0,  # Accessors for ints, read-only, no write.
            0,
            0,  # No accessors for floats
            0,
            0,  # No accessors for doubles
            0,
            0,  # No accessors for int arrays
            0,
            0,  # No accessors for float arrays
            0,
            0,  # No accessors for raw data
            0,
            0,
        )  # Refcons not used
        self.debug("XPluginStart: runnig data accessor installed")

        self.debug("XPluginStart: ..started", force=True)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        self.debug("XPluginStop: stopping..", force=True)

        for k, v in self.CmdRefs.items():
            if v is not None:  # FTG_COMMAND
                xp.unregisterCommandHandler(v, self.commands[k][1], 1, None)
                self.debug(f"XPluginStop: {k} command unregistered")
            else:
                self.debug(f"XPluginStop: {k} command not unregistered")

        if STW_MENU is not None:
            oldidx = self.menuIdx_st
            if self.menuIdx_st is not None and self.menuIdx_st >= 0:
                xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx_st)
                self.menuIdx_st = None
                self.debug(f"XPluginStop: menu item «{STW_MENU}» removed (index was {oldidx})")
            else:
                self.debug(f"XPluginStop: menu item «{STW_MENU}» not removed (index {oldidx})")

            if self.showTaxiways:
                try:
                    self.showTaxiways.stop()
                    self.showTaxiways = None
                    self.debug("XPluginStop: ShowTaxiways stopped")
                except:
                    self.debug("XPluginStop: exception", force=True)
                    print_exc()

        # Follow the Greens
        oldidx = self.menuIdx
        if self.menuIdx is not None and self.menuIdx >= 0:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            self.debug(f"XPluginStop: menu item «{FTG_MENU}» removed (index was {oldidx})")
        else:
            self.debug(f"XPluginStop: menu item «{FTG_MENU}» not removed (index {oldidx})")

        if self.isRunningRef is not None:  # and self.isRunningRef > 0?
            xp.unregisterDataAccessor(self.isRunningRef)
            self.isRunningRef = None
            self.debug("XPluginStop: data accessor unregistered")
        else:
            self.debug("XPluginStop: data accessor not unregistered")

        if self.followTheGreens:
            try:
                self.followTheGreens.stop()
                self.followTheGreens = None
                self.debug("XPluginStop: FollowTheGreens stopped")
            except:
                self.debug("XPluginStop: exception", force=True)
                print_exc()

        self.debug("XPluginStop: ..stopped", force=True)
        return None

    def XPluginEnable(self):
        self.debug("XPluginEnable: enabling..", force=True)

        try:
            self.followTheGreens = FollowTheGreens(self)

            if self.isRunningRef is not None:
                for sig in (
                    "com.leecbaker.datareftool",
                    "xplanesdk.examples.DataRefEditor",
                ):
                    dre = xp.findPluginBySignature(sig)
                    if dre != xp.NO_PLUGIN_ID:
                        xp.sendMessageToPlugin(dre, 0x01000000, FTG_IS_RUNNING)
                        self.debug(f"XPluginEnable: data accessor registered with {sig}")
                    else:
                        self.debug(f"XPluginEnable: plugin {sig} not found")
            else:
                self.debug("XPluginEnable: no data accessor")

            self.debug("XPluginEnable: FollowTheGreens created")
        except:
            self.debug("XPluginEnable: exception", force=True)
            print_exc()

        if STW_MENU is not None:
            try:
                self.showTaxiways = ShowTaxiways(self)
                self.debug("XPluginEnable: ShowTaxiways created")
                self.enabled = True
                self.debug("XPluginEnable: ..enabled", force=True)
                return 1
            except:
                self.debug("XPluginEnable: exception", force=True)
                print_exc()
        else:
            self.enabled = True
            self.debug("XPluginEnable: ..enabled", force=True)
            return 1

        self.enabled = False
        self.debug("XPluginEnable: ..not enabled", force=True)
        return 0

    def XPluginDisable(self):
        self.debug("XPluginDisable: disabling..")

        # 1. Follow The Greens
        try:
            if self.enabled and self.followTheGreens:
                self.followTheGreens.disable()
                self.followTheGreens = None
            self.debug("XPluginDisable: FollowTheGreens disabled")
        except:
            self.debug("XPluginDisable: exception", force=True)
            print_exc()

        # 2. Show Taxiways
        try:
            if self.enabled and self.showTaxiways:
                self.showTaxiways.disable()
                self.showTaxiways = None

            self.debug("XPluginDisable: ShowTaxiways disabled")
            self.enabled = False
            self.debug("XPluginDisable: ..disabled")
            return None
        except:
            self.debug("XPluginDisable: exception")
            print_exc()

        self.enabled = False
        self.debug("XPluginDisable: ..disabled with exception")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        # Should may be handle change of location/airport?
        pass

    # Commands
    def clearanceCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("clearanceCmd: not enabled", force=True)
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("clearanceCmd: available.")
            try:
                self.followTheGreens.ui.clearanceReceived()
                self.debug("clearanceCmd: executed.")
                return 1
            except:
                self.debug("clearanceCmd: exception", force=True)
                print_exc()
        elif not self.followTheGreens:
            self.debug("clearanceCmd: no FollowTheGreens running", force=True)

        return 0

    def cancelCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("cancelCmd: not enabled", force=True)
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("cancelCmd: available")
            try:
                self.followTheGreens.ui.cancelReceived("cancel command received")
                self.debug("cancelCmd: executed")
                return 1
            except:
                self.debug("cancelCmd: exception", force=True)
                print_exc()
        elif not self.followTheGreens:
            self.debug("cancelCmd: no FollowTheGreens running.")

        return 0

    def okCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("okCmd: not enabled.")
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("okCmd: available.")
            try:
                self.followTheGreens.ui.cancelReceived("ok command received")
                self.debug("okCmd: executed.")
                return 1
            except:
                self.debug("okCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            self.debug("okCmd: no FollowTheGreens running", force=True)

        return 0

    def bookmarkCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("bookmarkCmd: not enabled.")
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("bookmarkCmd: available.")
            try:
                self.followTheGreens.bookmark()
                self.debug("bookmarkCmd: executed.")
                return 1
            except:
                self.debug("bookmarkCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            self.debug("bookmarkCmd: no FollowTheGreens running", force=True)

        return 0

    def followTheGreensCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("followTheGreensCmd: not enabled", force=True)
            return 0

        if not self.followTheGreens:
            try:
                self.followTheGreens = FollowTheGreens(self)
                self.debug("followTheGreensCmd: created.")
            except:
                self.debug("followTheGreensCmd: exception at creation", force=True)
                print_exc()
                return 0

        if self.followTheGreens and phase == 0:
            self.debug("followTheGreensCmd: available.")
            try:
                self.followTheGreens.start()
                self.debug("followTheGreensCmd: started.")
                return 1
            except:
                self.debug("followTheGreensCmd: exception", force=True)
                print_exc()
                return 0
        elif not self.followTheGreens:
            self.debug(
                "followTheGreensCmd: Error: could not create FollowTheGreens.",
                force=True,
            )

        return 0

    def showTaxiwaysCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("showTaxiwaysCmd: not enabled", force=True)
            return 0

        if not self.showTaxiways:
            try:
                self.showTaxiways = ShowTaxiways(self)
                self.debug("showTaxiwaysCmd: created.")
            except:
                self.debug("showTaxiwaysCmd: exception at creation", force=True)
                print_exc()
                return 0

        if self.showTaxiways is not None and phase == 0:
            self.debug("showTaxiwaysCmd: available.")

            if self.showTaxiways.ui.mainWindowExists():  # already running, we stop it...
                try:
                    self.showTaxiways.cancel()
                    self.debug("showTaxiwaysCmd: ended.")
                    return 1
                except:
                    self.debug("showTaxiwaysCmd: exception", force=True)
                    print_exc()
                return 0

            try:
                self.showTaxiways.start()
                self.debug("showTaxiwaysCmd: started.")
                return 1
            except:
                self.debug("showTaxiwaysCmd: exception", force=True)
                print_exc()
        elif not self.showTaxiways:
            self.debug("showTaxiwaysCmd: Error: could not create ShowTaxiways.")

        return 0

    def rabbitModeSlowest(self, commandRef, phase, refCon):
        return self.rabbitMode(commandRef=commandRef, phase=phase, refCon=refCon, mode=RABBIT_MODE.SLOWEST)

    def rabbitModeSlower(self, commandRef, phase, refCon):
        return self.rabbitMode(commandRef=commandRef, phase=phase, refCon=refCon, mode=RABBIT_MODE.SLOWER)

    def rabbitModeMed(self, commandRef, phase, refCon):
        return self.rabbitMode(commandRef=commandRef, phase=phase, refCon=refCon, mode=RABBIT_MODE.MED)

    def rabbitModeFaster(self, commandRef, phase, refCon):
        return self.rabbitMode(commandRef=commandRef, phase=phase, refCon=refCon, mode=RABBIT_MODE.FASTER)

    def rabbitModeFastest(self, commandRef, phase, refCon):
        return self.rabbitMode(commandRef=commandRef, phase=phase, refCon=refCon, mode=RABBIT_MODE.FASTEST)

    def rabbitMode(self, commandRef, phase: int, refCon: Any, mode: RABBIT_MODE):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("rabbitMode: not enabled", force=True)
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("rabbitMode: FollowTheGreens available.")
            try:
                self.followTheGreens.rabbitMode(mode)
                self.debug("rabbitMode: set.")
                return 1
            except:
                self.debug("rabbitMode: exception", force=True)
                print_exc()
                return 0
        elif not self.followTheGreens:
            self.debug("rabbitMode: Error: could not create FollowTheGreens", force=True)
        return 0

    # Data accessors
    def getRunningStatusCallback(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        return 1 if self.followTheGreens is not None and self.followTheGreens.flightLoop.rabbitRunning else 0

    def getFTGIsHoldingCallback(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        return 1 if self.followTheGreens is not None and self.followTheGreens.ui.waiting_for_clearance else 0

    # Future use
    def runningStatusChangedCallback(self, inRefcon):
        """
        This is the callback for our shared data.  Right now we do not react
        to our shared data being chagned. (For "owned" data, we don't
        get a callback like this -- instead, our Accessors are called: MySetData(f|d)Callback.
        """
        pass
