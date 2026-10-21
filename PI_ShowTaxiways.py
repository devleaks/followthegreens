# Follow the greens XP Python3 Plugin Interface
#
# See README file in followhtegreens folder.
# Enjoy.
#
#
import logging
from traceback import print_exc

import xp

from followthegreens import __VERSION__
from followthegreens import XP_STW_COMMAND, XP_STW_COMMAND_DESC
from followthegreens import ShowTaxiways

FORMAT = "%(levelname)s %(filename)s:%(funcName)s:%(lineno)d: %(message)s"
logging.basicConfig(level=logging.INFO, format=FORMAT)


class PythonInterface:
    def __init__(self):
        self.Name = "Show taxiways"
        self.Sig = "xppython3.showtaxiways"
        self.Desc = (
            "Show taxiways, highlight taxiway network" + " (Rel. " + __VERSION__ + ")"
        )
        self.Info = self.Name + f" (rel. {__VERSION__})"
        self.enabled = False
        self.trace = False  # produces extra debugging in XPPython3.log for this class
        self.menuIdx = None
        self.showTaxiways = None
        self.showTaxiwaysCmdRef = None

    def XPluginStart(self):
        if self.trace:
            print(self.Info, "XPluginStart: starting..")

        self.showTaxiwaysCmdRef = xp.createCommand(XP_STW_COMMAND, XP_STW_COMMAND_DESC)
        xp.registerCommandHandler(
            self.showTaxiwaysCmdRef, self.showTaxiwaysCmd, 1, None
        )
        self.menuIdx = xp.appendMenuItemWithCommand(
            xp.findPluginsMenu(), self.Name, self.showTaxiwaysCmdRef
        )
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            print(self.Info, "XPluginStart: menu not added.")
        else:
            if self.trace:
                print(self.Info, "XPluginStart: menu added.", self.menuIdx)

        print(self.Info, "XPluginStart: ..started.")
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        if self.trace:
            print(self.Info, "XPluginStop: stopping..")

        if self.showTaxiwaysCmdRef:
            xp.unregisterCommandHandler(
                self.showTaxiwaysCmdRef, self.showTaxiwaysCmd, 1, None
            )
            self.showTaxiwaysCmdRef = None
        oldidx = self.menuIdx
        if self.menuIdx is not None and self.menuIdx >= 0:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            if self.trace:
                print(self.Info, "XPluginStop: menu removed.", oldidx)
        else:
            if self.trace:
                print(self.Info, "XPluginStop: menu not removed.", oldidx)
        if self.showTaxiways:
            try:
                self.showTaxiways.stop()
                self.showTaxiways = None
            except:
                print(self.Info, "XPluginStop: exception")
                print_exc()

        print(self.Info, "XPluginStop: ..stopped.")
        return None

    def XPluginEnable(self):
        if self.trace:
            print(self.Info, "XPluginEnable: enabling..")
        try:
            self.showTaxiways = ShowTaxiways(self)
            self.enabled = True
            if self.trace:
                print(self.Info, "XPluginEnable: enabled.")
            return 1
        except:
            print(self.Info, "XPluginEnable: exception")
            print_exc()
        print(self.Info, "XPluginEnable: not enabled.")
        return 0

    def XPluginDisable(self):
        if self.trace:
            print(self.Info, "XPluginEnable: disabling..")
        try:
            if self.enabled and self.showTaxiways:
                self.showTaxiways.disable()
                self.showTaxiways = None

            self.enabled = False
            if self.trace:
                print(self.Info, "XPluginDisable: ..disabled.")
            return None
        except:
            print(self.Info, "XPluginDisable: exception")
            print_exc()
        self.enabled = False
        print(self.Info, "XPluginEnable: ..disabled with issue.")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
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
