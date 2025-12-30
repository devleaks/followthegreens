# Follow the greens XP Python3 Plugin Interface
#
# See README file in followhtegreens folder.
# Enjoy.
#
#
from traceback import print_exc

import xp

from followthegreens import __VERSION__, __NAME__, __SIGNATURE__, __DESCRIPTION__
from followthegreens import (
    XP_FTG_COMMAND,
    XP_FTG_COMMAND_DESC,
    FOLLOW_THE_GREENS_IS_RUNNING,
    FTG_MENU,
)
from followthegreens import XP_FTG_CLEARANCE_COMMAND, XP_FTG_CLEARANCE_COMMAND_DESC
from followthegreens import XP_FTG_CANCEL_COMMAND, XP_FTG_CANCEL_COMMAND_DESC
from followthegreens import XP_FTG_OK_COMMAND, XP_FTG_OK_COMMAND_DESC
from followthegreens import XP_FTG_SPEED_COMMAND, XP_FTG_SPEED_COMMAND_DESC
from followthegreens import XP_STW_COMMAND, XP_STW_COMMAND_DESC, STW_MENU
from followthegreens import FollowTheGreens, ShowTaxiways


class PythonInterface:
    def __init__(self):
        self.Name = __NAME__
        self.Sig = __SIGNATURE__
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" (rel. {__VERSION__})"
        self.trace = True  # produces extra debugging in XPPython3.log for this class

        self.followTheGreens = None
        self.enabled = False

        self.isRunningRef = None

        # 1. Follow The Greens
        self.menuIdx = None
        self.followTheGreensCmdRef = None
        self.clearanceCmdRef = None
        self.cancelCmdRef = None
        self.okCmdRef = None

        # 2. Show Taxiways
        self.menuIdx_st = None
        self.showTaxiways = None
        self.showTaxiwaysCmdRef = None
        self.rabbitModeCmdRefs = {}

        self.rabbitModes = {
            "slow": self.rabbitModeSlow,
            "slower": self.rabbitModeSlower,
            "med": self.rabbitModeMed,
            "faster": self.rabbitModeFaster,
            "fast": self.rabbitModeFast,
        }

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "XPluginStart: starting..")

        # 1. Follow The Greens
        self.followTheGreensCmdRef = xp.createCommand(
            XP_FTG_COMMAND, XP_FTG_COMMAND_DESC
        )
        xp.registerCommandHandler(
            self.followTheGreensCmdRef, self.followTheGreensCmd, 1, None
        )
        if self.followTheGreensCmdRef is not None:
            if self.trace:
                print(self.Info, f"XPluginStart: {XP_FTG_COMMAND} command registered")
        else:
            if self.trace:
                print(self.Info, f"XPluginStart: {XP_FTG_COMMAND} not registered")

        self.clearanceCmdRef = xp.createCommand(
            XP_FTG_CLEARANCE_COMMAND, XP_FTG_CLEARANCE_COMMAND_DESC
        )
        xp.registerCommandHandler(self.clearanceCmdRef, self.clearanceCmd, 1, None)
        if self.followTheGreensCmdRef is not None:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_CLEARANCE_COMMAND} command registered",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_CLEARANCE_COMMAND} command not registered",
                )

        self.cancelCmdRef = xp.createCommand(
            XP_FTG_CANCEL_COMMAND, XP_FTG_CANCEL_COMMAND_DESC
        )
        xp.registerCommandHandler(self.cancelCmdRef, self.cancelCmd, 1, None)
        if self.followTheGreensCmdRef is not None:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_CANCEL_COMMAND} command registered",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_CANCEL_COMMAND} command not registered",
                )

        self.okCmdRef = xp.createCommand(XP_FTG_OK_COMMAND, XP_FTG_OK_COMMAND_DESC)
        xp.registerCommandHandler(self.okCmdRef, self.okCmd, 1, None)
        if self.followTheGreensCmdRef is not None:
            if self.trace:
                print(
                    self.Info, f"XPluginStart: {XP_FTG_OK_COMMAND} command registered"
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_OK_COMMAND} command not registered",
                )

        self.menuIdx = xp.appendMenuItemWithCommand(
            xp.findPluginsMenu(), FTG_MENU, self.followTheGreensCmdRef
        )
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            print(self.Info, "XPluginStart: menu not added")
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: menu item «{FTG_MENU}» added (index {self.menuIdx})",
                )

        self.isRunningRef = xp.registerDataAccessor(
            FOLLOW_THE_GREENS_IS_RUNNING,
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

        # 2. Show Taxiways
        self.showTaxiwaysCmdRef = xp.createCommand(XP_STW_COMMAND, XP_STW_COMMAND_DESC)
        xp.registerCommandHandler(
            self.showTaxiwaysCmdRef, self.showTaxiwaysCmd, 1, None
        )
        self.menuIdx_st = xp.appendMenuItemWithCommand(
            xp.findPluginsMenu(), STW_MENU, self.showTaxiwaysCmdRef
        )
        if self.menuIdx_st is None or (
            self.menuIdx_st is not None and self.menuIdx_st < 0
        ):
            print(self.Info, "XPluginStart: Show Taxiways menu not added")
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: menu item «{STW_MENU}» added (index={self.menuIdx_st})",
                )

        # 3. Rabbit modes
        self.rabbitModeCmdRefs = {}
        for mode, callback in self.rabbitModes.items():
            self.rabbitModeCmdRefs[mode] = xp.createCommand(
                XP_FTG_SPEED_COMMAND + mode, XP_FTG_SPEED_COMMAND_DESC + mode
            )
            xp.registerCommandHandler(self.rabbitModeCmdRefs[mode], callback, 1, None)
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStart: {XP_FTG_SPEED_COMMAND + mode} command registered",
                )
        print(self.Info, "XPluginStart: registered speed commands")

        print(self.Info, "XPluginStart: ..started")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "XPluginStop: stopping..")

        # 1. Follow The Greens
        if self.followTheGreensCmdRef:  # XP_FTG_COMMAND
            xp.unregisterCommandHandler(
                self.followTheGreensCmdRef, self.followTheGreensCmd, 1, None
            )
            self.followTheGreensCmdRef = None
            if self.trace:
                print(self.Info, f"XPluginStop: {XP_FTG_COMMAND} command unregistered")
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_COMMAND} command not unregistered",
                )

        if self.clearanceCmdRef:  # XP_FTG_CLEARANCE_COMMAND
            xp.unregisterCommandHandler(
                self.clearanceCmdRef, self.clearanceCmd, 1, None
            )
            self.clearanceCmdRef = None
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_CLEARANCE_COMMAND} command unregistered",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_CLEARANCE_COMMAND} command not unregistered",
                )

        if self.cancelCmdRef:  # XP_FTG_CANCEL_COMMAND
            xp.unregisterCommandHandler(self.cancelCmdRef, self.cancelCmd, 1, None)
            self.cancelCmdRef = None
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_CANCEL_COMMAND} command unregistered",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_CANCEL_COMMAND} command not unregistered",
                )

        if self.okCmdRef:  # XP_FTG_OK_COMMAND
            xp.unregisterCommandHandler(self.okCmdRef, self.okCmd, 1, None)
            self.okCmdRef = None
            if self.trace:
                print(
                    self.Info, f"XPluginStop: {XP_FTG_OK_COMMAND} command unregistered"
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: {XP_FTG_OK_COMMAND} command not unregistered",
                )

        # Rabbit speeds
        for mode, callback in self.rabbitModes.items():
            if self.rabbitModeCmdRefs[mode] is not None:
                xp.unregisterCommandHandler(
                    self.rabbitModeCmdRefs[mode], callback, 1, None
                )
                if self.trace:
                    print(
                        self.Info,
                        f"XPluginStop: {XP_FTG_SPEED_COMMAND + mode} command unregistered",
                    )
        print(self.Info, "XPluginStop: unregistered speed commands")

        # Follow the Greens
        oldidx = self.menuIdx
        if self.menuIdx is not None and self.menuIdx >= 0:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: menu item «{FTG_MENU}» removed (index was {oldidx})",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: menu item «{FTG_MENU}» not removed (index {oldidx})",
                )

        if self.isRunningRef is not None:  # and self.isRunningRef > 0?
            # xp.unshareData(FOLLOW_THE_GREENS_IS_RUNNING, xp.Type_Int, self.runningStatusChangedCallback, 0)
            xp.unregisterDataAccessor(self.isRunningRef)
            self.isRunningRef = None
            if self.trace:
                print(self.Info, "XPluginStop: data accessor unregistered")
        else:
            if self.trace:
                print(self.Info, "XPluginStop: data accessor not unregistered")

        if self.followTheGreens:
            try:
                self.followTheGreens.stop()
                self.followTheGreens = None
                if self.trace:
                    print(self.Info, f"XPluginStop: FollowTheGreens stopped")
            except:
                print(self.Info, "XPluginStop: exception")
                print_exc()

        # Show Taxiways
        if self.showTaxiwaysCmdRef:
            xp.unregisterCommandHandler(
                self.showTaxiwaysCmdRef, self.showTaxiwaysCmd, 1, None
            )
            self.showTaxiwaysCmdRef = None
        oldidx = self.menuIdx_st
        if self.menuIdx_st is not None and self.menuIdx_st >= 0:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx_st)
            self.menuIdx_st = None
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: menu item «{STW_MENU}» removed (index {oldidx})",
                )
        else:
            if self.trace:
                print(
                    self.Info,
                    f"XPluginStop: menu item «{STW_MENU}» not removed (index {oldidx})",
                )
        if self.showTaxiways:
            try:
                self.showTaxiways.stop()
                self.showTaxiways = None
                if self.trace:
                    print(self.Info, f"XPluginStop: ShowTaxiways stopped")
            except:
                print(self.Info, "XPluginStop: exception")
                print_exc()

        print(self.Info, "XPluginStop: ..stopped")
        return None

    def XPluginEnable(self):
        if self.trace:
            print(self.Info, "XPluginEnable: enabling..")

        # 1. Follow The Greens
        try:
            self.followTheGreens = FollowTheGreens(self)

            if self.isRunningRef is not None:
                for sig in (
                    "com.leecbaker.datareftool",
                    "xplanesdk.examples.DataRefEditor",
                ):
                    dre = xp.findPluginBySignature(sig)
                    if dre != xp.NO_PLUGIN_ID:
                        xp.sendMessageToPlugin(
                            dre, 0x01000000, FOLLOW_THE_GREENS_IS_RUNNING
                        )
                        if self.trace:
                            print(
                                self.Info,
                                f"XPluginEnable: data accessor registered with {sig}",
                            )
                    else:
                        if self.trace:
                            print(self.Info, f"XPluginEnable: plugin {sig} not found")
            else:
                if self.trace:
                    print(self.Info, "XPluginEnable: no data accessor")

            print(self.Info, "XPluginEnable: FollowTheGreens created")
        except:
            print(self.Info, "XPluginEnable: ..exception")
            print_exc()

        # 2. Show Taxiways
        try:
            self.showTaxiways = ShowTaxiways(self)
            if self.trace:
                print(self.Info, "XPluginEnable: ShowTaxiways created")
            self.enabled = True
            return 1
        except:
            print(self.Info, "XPluginEnable: exception")
            print_exc()

        self.enabled = False
        print(self.Info, "XPluginEnable: ..not enabled")
        return 0

    def XPluginDisable(self):
        if self.trace:
            print(self.Info, "XPluginDisable: disabling..")

        # 1. Follow The Greens
        try:
            if self.enabled and self.followTheGreens:
                self.followTheGreens.disable()
                self.followTheGreens = None
            print(self.Info, "XPluginDisable: FollowTheGreens disabled")
        except:
            print(self.Info, "XPluginDisable: exception")
            print_exc()

        # 2. Show Taxiways
        try:
            if self.enabled and self.showTaxiways:
                self.showTaxiways.disable()
                self.showTaxiways = None

            if self.trace:
                print(self.Info, "XPluginDisable: ShowTaxiways disabled")
                print(self.Info, "XPluginDisable: ..disabled")
            self.enabled = False
            return None
        except:
            print(self.Info, "XPluginDisable: exception")
            print_exc()

        self.enabled = False
        print(self.Info, "XPluginDisable: ..disabled with exception")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        # Should may be handle change of location/airport?
        pass

    def clearanceCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "clearanceCmd: not enabled.")
            return 0

        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "clearanceCmd: command phase", commandPhase)
        else:
            print(self.Info, "clearanceCmd: no command phase", len(args))

        if self.followTheGreens and commandPhase == 0:
            if self.trace:
                print(self.Info, "clearanceCmd: available.")
            try:
                self.followTheGreens.ui.clearanceReceived()
                if self.trace:
                    print(self.Info, "clearanceCmd: executed.")
                return 1
            except:
                print(self.Info, "clearanceCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            print(self.Info, "clearanceCmd: no FollowTheGreens running.")

        return 0

    def cancelCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "cancelCmd: not enabled.")
            return 0

        # When mapped on a keystroke, followTheGreen only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "cancelCmd: command phase", commandPhase)
        else:
            print(self.Info, "cancelCmd: no command phase", len(args))

        if self.followTheGreens and commandPhase == 0:
            if self.trace:
                print(self.Info, "cancelCmd: available.")
            try:
                self.followTheGreens.ui.cancelReceived("cancel command received")
                if self.trace:
                    print(self.Info, "cancelCmd: executed.")
                return 1
            except:
                print(self.Info, "cancelCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            print(self.Info, "cancelCmd: no FollowTheGreens running.")

        return 0

    def okCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "okCmd: not enabled.")
            return 0

        # When mapped on a keystroke, followTheGreen only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "okCmd: command phase", commandPhase)
        else:
            print(self.Info, "okCmd: no command phase", len(args))

        if self.followTheGreens and commandPhase == 0:
            if self.trace:
                print(self.Info, "okCmd: available.")
            try:
                self.followTheGreens.ui.cancelReceived("ok command received")
                if self.trace:
                    print(self.Info, "okCmd: executed.")
                return 1
            except:
                print(self.Info, "okCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            print(self.Info, "okCmd: no FollowTheGreens running.")

        return 0

    def followTheGreensCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "followTheGreensCmd: not enabled.")
            return 0

        # When mapped on a keystroke, followTheGreen only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "followTheGreensCmd: command phase", commandPhase)
        else:
            print(self.Info, "followTheGreensCmd: no command phase", len(args))

        if not self.followTheGreens:
            try:
                self.followTheGreens = FollowTheGreens(self)
                if self.trace:
                    print(self.Info, "followTheGreensCmd: created.")
            except:
                print(self.Info, "followTheGreensCmd: exception at creation")
                print_exc()
                return 0

        if self.followTheGreens and commandPhase == 0:
            if self.trace:
                print(self.Info, "followTheGreensCmd: available.")
            try:
                self.followTheGreens.start()
                if self.trace:
                    print(self.Info, "followTheGreensCmd: started.")
                return 1
            except:
                print(self.Info, "followTheGreensCmd: exception")
                print_exc()
                return 0
        elif not self.followTheGreens:
            print(
                self.Info,
                "followTheGreensCmd: Error: could not create FollowTheGreens.",
            )

        return 0

    def getRunningStatusCallback(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        if self.followTheGreens is not None:
            if self.followTheGreens.flightLoop.rabbitRunning:
                return 1
        return 0

    def runningStatusChangedCallback(self, inRefcon):
        """
        This is the callback for our shared data.  Right now we do not react
        to our shared data being chagned. (For "owned" data, we don't
        get a callback like this -- instead, our Accessors are called: MySetData(f|d)Callback.
        """
        pass

    def showTaxiwaysCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "showTaxiwaysCmd: not enabled.")
            return 0

        # When mapped on a keystroke, showTaxiways only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "showTaxiwaysCmd: command phase", commandPhase)
        else:
            print(self.Info, "showTaxiwaysCmd: no command phase", len(args))

        if not self.showTaxiways:
            try:
                self.showTaxiways = ShowTaxiways(self)
                if self.trace:
                    print(self.Info, "showTaxiwaysCmd: created.")
            except:
                print(self.Info, "showTaxiwaysCmd: exception at creation")
                print_exc()
                return 0

        if self.showTaxiways and commandPhase == 0:
            if self.trace:
                print(self.Info, "showTaxiwaysCmd: available.")

            if (
                self.showTaxiways.ui.mainWindowExists()
            ):  # already running, we stop it...
                try:
                    self.showTaxiways.cancel()
                    if self.trace:
                        print(self.Info, "showTaxiwaysCmd: ended.")
                    return 1
                except:
                    print(self.Info, "showTaxiwaysCmd: exception")
                    print_exc()
                return 0

            try:
                self.showTaxiways.start()
                if self.trace:
                    print(self.Info, "showTaxiwaysCmd: started.")
                return 1
            except:
                print(self.Info, "showTaxiwaysCmd: exception")
                print_exc()
        elif not self.showTaxiways:
            print(self.Info, "showTaxiwaysCmd: Error: could not create ShowTaxiways.")

        return 0

    def rabbitModeSlow(self, commandRef, phase, refCon):
        return self.rabbitMode(
            commandRef=commandRef, phase=phase, refCon=refCon, mode="slow"
        )

    def rabbitModeSlower(self, commandRef, phase, refCon):
        return self.rabbitMode(
            commandRef=commandRef, phase=phase, refCon=refCon, mode="slower"
        )

    def rabbitModeMed(self, commandRef, phase, refCon):
        return self.rabbitMode(
            commandRef=commandRef, phase=phase, refCon=refCon, mode="med"
        )

    def rabbitModeFast(self, commandRef, phase, refCon):
        return self.rabbitMode(
            commandRef=commandRef, phase=phase, refCon=refCon, mode="fast"
        )

    def rabbitModeFaster(self, commandRef, phase, refCon):
        return self.rabbitMode(
            commandRef=commandRef, phase=phase, refCon=refCon, mode="faster"
        )

    def rabbitMode(self, commandRef, phase: int, refCon, mode: str):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "rabbitMode: not enabled.")
            return 0

        if self.followTheGreens and phase == 0:
            if self.trace:
                print(self.Info, "rabbitMode: FollowTheGreens available.")
            try:
                self.followTheGreens.rabbitMode(mode)
                if self.trace:
                    print(self.Info, "rabbitMode: set.")
                return 1
            except:
                print(self.Info, "rabbitMode: exception")
                print_exc()
                return 0
        elif not self.followTheGreens:
            print(self.Info, "rabbitMode: Error: could not create FollowTheGreens.")

        return 0
