# Follow the greens XP Python3 Plugin Interface
#
# See README file in followhtegreens folder.
# Enjoy.
#
#
from traceback import print_exc

import xp

from followthegreens import __VERSION__, __NAME__, __SIGNATURE__, __DESCRIPTION__
from followthegreens import XP_FTG_COMMAND, XP_FTG_COMMAND_DESC, FOLLOW_THE_GREENS_IS_RUNNING
from followthegreens import FollowTheGreens


class PythonInterface:

    def __init__(self):
        self.Name = __NAME__
        self.Sig = __SIGNATURE__
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" (rel. {__VERSION__})"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.followTheGreens = None
        self.followTheGreensCmdRef = None
        self.isRunningRef = None

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "PI::XPluginStart: starting..")

        self.followTheGreensCmdRef = xp.createCommand(XP_FTG_COMMAND, XP_FTG_COMMAND_DESC)
        xp.registerCommandHandler(self.followTheGreensCmdRef, self.followTheGreensCmd, 1, None)
        if self.followTheGreensCmdRef is not None:
            if self.trace:
                print(self.Info, "PI::XPluginStart: command registered.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStop: command not registered.")

        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), self.Name, self.followTheGreensCmdRef)
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            print(self.Info, "PI::XPluginStart: menu not added.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStart: menu added.")

        self.isRunningRef = xp.registerDataAccessor(
            FOLLOW_THE_GREENS_IS_RUNNING,
            xp.Type_Int,  # The types we support
            0,            # Read-Only
            self.getRunningStatusCallback, 0, # Accessors for ints, read-only, no write.
            0, 0,   # No accessors for floats
            0, 0,   # No accessors for doubles
            0, 0,   # No accessors for int arrays
            0, 0,   # No accessors for float arrays
            0, 0,   # No accessors for raw data
            0, 0)   # Refcons not used
        if self.isRunningRef is not None:
            xp.shareData(FOLLOW_THE_GREENS_IS_RUNNING, xp.Type_Int, self.runningStatusChangedCallback, 0)
            if self.trace:
                print(self.Info, "PI::XPluginStart: data accessor registered.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStart: data accessor not registered.")

        if self.trace:
            print(self.Info, "PI::XPluginStart: ..started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "PI::XPluginStart: stopping..")

        if self.followTheGreensCmdRef:
            xp.unregisterCommandHandler(self.followTheGreensCmdRef,
                                        self.followTheGreensCmd,
                                        1, None)
            self.followTheGreensCmdRef = None
            if self.trace:
                print(self.Info, "PI::XPluginStop: command unregistered.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStop: command not unregistered.")

        if self.menuIdx is not None and self.menuIdx >= 0:
            oldidx = self.menuIdx
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(self.Info, "PI::XPluginStop: menu removed.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStop: menu not removed.")

        if self.isRunningRef is not None: # and self.isRunningRef > 0?
            xp.unshareData(FOLLOW_THE_GREENS_IS_RUNNING, xp.Type_Int, self.runningStatusChangedCallback, 0)
            xp.unregisterDataAccessor(self.isRunningRef)
            if self.trace:
                print(self.Info, "PI::XPluginStop: data accessor unregistered.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStop: data accessor not unregistered.")

        if self.followTheGreens:
            try:
                self.followTheGreens.stop()
                self.followTheGreens = None
                if self.trace:
                    print(self.Info, "PI::XPluginStop: ..stopped.")
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginStop: ..exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        if self.trace:
            print(self.Info, "PI::XPluginEnable: enabling..")
        try:
            self.followTheGreens = FollowTheGreens(self)
            self.enabled = True

            if self.isRunningRef is not None:
                for sig in ("com.leecbaker.datareftool", "xplanesdk.examples.DataRefEditor"):
                    dre = xp.findPluginBySignature(sig)
                    if dre != xp.NO_PLUGIN_ID:
                        xp.sendMessageToPlugin(dre, 0x01000000, FOLLOW_THE_GREENS_IS_RUNNING)
                        if self.trace:
                            print(self.Info, f"PI::XPluginEnable: data accessor registered with {sig}.")
                    else:
                        if self.trace:
                            print(self.Info, f"PI::XPluginEnable: dataref not created.")
            else:
                if self.trace:
                    print(self.Info, f"PI::XPluginEnable: plgin {sig} not found.")

            if self.trace:
                print(self.Info, "PI::XPluginEnable: ..enabled.")
            return 1
        except:
            if self.trace:
                print(self.Info, "PI::XPluginEnable: ..exception.")
            print_exc()
        return 0

    def XPluginDisable(self):
        if self.trace:
            print(self.Info, "PI::XPluginDisable: disabling..")
        try:
            if self.enabled and self.followTheGreens:
                self.followTheGreens.disable()
                self.followTheGreens = None
            self.enabled = False
            if self.trace:
                print(self.Info, "PI::XPluginDisable: disabled.")
            return None
        except:
            if self.trace:
                print(self.Info, "PI::XPluginDisable: exception.")
            print_exc()
            self.enabled = False
            return None
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass

    def followTheGreensCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Info, "PI::followTheGreensCmd: not enabled.")
            return 0

        # When mapped on a keystroke, followTheGreen only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Info, "PI::followTheGreensCmd: COMMAND PHASE", commandPhase)
        else:
            print(self.Info, "PI::followTheGreensCmd: NO COMMAND PHASE", len(args))

        if not self.followTheGreens:
            try:
                self.followTheGreens = FollowTheGreens(self)
                if self.trace:
                    print(self.Info, "PI::followTheGreensCmd: created.")
            except:
                if self.trace:
                    print(self.Info, "PI::followTheGreensCmd: exception.")
                print_exc()
                return 0

        if self.followTheGreens and commandPhase == 0:
            if self.trace:
                print(self.Info, "PI::followTheGreensCmd: available.")
            try:
                self.followTheGreens.start()
                if self.trace:
                    print(self.Info, "PI::followTheGreensCmd: started.")
                return 1
            except:
                if self.trace:
                    print(self.Info, "PI::followTheGreensCmd: exception(2).")
                print_exc()
                return 0
        elif not self.followTheGreens:
            print(self.Info, "PI::followTheGreensCmd: Error: could not create FollowTheGreens.")

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

