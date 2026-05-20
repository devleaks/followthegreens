from datetime import datetime
from enum import StrEnum

from followthegreens.geo import destination

from .version import __VERSION__
from .globals import logger

try:
    from XPPython3 import xp, xp_imgui
    import imgui
except ImportError:
    print("X-Plane not loaded")


class FTG_COMMANDS(StrEnum):
    CLEAR = "CLEAR"  # clearance received, continue
    CANCEL = "CANCEL"  # terminates FTG
    START = "START"  # starts session
    AIRPORT = "AIRPORT"  # change airport
    NEWGREENS = "NEWGREENS"  # new greens/route requested, continue
    BYE = "BYE"  # terminates after completion
    OK = "OK"  # no op? similar to close
    CLOSE = "CLOSE"  # close window


class UIIM:

    WIN_WIDTH = 480  # px
    WIN_HEIGHT = 520  # px

    STAND_COMBO = 20  # show combo from that many item on
    STAND_COMBO_WIDTH = 240  # px

    DESTINATION = -1  # or 0 to select first available destination if any

    LIGHT_MAX = 16  # or 0 to select first available destination if any

    def __init__(self, ftg):
        self.ftg = ftg

        self._airport = "<None>"
        self.alt_airport = self.airport
        self.runway_threshold = True
        self.dest_idx = self.DESTINATION if self.DESTINATION < len(self.dest_dep) else -1
        self.deparr = [True, False]
        self._deparr = True

        self.lights = [True, False]
        self.rabbit_length = 8
        self.rabbit_speed = 2
        self.lights_ahead = 0
        self.use_4d = True

        self.use_car = False
        self.fmcars = ["Car 1", "Car 2", "Other"]
        self.fmcar_idx = 0
        self.use_indicator = True

        self.hint = None
        self.text = None

        self.win_pos = [100, 600]
        self.win_autohide = True
        self.win_timeout = 30  # secs

        self.window_flags = 0
        self.window_flags |= imgui.WINDOW_NO_COLLAPSE
        self.window = None
        self.imgui_refcon = {}
        self._last = datetime.now()
        self.todo = FTG_COMMANDS.OK

    @property
    def destination(self) -> str | None:
        destinations = self.dest_dep if self.deparr[0] else self.dest_arr
        return str(destinations[self.dest_idx]) if len(destinations) > 0 and self.dest_idx != -1 else None

    @property
    def move(self) -> str:
        return "DEPARTURE" if self._deparr else "ARRIVAL"

    @property
    def guide(self) -> str:
        return "car" if self.use_car else "greens"

    @property
    def fmcar(self) -> str | None:
        return str(self.fmcars[self.fmcar_idx]) if len(self.fmcars) > 0 and self.fmcar_idx != -1 else None

    @property
    def timedout(self) -> bool:
        return self.win_autohide and (datetime.now() - self._last).total_seconds() > self.win_timeout

    def execute(self, action: FTG_COMMANDS):
        self.ftg.execute(action)

    def toggleVisibility(self):
        if self.window is None:
            self.activateWindow()
        else:
            self.deleteWindow()

    def hideWindowIfTimedout(self, elapsedSinceLastCall: float):
        if self.timedout:
            self.deleteWindow()

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

    @property
    def hasAirport(self) -> bool:
        r = self.ftg is not None and self.ftg.airport is not None
        if r:  # check if airport has changed
            if self.ftg.airport.icao != self._airport:
                self._airport = self.ftg.airport.icao
                self.resetDestination()
        return r

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

    def resetTimeout(self):
        self._last = datetime.now()

    def createWindow(self, report: dict | None = None):
        if self.window is not None:
            return
        l, t, _r, _b = xp.getScreenBoundsGlobal()
        left_offset = self.win_pos[0]
        top_offset = self.win_pos[1]
        if type(report) is dict:
            self.imgui_refcon = report
            self.window = xp_imgui.Window(
                left=l + left_offset,
                top=top_offset + self.WIN_HEIGHT,
                right=l + left_offset + self.WIN_WIDTH,
                bottom=top_offset,
                visible=1,
                draw=self.report,
                refCon=self.imgui_refcon,
            )
        else:
            self.use_car = self.ftg.alternate
            self.window = xp_imgui.Window(
                left=l + left_offset,
                top=top_offset + self.WIN_HEIGHT,
                right=l + left_offset + self.WIN_WIDTH,
                bottom=top_offset,
                visible=1,
                draw=self.collect,
                refCon=self.imgui_refcon,
            )
        self.resetTimeout()
        self.window.setTitle("Follow the greens")

    def activateWindow(self):
        if self.window is None:
            self.createWindow(report=self.imgui_refcon)
        self.resetTimeout()

    def deleteWindow(self):
        if self.window is None:
            return
        self.window.delete()
        self.window = None
        self.hint = None

    def collect(self, _windowID, refCon):
        if self.window is None:
            return
        # Most "big" widgets share a common width settings by default.
        imgui.push_item_width(imgui.get_window_width() * 0.65)
        # Use 2/3 of the space for widgets and 1/3 for labels (default)
        imgui.push_item_width(imgui.get_font_size() * -12)
        # Use fixed width for labels (by passing a negative value), the rest goes to widgets. We choose a width proportional to our font size.

        #
        # 1. LOCATION
        #
        # 1.1 AIRPORT
        if self.airport == "<None>":
            imgui.text(f"{self.airport}   Airport ICAO  ")
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
        else:
            imgui.text(f"At {self.airport}")

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
        clicked, self.use_car = imgui.checkbox(label="Use Follow Me car instead of greens", state=self.use_car)

        # 1.5 GO!
        imgui.spacing()
        imgui.spacing()
        if self.dest_idx != -1:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.0, 0.8, 0.1, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.0, 0.8, 0.1, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.0, 0.8, 0.1, 1.0)
        else:
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.4, 0.4, 0.4, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.4, 0.4, 0.4, 1.0)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.4, 0.4, 0.4, 1.0)
        if imgui.button(label="Follow the " + self.guide):
            if self.dest_idx != -1:
                self.execute(FTG_COMMANDS.START)
                self.hint = None
            else:
                self.hint = "Select " + ("runway" if self._deparr else "destination stand")

        imgui.pop_style_color(3)
        imgui.same_line()
        self.show_help_marker("Press to start")
        imgui.spacing()
        imgui.spacing()

        #
        # 2. FTG Options
        #
        show, _ = imgui.collapsing_header("Follow the greens options", visible=not self.use_car)
        if show:
            imgui.push_item_width(240)
            changed, self.rabbit_length = imgui.slider_int("Rabbit length", self.rabbit_length, 0, self.LIGHT_MAX)
            changed, self.rabbit_speed = imgui.slider_int("Rabbit speed", self.rabbit_speed, 0, 3)  # none, slow, normal, fast
            imgui.same_line()
            imgui.text("(" + ["no rabbit", "slow", "medium", "fast"][self.rabbit_speed] + ")")
            changed, self.lights_ahead = imgui.slider_int("Lights ahead", self.lights_ahead, 0, self.LIGHT_MAX)
            imgui.same_line()
            self.show_help_marker("0 light ahead means show greens to next stop")
            imgui.pop_item_width()
            clicked, self.use_4d = imgui.checkbox(label="Use 4D", state=self.use_4d)
            self.lights = self.radioButtons(["Omni directional", "Taxiway"], self.lights)

        #
        # 3. FMC Options
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
        # 4. Options
        #
        show, _ = imgui.collapsing_header("Plugin options")
        if show:
            imgui.text("Window top left position (from screen bottom left)")
            changed, self.win_pos[0] = imgui.slider_int("From Left", self.win_pos[0], 0, 600)
            imgui.same_line()
            self.show_help_marker("Top of window from left of screen")
            changed, self.win_pos[1] = imgui.slider_int("From Bottom", self.win_pos[1], 0, 600)
            imgui.same_line()
            self.show_help_marker("Top of window from bottom of screen")
            imgui.spacing()
            checked, self.win_autohide = imgui.checkbox(label="Auto Hide", state=self.win_autohide)
            changed, self.win_timeout = imgui.slider_int("Hide timeout (seconds)", self.win_timeout, 1, 60)
            imgui.spacing()
            checked, self.runway_threshold = imgui.checkbox(label="Use runway threshold", state=self.runway_threshold)

        self.status()

    def report(self, _windowID, refCon):
        text = refCon.get("text", "<No text>")
        imgui.push_item_width(imgui.get_font_size() * -12)
        imgui.text("\n".join(text))
        imgui.spacing()
        imgui.spacing()

        if refCon.get("clearance", False):
            if imgui.button(label="Clearance received", width=150, height=0):
                self.execute(FTG_COMMANDS.CLEAR)
                self.resetTimeout()
            imgui.same_line()

        if refCon.get("newgreens", False):
            if imgui.button(label="New " + ("route" if self.use_car else "greens"), width=80, height=0):
                self.execute(FTG_COMMANDS.NEWGREENS)
                self.resetTimeout()
            imgui.same_line()

        if refCon.get("cancel", False):
            if imgui.button(label="Cancel", width=80, height=0):
                self.execute(FTG_COMMANDS.CANCEL)
                self.resetTimeout()
                return

        if refCon.get("ok", False):
            if imgui.button(label="OK", width=80, height=0):
                self.execute(FTG_COMMANDS.OK)
                self.resetTimeout()
            imgui.same_line()

        if refCon.get("close", False):
            if imgui.button(label="Close", width=80, height=0):
                self.execute(FTG_COMMANDS.CLOSE)
                self.resetTimeout()
            imgui.same_line()

        if refCon.get("bye", False):
            if imgui.button(label="Terminate", width=80, height=0):
                self.execute(FTG_COMMANDS.BYE)
                self.resetTimeout()
            imgui.same_line()

        imgui.new_line()
        self.status()

    def status(self):
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.spacing()
        imgui.text("DEMO PURPOSE ONLY NOTHING IS DONE WITH DATA IN THIS FORM")
        imgui.spacing()
        # imgui.text("Safely close this window to cancel actions")
        # imgui.spacing()
        if self.hint is not None:
            imgui.text("Hint: " + self.hint)
        imgui.spacing()
        imgui.text("Follow the greens rel. " + __VERSION__)
