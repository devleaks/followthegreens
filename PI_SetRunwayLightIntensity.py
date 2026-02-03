# Adds X-Plane Plugins menu entries to control runway lights
import xp
from traceback import print_exc

__VERSION__ = "1.0.0"
__NAME__ = "Set Runway Light Intensity"
__DESCRIPTION__ = "Wrapper around X-Plane runway light control commands"

# Produces additional debugging information in XPPython3Log.txt file if set to True
SHOW_TRACE = False

MENU = "Set Runway Lights"

class PythonInterface:

    PLUGIN_ROOT_PATH = "XPPython3/set_runway_lights/"
    CMDROOT = "sim/operation/rwy_lights_"  # + AMBIANT_RWY_LIGHT
    LEVEL = {
        "hi": "Hight",
        "med": "Medium",
        "lo": "Low",
        "off": "Off",
    }

    def __init__(self):
        self.Name = __NAME__
        self.Sig = PythonInterface.PLUGIN_ROOT_PATH.strip("/").replace("/", ".")
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" {__VERSION__}"

        self.enabled = False

        self.trace = SHOW_TRACE

        self.cmdRefs = {}
        self.menuIdx = None
        self.menuIdxs = {}

    def debug(self, message, force: bool = False):
        if self.trace or force:
            print(self.Info, message)

    # Plugin Interface
    def XPluginStart(self):
        self.debug("XPluginStart: starting..", force=True)

        self.menuIdx = xp.createMenu(name=MENU)
        if self.menuIdx is None:
            self.debug(f"XPluginStart: menu {MENU} not added")
            self.debug("XPluginStart: ..not started", force=True)
            return self.Name, self.Sig, self.Desc
        else:
            self.debug(f"XPluginStart: menu item «{MENU}» added (index {self.menuIdx})")

        for k, v in self.LEVEL.items():
            self.cmdRefs[k] = xp.findCommand(name=self.CMDROOT + k)
            if self.cmdRefs[k] is not None:
                self.menuIdxs[k] = xp.appendMenuItemWithCommand(menuID=self.menuIdx, name=v, commandRef=self.cmdRefs[k])
                if self.menuIdxs[k] is None:
                    self.debug(f"XPluginStart: menu {v} not added")
                else:
                    self.debug(f"XPluginStart: menu item «{v}» added (index {self.menuIdxs[k]})")
            else:
                self.debug(f"XPluginStart: {v} not registered")

        self.debug("XPluginStart: ..started", force=True)
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self):
        self.debug("XPluginStop: stopping..", force=True)

        for k, v in self.cmdRefs.items():
            if v is not None:  # FTG_COMMAND
                xp.removeMenuItem(self.menuIdx, self.menuIdxs[k])
                self.debug(f"XPluginStop: {k} command unregistered")
            else:
                self.debug(f"XPluginStop: {k} command not unregistered")

        if self.menuIdx is not None and self.menuIdx >= 0:
            xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
            self.menuIdx = None
            self.debug(f"XPluginStop: menu item «{MENU}» removed")
        else:
            self.debug(f"XPluginStop: menu item «{MENU}» not removed")

        self.debug("XPluginStop: ..stopped", force=True)
        return None

    def XPluginEnable(self):
        self.debug("XPluginEnable: enabling..", force=True)
        if self.menuIdx is not None:
            self.enabled = True
            self.debug("XPluginStop: ..enabled", force=True)
            return 1
        return 0

    def XPluginDisable(self):
        self.debug("XPluginDisable: disabling..")
        self.enabled = False
        self.debug("XPluginDisable: ..disabled")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        pass