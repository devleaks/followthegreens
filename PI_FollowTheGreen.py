# Follow The Green XP Python3 Plugin Interface
#
from traceback import print_exc
import xp
from followthegreen import FollowTheGreen
"""
     if running on xppython3 3.1.3 or later the reload of the modules will not work like it woked with 3.1.2
     the reload() from the import lib might work for some cases, but as the __init__() will not be reloaded
     the bytecode still remains the same.... Need to see a solution, until then - for development - stay on 3.1.2

from importlib import reload
import followthegreen            # Only needed for development, when dynamically changing the code
result = reload(followthegreen)  # and using the XPPython3 reload function.
from followthegreen import FollowTheGreen
     
"""


RELEASE = "1.3.0b"

class PythonInterface:

    def __init__(self):
        self.Name = "Follow the Greens"
        self.Sig = "followthegreens.xppython3"
        self.Desc = "Follow the Greens, an X-Plane ATC A-SMGCS experience. (Rel. " + RELEASE + ")"
        self.enabled = False
        self.trace = True  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.followTheGreen = None
        self.followTheGreenCmdRef = None

    def XPluginStart(self):
        self.followTheGreenCmdRef = xp.createCommand('xppython3/followthegreen/toggle', 'Open or close Follow the Greens window')
        xp.registerCommandHandler(self.followTheGreenCmdRef, self.followTheGreenCmd, 1, None)
        self.menuIdx = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), self.Name, self.followTheGreenCmdRef)
        if self.trace:
            print(self.Name, "PI::XPluginStop: menu added.")
        if self.trace:
            print(self.Name, "PI::XPluginStart: started.")
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
            if self.trace:
                print(self.Name, "PI::XPluginStop: menu removed.")
        if self.followTheGreen:
            try:
                self.followTheGreen.stop()
                self.followTheGreen = None
                if self.trace:
                    print(self.Name, "PI::XPluginStop: stopped.")
            except:
                if self.trace:
                    print(self.Name, "PI::XPluginStop: exception.")
                print_exc()
        return None

    def XPluginEnable(self):
        try:
            self.followTheGreen = FollowTheGreen(self)
            self.enabled = True
            if self.trace:
                print(self.Name, "PI::XPluginEnable: enabled.")
            return 1
        except:
            if self.trace:
                print(self.Name, "PI::XPluginEnable: exception.")
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
            if self.trace:
                print(self.Name, "PI::XPluginDisable: exception.")
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
                if self.trace:
                    print(self.Name, "PI::followTheGreenCmd: exception.")
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
                if self.trace:
                    print(self.Name, "PI::followTheGreenCmd: exception(2).")
                print_exc()
                return 0
        elif not self.followTheGreen:
            print(self.Name, "PI::followTheGreenCmd: Error: could not create FollowTheGreen.")

        return 0
