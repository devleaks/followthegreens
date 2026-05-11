# Follow the greens XP Python3 Plugin Interface
#
# See README file in followhtegreens folder.
# Enjoy.
#
#
import sys
import os
import re
from traceback import print_exc
from typing import Any

try:
    import xp
    from XPPython3.utils import xp_pip
except ImportError:
    print("X-Plane not loaded")

missing_modules = []
try:
    import xplane_airports
except ModuleNotFoundError:
    missing_modules.append("xplane_airports")


PLUGIN_FOLDER_NAME = "followthegreens"
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))  # .../PythonPlugins

# Ensure PythonPlugins root is importable so package imports work
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

# Optional safety: ensure folder exists
_PLUGIN_DIR = os.path.join(_THIS_DIR, PLUGIN_FOLDER_NAME)
if not os.path.isdir(_PLUGIN_DIR):
    raise ImportError(f"Missing plugin folder: {_PLUGIN_DIR}")

# ---------------------------------------------------------------------
# IMPORTANT:
# We must import followthegreens as a PACKAGE to allow relative imports
# inside followthegreens.py (e.g. from .version import __VERSION__).
# Therefore, we add the PythonPlugins root to sys.path and import
from followthegreens import (
    __VERSION__,
    __NAME__,
    __DESCRIPTION__,
    FollowTheGreens,
    ShowTaxiways,
    RABBIT_MODE,
    FTG_PLUGIN_ROOT_PATH,
    FTG_HUD,
    FTG_HUD_DESC,
    FTG_CANCEL_COMMAND,
    FTG_CANCEL_COMMAND_DESC,
    FTG_OK_COMMAND,
    FTG_CLEARANCE_COMMAND,
    FTG_CLEARANCE_COMMAND_DESC,
    FTG_IS_RUNNING,
    FTG_INDICATOR,
    FTG_OK_COMMAND_DESC,
    FTG_SPEED_COMMAND,
    FTG_SPEED_COMMAND_DESC,
    FTG_COMMAND,
    FTG_COMMAND_DESC,
    FTC_COMMAND,
    FTC_COMMAND_DESC,
    FTG_BOOKMARK_COMMAND,
    FTG_BOOKMARK_COMMAND_DESC,
    FTG_NEWGREENS_COMMAND,
    FTG_NEWGREENS_COMMAND_DESC,
    FTG_MENU,
    FTC_MENU,
    STW_COMMAND,
    STW_COMMAND_DESC,
    STW_MENU,
)

# Produces additional debugging information in XPPython3Log.txt file if set to True
SHOW_TRACE = False


AMBER = (1.0, 0.85, 0.0)
RED = (1.0, 0.0, 0.0)
GREEN = (0, 1, 0)
CYAN = (0.0, 1.0, 1.0)
WHITE = (1.0, 1.0, 1.0)


class PythonInterface:

    def __init__(self):
        self.Name = __NAME__
        self.vu = "VU" + re.sub("[^0-9]", "", __VERSION__)
        self.Sig = FTG_PLUGIN_ROOT_PATH.strip("/").replace("/", ".")
        self.Desc = __DESCRIPTION__ + " (Rel. " + __VERSION__ + ")"
        self.Info = self.Name + f" {__VERSION__}"

        self.trace = SHOW_TRACE  # produces extra debugging in XPPython3.log for this class

        self.followTheGreens = None
        self.enabled = False

        self.isRunningRef = None
        self.getIndicatorRef = None

        # 1. Follow The Greens
        self.menuIdx = None
        self.menuIdx2 = None
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
            FTC_COMMAND: [FTC_COMMAND_DESC, self.followTheCarCmd],
            FTG_CLEARANCE_COMMAND: [
                FTG_CLEARANCE_COMMAND_DESC,
                self.clearanceCmd,
            ],
            FTG_CANCEL_COMMAND: [FTG_CANCEL_COMMAND_DESC, self.cancelCmd],
            FTG_OK_COMMAND: [FTG_OK_COMMAND_DESC, self.okCmd],
            FTG_NEWGREENS_COMMAND: [FTG_NEWGREENS_COMMAND_DESC, self.newGreensCmd],
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
        # Add back to automatic mode after manual mode
        self.commands = self.commands | {
            FTG_SPEED_COMMAND
            + "auto": [
                FTG_SPEED_COMMAND_DESC + " autotune",
                self.rabbitModeAuto,
            ]
        }
        if FTG_HUD is not None:
            self.commands = self.commands | {
                FTG_HUD: [FTG_HUD_DESC, self.hudToggle],
            }
        self._hud = False  # now shown by default
        self._hud_pos = {}
        self._speed = 0.0
        self._speed_color = (1, 1, 1)
        self._speed_cnt = 0
        # notify
        self.not_message = "Follow the greens"
        self.not_color = (1, 1, 1)
        self.not_duration = 100

    def debug(self, message, force: bool = False):
        if self.trace or force:
            print(self.Info, message)

    # Plugin Interface
    def XPluginStart(self):
        self.debug("XPluginStart: starting..", force=True)

        try:
            self.followTheGreens = FollowTheGreens(self)
            self.debug("XPluginStart: FollowTheGreens created")
        except:
            self.debug("XPluginStart: exception", force=True)
            print_exc()

        if STW_MENU is not None:
            try:
                self.showTaxiways = ShowTaxiways(self)
                self.debug("XPluginStart: ShowTaxiways created")
            except:
                self.debug("XPluginStart: exception", force=True)
                print_exc()

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

        self.menuIdx2 = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), FTC_MENU, self.CmdRefs[FTC_COMMAND])
        if self.menuIdx is None or (self.menuIdx is not None and self.menuIdx < 0):
            self.debug("XPluginStart: menu not added")
        else:
            self.debug(f"XPluginStart: menu item «{FTC_MENU}» added (index {self.menuIdx2})")

        if STW_MENU is not None:
            self.menuIdx_st = xp.appendMenuItemWithCommand(xp.findPluginsMenu(), STW_MENU, self.CmdRefs[STW_COMMAND])
            if self.menuIdx_st is None or (self.menuIdx_st is not None and self.menuIdx_st < 0):
                self.debug("XPluginStart: Show Taxiways menu not added")
            else:
                self.debug(f"XPluginStart: menu item «{STW_MENU}» added (index={self.menuIdx_st})")

        self.debug("XPluginStart: creation of FollowTheGreens is postposed when enabling")
        if STW_MENU is not None:
            self.debug("XPluginStart: creation of ShowTaxiways is postposed when enabling")

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
        self.getIndicatorRef = xp.registerDataAccessor(
            FTG_INDICATOR,
            xp.Type_Int,  # The types we support
            0,  # Read-Only
            self.getIndicator,
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
                try:
                    xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx_st)
                    self.menuIdx_st = None
                    self.debug(f"XPluginStop: menu item «{STW_MENU}» removed (index was {oldidx})")
                except:
                    self.debug(f"XPluginStop: removeMenuItem «{STW_MENU}» error", force=True)
            else:
                self.debug(f"XPluginStop: menu item «{STW_MENU}» not removed (index {oldidx})")

            if self.showTaxiways:
                try:
                    del self.showTaxiways
                    self.showTaxiways = None
                    self.debug("XPluginStop: ShowTaxiways stopped")
                except:
                    self.debug("XPluginStop: exception", force=True)
                    print_exc()

        # Follow the Greens
        oldidx = self.menuIdx2
        if self.menuIdx2 is not None and self.menuIdx2 >= 0:
            try:
                xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx2)
                self.menuIdx2 = None
                self.debug(f"XPluginStop: menu item «{FTC_MENU}» removed (index was {oldidx})")
            except:
                self.debug(f"XPluginStop: removeMenuItem «{FTC_MENU}» error", force=True)
        else:
            self.debug(f"XPluginStop: menu item «{FTC_MENU}» not removed (index {oldidx})")

        oldidx = self.menuIdx
        if self.menuIdx is not None and self.menuIdx >= 0:
            try:
                xp.removeMenuItem(xp.findPluginsMenu(), self.menuIdx)
                self.menuIdx = None
                self.debug(f"XPluginStop: menu item «{FTG_MENU}» removed (index was {oldidx})")
            except:
                self.debug(f"XPluginStop: removeMenuItem «{FTG_MENU}» error", force=True)
        else:
            self.debug(f"XPluginStop: menu item «{FTG_MENU}» not removed (index {oldidx})")

        if self.isRunningRef is not None:  # and self.isRunningRef > 0?
            xp.unregisterDataAccessor(self.isRunningRef)
            xp.unregisterDataAccessor(self.getIndicatorRef)
            self.isRunningRef = None
            self.debug("XPluginStop: data accessor unregistered")
        else:
            self.debug("XPluginStop: data accessor not unregistered")

        if self.followTheGreens:
            try:
                del self.followTheGreens
                self.followTheGreens = None
                self.debug("XPluginStop: FollowTheGreens stopped")
            except:
                self.debug("XPluginStop: exception", force=True)
                print_exc()

        self.debug("XPluginStop: ..stopped", force=True)
        return None

    def XPluginEnable(self):
        self.debug("XPluginEnable: enabling..", force=True)

        if len(missing_modules) > 0:
            xp_pip.load_packages(missing_modules, "Loading missing modules", "Modules loaded.\nCheck for errors, and RESTART X-Plane.")
            return 0  # to disable the plugin

        if FTG_HUD is not None:
            xp.registerDrawCallback(self.hud)

        try:
            if self.followTheGreens is not None:
                self.followTheGreens.enable()
                self.debug("XPluginEnable: FollowTheGreens enabled")
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
        except:
            self.debug("XPluginEnable: exception", force=True)
            print_exc()

        if STW_MENU is not None:
            try:
                if self.showTaxiways is not None:
                    self.showTaxiways.enable()
                    self.debug("XPluginEnable: ShowTaxiways enabled")
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

        # 1. Show Taxiways
        try:
            if self.enabled and self.showTaxiways:
                self.showTaxiways.disable()
                self.debug("XPluginDisable: ShowTaxiways disabled")
                return None
        except:
            self.debug("XPluginDisable: exception")
            print_exc()

        # 2. Follow The Greens
        try:
            if FTG_HUD is not None:
                xp.unregisterDrawCallback(self.hud)

            if self.enabled and self.followTheGreens:
                self.followTheGreens.disable()
            self.debug("XPluginDisable: FollowTheGreens disabled")
            self.enabled = False
            self.debug("XPluginDisable: ..disabled")
        except:
            self.debug("XPluginDisable: exception", force=True)
            print_exc()

        self.enabled = False
        self.debug("XPluginDisable: ..disabled with exception")
        return None

    def XPluginReceiveMessage(self, inFromWho, inMessage, inParam):
        # Both messages invalidate all previously-loaded XPLMObjectRef and
        # XPLMInstanceRef capsules.  If FTG still holds stale capsules and then
        # tries to call xp.createInstance() it raises:
        #   TypeError: mismatch in requested capsule type
        # which freezes / crashes the plugin.
        #
        # Fix: on either message we tear down every live light instance and
        # unload every cached object reference so that the next illumination
        # cycle re-loads everything from scratch with fresh capsules.

        try:

            if inMessage in (xp.MSG_SCENERY_LOADED, xp.MSG_AIRPORT_LOADED):
                msg_name = "SCENERY_LOADED" if inMessage == xp.MSG_SCENERY_LOADED else "AIRPORT_LOADED"
                self.debug(f"XPluginReceiveMessage: {msg_name} — invalidating lights..", force=True)

                if not self.enabled:
                    return

                if self.followTheGreens is not None:
                    # Destroy all live XPLMInstanceRef objects (turns lights off
                    # and sets every Light.instance back to None).
                    if self.followTheGreens.newLocation():
                        self.notify(message="New location", color=GREEN)
                        self.debug(f"XPluginReceiveMessage: ..{msg_name.lower().replace('_', ' ')}", force=True)
                    else:
                        self.debug(f"XPluginReceiveMessage: ..{msg_name.lower().replace('_', ' not ')}", force=True)

            if inMessage == xp.MSG_PLANE_LOADED:
                msg_name = "PLANE_LOADED"
                self.debug(f"XPluginReceiveMessage: {msg_name} — loading aircraft..", force=True)

                if not self.enabled:
                    return

                if self.followTheGreens is not None:
                    # Destroy all live XPLMInstanceRef objects (turns lights off
                    # and sets every Light.instance back to None).
                    if self.followTheGreens.newAircraft():
                        self.notify(message="New aircraft", color=GREEN)
                        self.debug("XPluginReceiveMessage: ..aircraft loaded", force=True)
                    else:
                        self.debug("XPluginReceiveMessage: ..aircraft not loaded", force=True)

        except Exception:
            # Never let a message handler crash XP.
            print_exc()
            self.debug("XPluginReceiveMessage: exception", force=True)

    # Commands
    def clearanceCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("clearanceCmd: not enabled", force=True)
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("clearanceCmd: available")
            try:
                self.followTheGreens.ui.clearanceReceived()
                self.debug("clearanceCmd: executed")
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
            self.debug("cancelCmd: no FollowTheGreens running")

        return 0

    def okCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("okCmd: not enabled")
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("okCmd: available")
            try:
                self.followTheGreens.ui.cancelReceived("ok command received")
                self.debug("okCmd: executed")
                return 1
            except:
                self.debug("okCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            self.debug("okCmd: no FollowTheGreens running", force=True)

        return 0

    def newGreensCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("newGreensCmd: not enabled")
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("newGreensCmd: available")
            try:
                self.followTheGreens.ui.newGreensReceived()
                self.debug("newGreensCmd: executed")
                self.notify(message="New green requested", color=GREEN)
                return 1
            except:
                self.debug("newGreensCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            self.debug("newGreensCmd: no FollowTheGreens running", force=True)

        return 0

    def bookmarkCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("bookmarkCmd: not enabled")
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("bookmarkCmd: available")
            try:
                self.followTheGreens.bookmark()
                self.debug("bookmarkCmd: executed")
                self.notify(message="Bookmarked", color=GREEN)
                return 1
            except:
                self.debug("bookmarkCmd: exception")
                print_exc()
        elif not self.followTheGreens:
            self.debug("bookmarkCmd: no FollowTheGreens running", force=True)

        return 0

    def _followTheGreensCmd(self, commandRef, phase: int, refCon: Any, alternate: bool = False):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("_followTheGreensCmd: not enabled", force=True)
            return 0

        if not self.followTheGreens:
            try:
                self.followTheGreens = FollowTheGreens(self)
                self.debug("_followTheGreensCmd: created")
            except:
                self.debug("_followTheGreensCmd: exception at creation", force=True)
                print_exc()
                return 0

        if self.followTheGreens and phase == 0:
            self.debug("_followTheGreensCmd: available")
            try:
                self.followTheGreens.start(alternate=alternate)
                self.debug("_followTheGreensCmd: started")
                return 1
            except:
                self.debug("_followTheGreensCmd: exception", force=True)
                print_exc()
                return 0
        elif not self.followTheGreens:
            self.debug(
                "_followTheGreensCmd: Error: could not create FollowTheGreens",
                force=True,
            )

        return 0

    def followTheGreensCmd(self, commandRef, phase: int, refCon: Any):
        return self._followTheGreensCmd(commandRef=commandRef, phase=phase, refCon=refCon, alternate=False)

    def followTheCarCmd(self, commandRef, phase: int, refCon: Any):
        return self._followTheGreensCmd(commandRef=commandRef, phase=phase, refCon=refCon, alternate=True)

    def showTaxiwaysCmd(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("showTaxiwaysCmd: not enabled", force=True)
            return 0

        if not self.showTaxiways:
            try:
                self.showTaxiways = ShowTaxiways(self)
                self.debug("showTaxiwaysCmd: created")
            except:
                self.debug("showTaxiwaysCmd: exception at creation", force=True)
                print_exc()
                return 0

        if self.showTaxiways is not None and phase == 0:
            self.debug("showTaxiwaysCmd: available")

            if self.showTaxiways.ui.mainWindowExists():  # already running, we stop it...
                try:
                    self.showTaxiways.terminate("normal termination")
                    self.debug("showTaxiwaysCmd: ended")
                    return 1
                except:
                    self.debug("showTaxiwaysCmd: exception", force=True)
                    print_exc()
                return 0
            else:
                try:
                    self.showTaxiways.start()
                    self.debug("showTaxiwaysCmd: started")
                    return 1
                except:
                    self.debug("showTaxiwaysCmd: exception", force=True)
                    print_exc()
        elif not self.showTaxiways:
            self.debug("showTaxiwaysCmd: Error: could not create ShowTaxiways")

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
            self.debug("rabbitMode: FollowTheGreens available")
            try:
                self.followTheGreens.rabbitMode(mode)
                self.debug("rabbitMode: set")
                return 1
            except:
                self.debug("rabbitMode: exception", force=True)
                print_exc()
                return 0
        elif not self.followTheGreens:
            self.debug("rabbitMode: Error: could not create FollowTheGreens", force=True)
        return 0

    def rabbitModeAuto(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("rabbitMode: not enabled", force=True)
            return 0

        if self.followTheGreens and phase == 0:
            self.debug("rabbitMode: FollowTheGreens available")
            try:
                self.followTheGreens.rabbitModeAuto()
                self.debug("rabbitMode: set")
                return 1
            except:
                self.debug("rabbitMode: exception", force=True)
                print_exc()
                return 0
        elif not self.followTheGreens:
            self.debug("rabbitMode: Error: could not create FollowTheGreens", force=True)
        return 0

    def hudToggle(self, commandRef, phase: int, refCon: Any):
        # pylint: disable=unused-argument
        if not self.enabled:
            self.debug("hudToggle: not enabled", force=True)
            return 0
        if phase == 0:
            self._hud = not self._hud
            self.followTheGreens.bookmark(f"hud set to {self._hud}")
            return 1
        return 0

    # Data accessors
    def getIndicator(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        return self.followTheGreens.fmcar.indicator if self.followTheGreens is not None and self.followTheGreens.fmcar is not None else 0

    def getRunningStatusCallback(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        return 1 if self.followTheGreens is not None and self.followTheGreens.flightLoop is not None and self.followTheGreens.flightLoop.rabbitRunning else 0

    def getFTGIsHoldingCallback(self, inRefcon):
        # Returns 1 if actually running (lights blinking on taxiways). 0 otherwise.
        return 1 if self.followTheGreens is not None and self.followTheGreens.ui is not None and self.followTheGreens.ui.waiting_for_clearance else 0

    # Future use
    def runningStatusChangedCallback(self, inRefcon):
        """
        This is the callback for our shared data.  Right now we do not react
        to our shared data being chagned. (For "owned" data, we don't
        get a callback like this -- instead, our Accessors are called: MySetData(f|d)Callback.
        """
        pass

    def hud(self, phase, after, refCon):
        if not self._hud or self.followTheGreens is None:
            return
        if self.followTheGreens.flightLoop is None or not self.followTheGreens.flightLoop.rabbitRunning:
            return
        try:
            text_color = GREEN  # default
            MAX_LINES = 4

            fl = self.followTheGreens.flightLoop
            fc = self.followTheGreens.fmcar
            if fc is not None:
                MAX_LINES += 1
            if fl is not None:
                hp = fl.hudPosition()
                text_color = fl.hudColors()  # may be we'll pass other colors after
            LINE = 15 if len(hp) < 3 else hp[2]
            LEFT = max(hp[0], 1)
            TOP = max(hp[1], MAX_LINES * LINE + 1)

            xp.setGraphicsState(0, 1, 0, 0, 0, 0, 0)
            xp.drawString(text_color, LEFT - 3, TOP, "TAXI")  # Title/header
            xp.drawString(CYAN, LEFT + 65, TOP, self.vu)  # cannot change color of VU identifier (standard)
            color = RED if fl.is_late else GREEN  # cannot change color of timing status (meaningful)
            xp.drawString(color, LEFT, TOP - LINE, fl.remaining)  # 1234m, 12:45   indication
            xp.drawString(color, LEFT, TOP - 2 * LINE, f"! {round(fl.dist_to_next_turn):4d}m")  # 1234m
            color = RED if fl.rabbitRunning else AMBER  # cannot change color of rabbit status (meaningful)
            if self.followTheGreens.status.value == "ACTIVE":
                xp.drawString(text_color, LEFT, TOP - 3 * LINE, fl.rabbitText)  # Rabbit status
            else:
                xp.drawString(color, LEFT, TOP - 3 * LINE, self.followTheGreens.status.value)  # FtG status
            if fc is not None:
                xp.drawString(text_color, LEFT, TOP - 4 * LINE, fc.hudText)  # Global status
            dist_speed = self.followTheGreens.aircraft.speed()
            curr_speed = dist_speed
            speed_color = self._speed_color
            if curr_speed > 15.0:
                speed_color = RED
            elif curr_speed > self._speed:
                speed_color = GREEN
            elif curr_speed < self._speed:
                speed_color = AMBER
            elif curr_speed == self._speed or round(curr_speed, 1) == 0.0:
                speed_color = text_color
            self._speed_cnt -= 1
            if self._speed_cnt < 0:
                self._speed = curr_speed
                self._speed_color = speed_color
                self._speed_cnt = 100
            xp.drawString(speed_color, LEFT, TOP - MAX_LINES * LINE, f"SPEED {round(dist_speed, 1)} m/s")  # Aircraft speed
        except:
            xp.drawString((1, 0, 0), 287, 90, "TAXI HUD ERROR")  # almost everything hardcoded..;
            xp.drawString((0.0, 1.0, 1.0), 400, 90, self.vu)
            self.debug("hud: exception", force=True)
            print_exc()

    def _notify(self, phase, after, refCon):
        xp.setGraphicsState(0, 1, 0, 0, 0, 0, 0)
        xp.drawString(self.not_color, 220, 90 + 15, self.not_message)
        self.not_duration = self.not_duration - 1
        if self.not_duration <= 0:
            xp.unregisterDrawCallback(self._notify)

    def notify(self, message: str = "Follow the greens", color: tuple = WHITE, duration: int = 100):
        self.not_message = message
        self.not_color = color
        self.not_duration = duration
        xp.registerDrawCallback(self._notify)
