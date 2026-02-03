# Adds X-Plane Plugins menu entries to control runway lights
import xp

__VERSION__ = "1.0.1"
__NAME__ = "Set Runway Light Intensity"
__DESCRIPTION__ = "Wrapper around X-Plane runway light control commands"


class PythonInterface:

    LEVEL = {
        "hi": "Hight",
        "med": "Medium",
        "lo": "Low",
        "off": "Off",
    }

    def __init__(self):
        self.Name = __NAME__
        self.Sig = "XPPython3.set_runway_lights."
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" {__VERSION__}"
        self.menuIdx = 0
        self.cmdRefs = {}
        self.menuIdxs = {}

    # Plugin Interface
    def XPluginStart(self) -> tuple:
        self.menuIdx = xp.createMenu(name="Set Runway Lights")
        self.cmdRefs = {v: xp.findCommand(name="sim/operation/rwy_lights_" + k) for k, v in self.LEVEL.items()}
        self.menuIdxs = {k: xp.appendMenuItemWithCommand(menuID=self.menuIdx, name=k, commandRef=v) for k, v in self.cmdRefs.items() if v is not None}
        return self.Name, self.Sig, self.Desc

    def XPluginStop(self) -> None:
        for v in self.menuIdxs.values():
            xp.removeMenuItem(menuID=self.menuIdx, index=v)
        xp.removeMenuItem(menuID=xp.findPluginsMenu(), index=self.menuIdx)
        return None

    def XPluginEnable(self) -> int:
        return 1

    def XPluginDisable(self) -> None:
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam) -> None:
        pass
