# User Interface Utility Class
# Creates FTG windows using imgui through xppython3
#
from datetime import datetime
from enum import StrEnum, Enum

from .version import __VERSION__
from .globals import MOVEMENT, logger, get_global
from .cursor import FOLLOW_ME_CARS

try:
    from XPPython3 import xp, xp_imgui
    import imgui
except ImportError:
    print("X-Plane not loaded")


class FTG_COMMANDS(StrEnum):
    START = "START"  # starts session
    CANCEL = "CANCEL"  # terminates FTG
    CLEAR = "CLEAR"  # clearance received, continue
    NEWGREENS = "NEWGREENS"  # new greens/route requested, continue
    BYE = "BYE"  # terminates after completion
    CONTINUE = "CONTINUE"  # no op? similar to close
    OK = "OK"  # no op? similar to close
    CLOSE = "CLOSE"  # close window
    AIRPORT = "AIRPORT"  # change airport


class UI_BUTTON(Enum):
    CLEARANCE = ("Clearance received", FTG_COMMANDS.CLEAR)
    CANCEL = ("Cancel", FTG_COMMANDS.CANCEL)  # terminates FTG
    BYE = ("Bye", FTG_COMMANDS.BYE)  # terminates after completion
    CONTINUE = ("Continue", FTG_COMMANDS.CONTINUE)  # no op? similar to close
    OK = ("OK", FTG_COMMANDS.OK)  # no op? similar to close
    CLOSE = ("Close", FTG_COMMANDS.CLOSE)  # close window
    NEWGREENS = ("New greens", FTG_COMMANDS.NEWGREENS)  # new greens/route requested, continue


RABBIT_SPEEDS = {"no rabbit": 0.00, "slow": 1.00, "medium": 0.50, "fast": 0.16}


class UIIM:

    WIN_WIDTH = 480  # px
    WIN_HEIGHT = 260  # px, height of "small report window", collect window is twice as height

    WIN_TOP = (2 * 260) + 200  # px
    WIN_LEFT = 100  # px

    STAND_COMBO = 20  # show combo from that many item on
    STAND_COMBO_WIDTH = 240  # px

    DESTINATION = -1  # or 0 to select first available destination if any

    LIGHT_MAX = 16  # or 0 to select first available destination if any

    def __init__(self, ftg):
        self.ftg = ftg

        self._airport = "<None>"
        self.alt_airport = self.airport
        self.use_runway_threshold = True
        self.dest_idx = self.DESTINATION if self.DESTINATION < len(self.dest_dep) else -1
        self.deparr = [True, False] if ftg.move == MOVEMENT.DEPARTURE else [False, True]
        self._deparr = ftg.move == MOVEMENT.DEPARTURE

        self.light_type = [True, False]
        self.rabbit_length = 8
        self.rabbit_speed_idx = 2
        self.lights_ahead = 0
        self.use_4d = True

        self.use_car = False
        self.fmcars = list(FOLLOW_ME_CARS.keys()) + ["Other"]
        self.fmcar_idx = 1
        self.use_indicator = True

        self.advanced_options = False

        self.hint = None  # hint is unique
        self.errors = set()

        self.win_pos = get_global("WINDOW_LEFT_TOP", ftg.prefs)
        self.win_pos_new = self.win_pos.copy()
        self.win_autohide = True
        self.win_timeout = 30  # secs

        self.window_flags = 0
        self.window_flags |= imgui.WINDOW_NO_COLLAPSE
        self.window = None
        self._last = datetime.now()
        self._canHide = True

        self._screen_l, self._screen_t, self._screen__r, self._screen__b = xp.getScreenBoundsGlobal()

    #
    # Window management
    #
    @property
    def destination(self) -> str | None:
        destinations = self.dest_dep if self.deparr[0] else self.dest_arr
        return str(destinations[self.dest_idx]) if len(destinations) > 0 and self.dest_idx != -1 else None

    @property
    def timedout(self) -> bool:
        return self.win_autohide and (datetime.now() - self._last).total_seconds() > self.win_timeout

    @property
    def hasWindow(self) -> bool:
        return self.window is not None

    def isVisible(self) -> bool:
        if self.hasWindow:
            return xp.getWindowIsVisible(self.window.windowID) == 1
        return False

    def showWindow(self, canHide: bool = True):
        if self.hasWindow:
            # self.win_pos = self.win_pos_new.copy()
            xp.setWindowIsVisible(self.window.windowID, visible=1)
            self.canHide = canHide
            self.resetTimeout()

    def hideWindow(self):
        if self.hasWindow and self.canHide:
            xp.setWindowIsVisible(self.window.windowID, visible=0)

    def toggleWindowVisibility(self):
        if self.isVisible():
            self.hideWindow()
        else:
            self.showWindow()

    def hideWindowIfTimedout(self, elapsedSinceLastCall: float):
        if self.timedout:
            self.hideWindow()

    @property
    def canHide(self) -> bool:
        return self._canHide

    @canHide.setter
    def canHide(self, canHide):
        if canHide != self._canHide:
            logger.debug(f"allow UI to hide={self._canHide}")
        self._canHide = canHide

    def addError(self, error: str):
        self.errors.add(error)

    def hasErrors(self) -> bool:
        return len(self.errors) > 0

    def getErrors(self) -> bool:
        return "\n".join(self.errors)

    def clearErrors(self):
        self.errors = set()

    def resetTimeout(self):
        self._last = datetime.now()

    def createWindow(self, report: dict = {}):
        if self.hasWindow:
            return
        DEFAULT_TEXT = ["<No text>"]
        l, t, _r, _b = (self._screen_l, self._screen_t, self._screen__r, self._screen__b)
        left_offset = self.win_pos[0]
        top_offset = self.win_pos[1]
        text = report.get("text", DEFAULT_TEXT)
        has_text = text != DEFAULT_TEXT
        h = (len(text) + 4) * 20 if has_text else self.WIN_HEIGHT
        if top_offset < h:
            top_offset = h + 10
        if has_text:  # info with buttons
            self.window = xp_imgui.Window(
                left=l + left_offset,
                top=top_offset,
                right=l + left_offset + self.WIN_WIDTH,
                bottom=top_offset - h,
                visible=1,
                draw=self.report,
                refCon=report,
            )
        else:  # general welcome screen for data collection
            self.use_car = self.ftg.use_car
            self.window = xp_imgui.Window(
                left=l + left_offset,
                top=top_offset,
                right=l + left_offset + self.WIN_WIDTH,
                bottom=top_offset - h,
                visible=1,
                draw=self.collect,
                refCon=report,
            )
        self.canHide = True  # new window can always be hidden
        self.resetTimeout()
        self.window.setTitle("Follow the greens")

    def deleteWindow(self):
        if self.window is None:
            return
        self.window.delete()
        self.window = None
        self.hint = None

    def execute(self, action: FTG_COMMANDS):
        self.ftg.execute(action)

    def terminate(self) -> bool:
        self.deleteWindow()
        return True

    #
    # Data for collection
    #
    @property
    def move(self) -> MOVEMENT:
        return MOVEMENT.DEPARTURE if self._deparr else MOVEMENT.ARRIVAL

    @property
    def guide(self) -> str:
        return "car" if self.use_car else "greens"

    @property
    def use_taxiway_lights(self) -> bool:
        return self.light_type[1]

    @property
    def fmcar(self) -> str | None:
        return str(self.fmcars[self.fmcar_idx]) if len(self.fmcars) > 0 and self.fmcar_idx != -1 else None

    @property
    def rabbit_speed(self) -> float | None:
        return list(RABBIT_SPEEDS.values())[self.rabbit_speed_idx] if self.rabbit_speed_idx != -1 else None

    @property
    def hasAirport(self) -> bool:
        r = self.ftg is not None and self.ftg.airport is not None
        if r:  # check if airport has changed
            if self.ftg.airport.icao != self._airport:
                self._airport = self.ftg.airport.icao
                self.alt_airport = self.airport
                self.resetDestination()
        return r

    @property
    def airport_ok(self) -> bool:
        if self.hasAirport:
            return self.ftg.airport.usable()
        return False

    @property
    def airport(self):
        return self.ftg.airport.icao if self.hasAirport else "<None>"

    @property
    def dest_dep(self):
        return sorted(self.ftg.airport.runways.keys()) if self.hasAirport else []

    @property
    def dest_arr(self):
        return sorted(self.ftg.airport.ramps.keys()) if self.hasAirport else []

    def resetDestination(self):
        self.dest_idx = self.DESTINATION if self.DESTINATION < len(self.dest_dep) else -1

    @property
    def info(self):
        return f"{self.airport}, {self.move}, {self.destination}, {self.guide}"

    #
    # Reporting window
    #
    def show_help_marker(self, desc):
        imgui.text_disabled("(?)")
        if imgui.is_item_hovered():
            imgui.begin_tooltip()
            imgui.push_text_wrap_pos(imgui.get_font_size() * 35.0)
            imgui.text_unformatted(desc)
            imgui.pop_text_wrap_pos()
            imgui.end_tooltip()

    def radioButtons(self, prompts: list, values: list) -> list:
        v = []
        for i in range(len(prompts)):
            v.append(False)
            v[i] = imgui.radio_button(prompts[i], values[i])
            imgui.same_line()
        imgui.new_line()
        return v if any(v) else values

    def collect(self, _windowID, refCon):
        if self.window is None:
            return

        l, t, _r, _b = (self._screen_l, self._screen_t, self._screen__r, self._screen__b)
        p = xp.getWindowGeometry(windowID=self.window.windowID)  # left, top, right, bottom
        left_offset = p[0]
        top_offset = p[1]
        h = self.WIN_HEIGHT if not self.advanced_options else 2 * self.WIN_HEIGHT
        if top_offset < h:
            top_offset = h + 10
        xp.setWindowGeometry(windowID=self.window.windowID, left=l + left_offset, top=top_offset, right=l + left_offset + self.WIN_WIDTH, bottom=top_offset - h)

        # Most "big" widgets share a common width settings by default.
        imgui.push_item_width(imgui.get_window_width() * 0.65)
        # Use 2/3 of the space for widgets and 1/3 for labels (default)
        imgui.push_item_width(imgui.get_font_size() * -12)
        # Use fixed width for labels (by passing a negative value), the rest goes to widgets. We choose a width proportional to our font size.

        #
        # 1. LOCATION
        #
        # 1.1 AIRPORT
        if self.airport == "<None>" or not self.airport_ok:
            imgui.text(f"{self.airport}   Airport ICAO  ")
            self.addError("Airport is invalid")
        else:
            imgui.text(f"At {self.airport}")

        imgui.same_line()
        if imgui.button(label="Change.."):
            imgui.open_popup("Change Airport")
        if imgui.begin_popup_modal(title="Change Airport", visible=None, flags=imgui.WINDOW_ALWAYS_AUTO_RESIZE)[0]:
            imgui.push_item_width(60)
            changed, self.alt_airport = imgui.input_text(label="New airport ICAO", value=self.alt_airport, buffer_length=6)
            imgui.pop_item_width()
            if imgui.button(label="OK", width=80, height=0):
                self.execute(FTG_COMMANDS.AIRPORT)
                imgui.close_current_popup()
            imgui.set_item_default_focus()
            imgui.same_line()
            if imgui.button(label="Cancel", width=80, height=0):
                imgui.close_current_popup()
            imgui.end_popup()

        # 1.2 DEPARTURE/ARRIVAL
        self.deparr = self.radioButtons(["Departure", "Arrival"], self.deparr)

        # 1.3 DESTINATION
        if self._deparr != self.deparr[0]:
            self._deparr = self.deparr[0]
            self.dest_idx = self.DESTINATION if self.DESTINATION < len(self.dest_dep) else -1
        destinations = self.dest_dep if self.deparr[0] else self.dest_arr
        destinations = destinations.copy()
        if self.deparr[1] and len(self.dest_arr) > self.STAND_COMBO:
            imgui.push_item_width(self.STAND_COMBO_WIDTH)
            clicked, self.dest_idx = imgui.combo("Stand", self.dest_idx, self.dest_arr)
            imgui.pop_item_width()
        else:
            if imgui.button(label="Select runway.." if self.deparr[0] else "Select stand.."):
                imgui.open_popup("destination")
            imgui.same_line()
            imgui.text_unformatted("<None>" if self.dest_idx == -1 else destinations[self.dest_idx])
            if imgui.begin_popup("destination"):
                imgui.text("Runway" if self.deparr[0] else "Stand")
                imgui.separator()
                for i in range(len(destinations)):
                    _, destinations[i] = imgui.selectable(destinations[i])
                    if destinations[i]:
                        self.dest_idx = i
                imgui.end_popup()

        # 1.4 alt
        clicked, self.use_car = imgui.checkbox(label="Use Follow Me car instead of taxiway green lights", state=self.use_car)

        # 1.5 GO!
        imgui.spacing()
        imgui.spacing()
        if self.dest_idx != -1:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.8, 0.1, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.0, 0.8, 0.1, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.0, 1.0, 0.1, 1.0)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.4, 0.4, 0.4, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.4, 0.4, 0.4, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.4, 0.4, 0.4, 1.0)
        if imgui.button(label="Follow the " + self.guide):
            if self.dest_idx != -1:
                self.hideWindow()
                self.execute(FTG_COMMANDS.START)
                self.hint = None
            else:
                self.hint = "Select " + ("runway" if self._deparr else "destination stand")

        imgui.pop_style_color(3)
        imgui.same_line()
        self.show_help_marker("Press to start")
        imgui.spacing()
        imgui.spacing()

        clicked, self.advanced_options = imgui.checkbox(label="Show advanced options", state=self.advanced_options)

        #
        # 2. Options
        #
        if self.advanced_options:
            #
            # 2.1 FTG Options
            #
            show, _ = imgui.collapsing_header("Follow the greens options", visible=not self.use_car)
            if show:
                imgui.push_item_width(240)
                changed, self.rabbit_length = imgui.slider_int("Rabbit length", self.rabbit_length, 0, self.LIGHT_MAX)
                changed, self.rabbit_speed_idx = imgui.slider_int("Rabbit speed", self.rabbit_speed_idx, 0, 3)  # none, slow, normal, fast
                imgui.same_line()
                imgui.text("(" + list(RABBIT_SPEEDS.keys())[self.rabbit_speed_idx] + f" (~ {self.rabbit_speed}s))")
                changed, self.lights_ahead = imgui.slider_int("Lights ahead", self.lights_ahead, 0, self.LIGHT_MAX)
                imgui.same_line()
                self.show_help_marker("0 light ahead means show greens to next stop")
                imgui.pop_item_width()
                clicked, self.use_4d = imgui.checkbox(label="Use 4D", state=self.use_4d)
                self.light_type = self.radioButtons(["Omni directional", "Taxiway"], self.light_type)

            #
            # 2.1 FMC Options
            #
            show, _ = imgui.collapsing_header("Follow Me Car options", visible=self.use_car)
            if show:
                clicked, self.fmcar_idx = imgui.combo("Model", self.fmcar_idx, self.fmcars)
                # imgui.same_line()
                # show_help_marker(
                #     'Refer to the "Combo" section below for an explanation of the full BeginCombo/EndCombo API, and demonstration of various flags.\n'
                # )
                clicked, self.use_indicator = imgui.checkbox(label="Use indicator", state=self.use_indicator)
                imgui.same_line()
                self.show_help_marker("An Indicator is a sign board on top of car to indicate direction and other messages")
                clicked, self.use_4d = imgui.checkbox(label="Use 4D", state=self.use_4d)

            #
            # 2.3 Options
            #
            show, _ = imgui.collapsing_header("Plugin options")
            if show:
                # l, t, _r, _b = (0, 1620, 3840, 0)
                # imgui.text("Window top left position (from screen bottom left)")
                # changed, self.win_pos_new[0] = imgui.slider_int("From Left", self.win_pos_new[0], 0, _r - self.WIN_LEFT - 10)
                # imgui.same_line()
                # self.show_help_marker("Top of window from left of screen")
                # changed, self.win_pos_new[1] = imgui.slider_int("From Bottom", self.win_pos_new[1], int(10 + 2 * self.WIN_HEIGHT), t)
                # imgui.same_line()
                # self.show_help_marker("Top of window from bottom of screen")
                # imgui.spacing()
                checked, self.win_autohide = imgui.checkbox(label="Auto Hide", state=self.win_autohide)
                if self.win_autohide:
                    changed, self.win_timeout = imgui.slider_int("Hide timeout (seconds)", self.win_timeout, 10, 120)
                imgui.spacing()
                if self.deparr[0]:
                    checked, self.use_runway_threshold = imgui.checkbox(label="Use runway threshold", state=self.use_runway_threshold)

        self.status(show_version=self.advanced_options)

    #
    # Data collection window
    #
    def status(self, show_version: bool = True):
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()

        if self.hasErrors():
            imgui.text_colored(self.getErrors(), r=1.0, g=0.0, b=0.0)

        imgui.spacing()

        if self.hint is not None:
            imgui.text_colored("Hint: " + self.hint, r=0.0, g=0.8, b=0.8)

        if show_version:
            imgui.spacing()
            imgui.text("Follow the greens rel. " + __VERSION__)

    def report(self, _windowID, refCon):
        # refCon = {
        #     "text": ["bla"],
        #     "buttons": [UI_BUTTON.OK],
        #     "error": "bla",
        #     "hint": "bla",
        # }
        text = refCon.get("text", ["<No text>"])
        imgui.push_item_width(imgui.get_font_size() * -12)
        imgui.text_wrapped("\n".join(text))
        imgui.spacing()
        imgui.spacing()

        buttons = refCon.get("buttons", [UI_BUTTON.OK])
        for b in buttons:
            p = b.value[0]
            w = 80 if len(p) < 12 else 150
            if imgui.button(label=p, width=w, height=0):
                self.execute(b.value[1])
                self.resetTimeout()
            imgui.same_line()

        imgui.new_line()

        self.hint = refCon.get("hint", self.hint)
        e = refCon.get("error")
        if e is not None:
            if type(e) in [list, tuple]:
                for m in e:
                    self.addError(m)
            else:
                self.addError(e)
        self.status()


# Options to pass
# Greens
# - speed, length
# - light type
# Car
# - Model
# - Indicator y/n OK
# Global
# - 4D y/n
# - Position: OK
# - Autohide timeout: OK
# - Use threshold: OK
