# Follow the greens XP Python3 Plugin Interface
#
from traceback import print_exc
import xp
from followthegreens import FollowTheGreens, __VERSION__


class PythonInterface:

    def __init__(self):
        self.Name = "Follow the greens"
        self.Sig = "followthegreens.xppython3"
        self.Desc = "Follow the greens, an X-Plane ATC A-SMGCS experience. (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" (rel. {__VERSION__})"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.followTheGreens = None
        self.followTheGreensCmdRef = None

    def XPluginStart(self):
        self.followTheGreensCmdRef = xp.createCommand('XPPython3/followthegreens/main_windown_toggle', 'Open or close Follow the Greens window')
        xp.registerCommandHandler(self.followTheGreensCmdRef, self.followTheGreensCmd, 1, None)
        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), self.Name, self.followTheGreensCmdRef)
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            print(self.Info, "PI::XPluginStart: menu not added.")
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStart: menu added.", self.menuIdx)
        if self.trace:
            print(self.Info, "PI::XPluginStart: started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.followTheGreensCmdRef:
            xp.unregisterCommandHandler(self.followTheGreensCmdRef,
                                        self.followTheGreensCmd,
                                        1, None)
            self.followTheGreensCmdRef = None
        if self.menuIdx is not None and self.menuIdx >= 0:
            oldidx = self.menuIdx
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(self.Info, "PI::XPluginStop: menu removed.", oldidx)
        else:
            if self.trace:
                print(self.Info, "PI::XPluginStop: menu not removed.")
        if self.followTheGreens:
            try:
                self.followTheGreens.stop()
                self.followTheGreens = None
                if self.trace:
                    print(self.Info, "PI::XPluginStop: stopped.")
            except:
                if self.trace:
                    print(self.Info, "PI::XPluginStop: exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            self.followTheGreens = FollowTheGreens(self)
            self.enabled = True
            if self.trace:
                print(self.Info, "PI::XPluginEnable: enabled.")
            return 1
        except:
            if self.trace:
                print(self.Info, "PI::XPluginEnable: exception.")
            print_exc()
        return 0

    def XPluginDisable(self):
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
