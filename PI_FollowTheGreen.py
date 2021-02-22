# Follow The Green XP Python3 Plugin Interface
# Rel. 0.0.5 04-FEB-2021
#
from traceback import print_exc
import xp
from followthegreen import FollowTheGreen


class PythonInterface:

    def __init__(self):
        self.Name = "Follow the green"
        self.Sig = "followthegreen.xppython3"
        self.Desc = "Follow the green, an X-Plane ATC A-SMGCS experience."
        self.enabled = False
        self.trace = False  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.followTheGreen = None
        self.followTheGreenCmdRef = None

    def XPluginStart(self):
        self.followTheGreenCmdRef = xp.createCommand('xppython3/followthegreen/toggle', 'Open or close Follow The Green window')
        xp.registerCommandHandler(self.followTheGreenCmdRef, self.followTheGreenCmd, 1, None)
        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), 'Follow The Green', self.followTheGreenCmdRef)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.followTheGreenCmdRef:
            xp.unregisterCommandHandler(self.followTheGreenCmdRef,
                                        self.followTheGreenCmd,
                                        1, None)
            self.followTheGreenCmdRef = None
        if self.menuIdx:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
        if self.followTheGreen:
            try:
                self.followTheGreen.stop()
                self.followTheGreen = None
                if self.trace:
                    print(self.Name, "PI::XPluginStop: stopped.")
            except:
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            self.followTheGreen = FollowTheGreen(self)
            if self.trace:
                print(self.Name, "PI::XPluginEnable: enabled.")
            self.enabled = True
            return 1
        except:
            print_exc()
        return 0

    def XPluginDisable(self):
        try:
            if self.enabled and self.followTheGreen:
                self.followTheGreen.disable()
                self.followTheGreen = None

            self.enabled = False
            if self.trace:
                print(self.Name, "PI::XPluginDisable: disabled.")
            return None
        except:
            print_exc()
            self.enabled = False
            return None
        self.enabled = False
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass


    def followTheGreenCmd(self, *args, **kwargs):
        # pylint: disable=unused-argument
        if not self.enabled:
            print(self.Name, "PI::followTheGreenCmd: not enabled.")
            return 0

        # When mapped on a keystroke, followTheGreen only starts on begin of command (phase=0).
        # Phase=1 (continuous press) and phase=2 (release key) are ignored.
        # If phase not found, report it in log and assume phase=0 (i.e. work will be done.)
        commandPhase = 0
        if len(args) > 2:
            commandPhase = args[1]
            if self.trace:
                print(self.Name, "PI::followTheGreenCmd: COMMAND PHASE", commandPhase)
        else:
            print(self.Name, "PI::followTheGreenCmd: NO COMMAND PHASE", len(args))

        if not self.followTheGreen:
            try:
                self.followTheGreen = FollowTheGreen(self)
                if self.trace:
                    print(self.Name, "PI::followTheGreenCmd: created.")
            except:
                print_exc()
                return 0

        if self.followTheGreen and commandPhase == 0:
            if self.trace:
                print(self.Name, "PI::followTheGreenCmd: available.")
            try:
                self.followTheGreen.start()
                if self.trace:
                    print(self.Name, "PI::followTheGreenCmd: started.")
                return 1
            except:
                print_exc()
                return 0
        elif not self.followTheGreen:
            print(self.Name, "PI::followTheGreenCmd: Error: could not create FollowTheGreen.")

        return 0
