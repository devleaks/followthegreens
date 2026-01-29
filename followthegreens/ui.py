# User Interface Utility Class
# Creates FTG windows.
#
from random import random

try:
    import xp
except ImportError:
    print("X-Plane not loaded")

from .globals import get_global, logger, MOVEMENT, GOOD

# Some texts we need to recognize. May be later translated.
CLOSE_TEXT = "Close"
CANCEL_TEXT = "Cancel Follow the greens"
FINISH_TEXT = "Finish"
CLEARANCE_TEXT = "Clearance received"
CANCELSHORT_TEXT = "Cancel"
CONTINUE_TEXT = "Continue"
IAMLOST_TEXT = "New green please"
NEWDEST_TEXT = "New destination"


SPECIAL_DEBUG = False


class UIUtil:
    def __init__(self, ftg):
        self.ftg = ftg
        self.mainWindow = None
        self.icao = None
        self.dest = None
        self.destinationIdx = 0
        self.validDestinations = []
        self.validDestIdxs = []
        self.linetops = []
        self.strHeight = 0
        self._canHide = True
        self.displayTime = 0
        self.waiting_for_clearance = False
        self.mainwindow_autohide = get_global("MAINWINDOW_AUTOHIDE", self.ftg.prefs)
        self.mainwindow_display_time = get_global("MAINWINDOW_DISPLAY_TIME", self.ftg.prefs)

    def window(self, strings, btns):
        if self.mainWindow and "widgetID" in self.mainWindow.keys():  # We create a new window each time we are called.
            xp.destroyWidget(self.mainWindow["widgetID"], 1)
            self.mainWindow = None

        widgetWindow = {
            "widgetID": None,
            "widgets": {},
        }  # the ID of the main window containing all other widgets  # hash of all child widgets we care about
        self.mainWindow = widgetWindow

        self.fontID = xp.Font_Proportional
        _w, strHeight, _ignore = xp.getFontDimensions(self.fontID)
        self.strHeight = strHeight
        linespace = 2.0

        self.wLeft = get_global("MAINWINDOW_FROM_LEFT", self.ftg.prefs)
        self.wBottom = get_global("MAINWINDOW_FROM_BOTTOM", self.ftg.prefs)
        self.wTop = self.wBottom + get_global("MAINWINDOW_HEIGHT", self.ftg.prefs) + len(strings) * int(linespace * self.strHeight)
        self.wRight = self.wLeft + get_global("MAINWINDOW_WIDTH", self.ftg.prefs)
        widgetCenter = int(self.wLeft + (self.wRight - self.wLeft) / 2)

        widgetWindow["widgetID"] = xp.createWidget(
            self.wLeft,
            self.wTop,
            self.wRight,
            self.wBottom,
            0,
            "Follow the greens",
            1,
            0,
            xp.WidgetClass_MainWindow,
        )

        xp.addWidgetCallback(widgetWindow["widgetID"], self.cbMainWindow)

        # xp.setWidgetProperty(widgetWindow['widgetID'], xp.Property_MainWindowType, xp.MainWindowStyle_Translucent)
        xp.setWidgetProperty(widgetWindow["widgetID"], xp.Property_MainWindowHasCloseBoxes, 1)

        # Add five label / editable text fields.
        # We determine placement based on the size of the font.
        # We'll "keep" the text fields so we can interact with them

        # Display lines of strings, going upward...
        self.linetops = []
        for s in strings:
            strWidth = xp.measureString(self.fontID, s)
            left = self.wLeft + 10
            right = int(left + strWidth)
            top = int(self.wTop - 35 - len(self.linetops) * linespace * self.strHeight)
            bottom = int(top - self.strHeight)
            self.linetops.append([top, right])  # where line finishes
            xp.createWidget(
                left,
                top,
                right,
                bottom,
                1,
                s,
                0,
                widgetWindow["widgetID"],
                xp.WidgetClass_Caption,
            )

        # Line of buttons
        buttons, bwidth = self.mkButtons(btns)
        top = int(self.wBottom + 30)
        bottom = int(top - 1.2 * self.strHeight)
        left0 = int(widgetCenter - bwidth / 2)
        for k, btn in buttons.items():
            left = left0 + btn["left"]
            right = left0 + btn["right"]
            widgetWindow["widgets"][btn["name"]] = xp.createWidget(
                left,
                top,
                right,
                bottom,
                1,
                btn["text"],
                0,
                widgetWindow["widgetID"],
                xp.WidgetClass_Button,
            )
            if btn["cb"]:
                xp.addWidgetCallback(widgetWindow["widgets"][btn["name"]], btn["cb"])

        self.canHide = True  # new window can always be hidden
        return widgetWindow["widgetID"]

    @property
    def canHide(self) -> bool:
        return self._canHide

    @canHide.setter
    def canHide(self, canHide):
        if canHide != self._canHide:
            logger.debug(f"allow UI to hide={self._canHide}")
        self._canHide = canHide

    def mkButtons(self, btns):
        buttons = {}
        prev = False

        for b, cb in btns.items():
            buttons[b] = {}
            if not prev:
                buttons[b]["left"] = 0
            else:
                buttons[b]["left"] = prev["right"] + 10  # inter-button
            buttons[b]["name"] = "btn" + str(len(buttons.keys()))
            buttons[b]["text"] = b
            buttons[b]["cb"] = cb
            buttons[b]["swidth"] = int(xp.measureString(self.fontID, b))
            buttons[b]["right"] = int(buttons[b]["left"] + buttons[b]["swidth"] + 10)  # inside button
            prev = buttons[b]

        return (buttons, prev["right"])  # total width of all buttons

    def mainWindowExists(self):
        return self.mainWindow is not None and "widgetID" in self.mainWindow.keys()

    def isMainWindowVisible(self):
        if self.mainWindowExists():
            return xp.isWidgetVisible(self.mainWindow["widgetID"])
        return False

    def showMainWindow(self, canHide=True):
        if SPECIAL_DEBUG:
            logger.debug(f"showMainWindow canHide={self.canHide}")
        if self.mainWindowExists():
            xp.showWidget(self.mainWindow["widgetID"])
            self.canHide = canHide
            self.displayTime = 0

    def hideMainWindowIfOk(self, elapsed=0):
        # We always hide it on request, even if canHide is False
        self.displayTime += elapsed
        if self.mainwindow_autohide and self.displayTime > self.mainwindow_display_time and self.canHide:
            if SPECIAL_DEBUG:
                logger.debug("auto hiding UI")
            self.hideMainWindow()
        else:
            if SPECIAL_DEBUG:
                logger.debug(f"UI not allowed to hide (canHide={self.canHide}, elapsed={round(self.displayTime, 1)} < {self.mainwindow_display_time})")

    def hideMainWindow(self):
        # We always hide it on request, even if canHide is False
        if self.mainWindowExists():
            xp.hideWidget(self.mainWindow["widgetID"])

    def toggleVisibilityMainWindow(self):
        if self.mainWindowExists():
            if SPECIAL_DEBUG:
                logger.debug(f"isMainWindowVisible(): {self.isMainWindowVisible()}.")
            if self.isMainWindowVisible():
                self.hideMainWindow()
            else:
                self.showMainWindow()

    def destroyMainWindow(self):
        if self.mainWindowExists():
            xp.hideWidget(self.mainWindow["widgetID"])
            xp.destroyWidget(self.mainWindow["widgetID"], 1)
            self.mainWindow = None

    #
    #
    # MAIN WINDOW prompts
    #
    def greetings(self, text="Good %s."):
        h = self.ftg.hourOfDay()
        logger.debug(f"bye: {h}.")
        ss = list(GOOD.keys())[-1]  # last one is good night, from 0-4 and 20-24.
        for k, v in GOOD.items():
            if h > v:
                ss = k
        logger.debug(f"bye: {h}h, good {ss}")
        return text % ss

    def promptForAirport(self):
        # Create a window to prompt for airport ICAO code
        prompt = "Please enter this airport ICAO code"
        widgetWindow = self.window(
            ["Welcome. We could not find the airport where you are located.", prompt],
            {"Follow the greens": self.cbAirport, CANCELSHORT_TEXT: self.cbCancel},
        )

        left = self.linetops[1][1] + 10
        right = int(left + 100)
        top = self.linetops[2][0]
        bottom = int(top - self.strHeight)
        widget = xp.createWidget(
            left,
            top,
            right,
            bottom,
            1,
            "icao",
            0,
            self.mainWindow["widgetID"],
            xp.WidgetClass_TextField,
        )
        self.mainWindow["widgets"]["icao"] = widget

        return widgetWindow

    def promptForDestination(self, status=""):
        # Create a window to prompt for a local airport destination, either a runway or a parking position
        move = self.ftg.move
        welcome = "Welcome. We could not guess where you want to taxi."
        if status != "":
            welcome = status + " Try again. Where do you want to taxi?"

        button = None
        prompt = None
        text = None
        if move == MOVEMENT.DEPARTURE:
            self.validDestinations = self.ftg.airport.getDestinations(MOVEMENT.DEPARTURE)
            prompt = "Please enter runway for departure"
            button = "It is an arrival"
            text = "RWY/HLD"
        else:
            self.validDestinations = self.ftg.airport.getDestinations(MOVEMENT.ARRIVAL)
            prompt = "Please enter stand number for arrival"
            button = "It is a departure"
            text = "RAMP"

        if len(self.validDestinations) > 0:
            self.validDestinations.sort()
            self.validDestIdxs = list(map(lambda x: x[0].upper(), self.validDestinations))
            self.destinationIdx = int(random() * len(self.validDestinations))
            text = self.validDestinations[self.destinationIdx]

        widgetWindow = self.window(
            [
                welcome,
                prompt,
                "Click inside the text box and use UP and DOWN arrow to cycle through values.",
            ],
            {"Follow the greens": self.cbDestination, CANCELSHORT_TEXT: self.cbCancel},
        )

        left = self.linetops[1][1] + 10
        right = int(left + 100)
        top = self.linetops[1][0] - 2
        bottom = int(top - self.strHeight)
        widget = xp.createWidget(
            left,
            top,
            right,
            bottom,
            1,
            text,
            0,
            self.mainWindow["widgetID"],
            xp.WidgetClass_TextField,
        )
        self.mainWindow["widgets"]["dest"] = widget
        xp.addWidgetCallback(self.mainWindow["widgets"]["dest"], self.cbUpDown)

        strWidth = xp.measureString(self.fontID, button)
        left = right + 20  # after the above textfield
        right = int(left + 1.1 * strWidth)
        # top = int(self.wTop - 40 - self.strHeight)
        # bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, button, 0, widgetWindow, xp.WidgetClass_Button)
        self.mainWindow["widgets"]["move"] = widget
        xp.addWidgetCallback(self.mainWindow["widgets"]["move"], self.cbMovement)

        return widgetWindow

    def followTheGreen(self):
        btns = {CANCEL_TEXT: self.cbCancel}
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        return self.window(
            [
                "Follow the greens.",
                "(You can close this window with the little x in the above window title bar.)",
            ],
            btns,
        )

    def promptForClearance(self, intro: list = []):
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        btns = {CLEARANCE_TEXT: self.cbClearance, CANCELSHORT_TEXT: self.cbCancel}
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        self.waiting_for_clearance = True
        return self.window(
            intro
            + [
                "Follow the greens until you encounter a line of red stop lights.",
                "At the stop lights, contact TOWER for clearance. Press Clearance received when cleared.",
            ],
            btns,
        )

    def tryAgain(self, text):
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        btns = {NEWDEST_TEXT: self.cbNewDestination, CANCEL_TEXT: self.cbCancel}
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        return self.window(
            [
                "We could not find a route to your destination.",
                "Get closer to taxiways and try again.",
            ],
            btns,
        )

    def promptForDeparture(self):
        # In front of the last stopbar, ask to ask for clearance for departure and press continue when clearance obtained.
        self.waiting_for_clearance = True
        return self.window(
            [
                "Follow the greens until you encounter a line of red stop lights at departure runway.",
                "Press Clearance received when cleared for runway.",
            ],
            {CLEARANCE_TEXT: self.cbClearance, CANCELSHORT_TEXT: self.cbCancel},
        )

    def promptForParked(self):
        btns = {CONTINUE_TEXT: self.cbClearance, CANCELSHORT_TEXT: self.cbCancel}
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        return self.window(
            [
                "Follow the greens to the designated parking area.",
                "Press Continue when parked.",
            ],
            btns,
        )

    def bye(self):
        return self.window(
            ["You have reached your destination.", self.greetings("Enjoy your %s.")],
            {FINISH_TEXT: self.cbBye},
        )

    def enjoy(self):
        return self.window(
            [
                "All taxiways in the network are lit. Press " + FINISH_TEXT + " to hide them.",
                self.greetings("Enjoy your %s."),
            ],
            {FINISH_TEXT: self.cbBye},
        )

    def sorry(self, message):
        # Open a window with explanation.
        return self.window(
            [
                "We are sorry. We cannot provide Follow the greens service at this airport.",
                message,
            ],
            {CLOSE_TEXT: self.cbClose},
        )

    #
    #
    # CALLBACK for buttons and caption
    #
    def cbMainWindow(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Router for all window events (when button pressed)
        if inMessage == xp.Message_CloseButtonPushed:
            xp.hideWidget(self.mainWindow["widgetID"])
            return 1
        return 0

    def cbAirport(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if "icao" in self.mainWindow["widgets"].keys():
                self.icao = xp.getWidgetDescriptor(self.mainWindow["widgets"]["icao"])
                logger.debug(f"airport: {self.icao}")
                xp.hideWidget(self.mainWindow["widgetID"])
                nextWindow = self.ftg.getDestination(self.icao)
                xp.showWidget(nextWindow)
            return 1
        return 0

    def cbUpDown(self, message, widgetID, param1, param2):
        # We intercept some keypress we are interested in _first_
        if message == xp.Msg_KeyPress and not (param1[1] & xp.UpFlag):
            if param1[2] == xp.VK_DOWN or (param1[2] == xp.VK_N and param1[1] & xp.ControlFlag):
                self.destinationIdx = (self.destinationIdx + 1) % len(self.validDestinations)
                xp.setWidgetDescriptor(widgetID, self.validDestinations[self.destinationIdx])
                return 1
            if param1[2] == xp.VK_UP or (param1[2] == xp.VK_P and param1[1] & xp.ControlFlag):
                xp.setWidgetDescriptor(widgetID, self.validDestinations[self.destinationIdx])
                self.destinationIdx = (self.destinationIdx - 1) % len(self.validDestinations)
                return 1
            if param1[2] >= xp.VK_0 and param1[2] <= xp.VK_Z:
                # thanks for the hint: https://forums.x-plane.org/index.php?/forums/topic/238447-best-ui-for-list-of-value/&tab=comments#comment-2130991
                c = chr(param1[2]).upper()
                idx = -1
                try:
                    idx = self.validDestIdxs.index(c)
                except ValueError:
                    idx = -1
                if idx > -1:
                    self.destinationIdx = idx
                    xp.setWidgetDescriptor(widgetID, self.validDestinations[self.destinationIdx])
                return 1
            # if any other key as been pressed, we ignore it.
            return 1
        return 0

    def cbDestination(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if "dest" in self.mainWindow["widgets"].keys():
                self.dest = xp.getWidgetDescriptor(self.mainWindow["widgets"]["dest"])
                logger.debug(f"destination: {self.dest}")
                xp.hideWidget(self.mainWindow["widgetID"])
                nextWindow = self.ftg.followTheGreen(self.dest)
                xp.showWidget(nextWindow)
            return 1
        return 0

    def cbNewDestination(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            nextWindow = self.promptForDestination()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbNewGreen(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if not self.dest:
                return 0
            xp.hideWidget(self.mainWindow["widgetID"])
            nextWindow = self.ftg.newGreen(self.dest)
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbMovement(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            if self.ftg.move == MOVEMENT.DEPARTURE:
                self.ftg.move = MOVEMENT.ARRIVAL
            else:
                self.ftg.move = MOVEMENT.DEPARTURE
            nextWindow = self.promptForDestination()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbClearance(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            self.waiting_for_clearance = False
            nextWindow = self.ftg.nextLeg()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def clearanceReceived(self):
        logger.info("clearance command received")
        if self.waiting_for_clearance:
            xp.hideWidget(self.mainWindow["widgetID"])
            self.waiting_for_clearance = False
            nextWindow = self.ftg.nextLeg()
            xp.showWidget(nextWindow)
        else:
            logger.info("not waiting for clearance, ignoring command")

    def cbClose(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Just closes the window. Do no alter any other process.
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            return 1
        return 0

    def cbCancel(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Cancels FollowTheGreen
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            self.ftg.terminate("user cancelled")
            return 1
        return 0

    def newGreensReceived(self):
        logger.info("new greens command received")
        if not self.dest:
            logger.info("no destination")
            return 1
        if self.mainWindow is not None:
            xp.hideWidget(self.mainWindow["widgetID"])
            nextWindow = self.ftg.newGreen(self.dest)
            xp.showWidget(nextWindow)
        else:
            logger.info("no window, probably not active")
        return 1

    def cancelReceived(self, comment: str):
        logger.info("cancel command received")
        xp.hideWidget(self.mainWindow["widgetID"])
        self.ftg.terminate(comment)

    def cbBye(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Cancels FollowTheGreen
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow["widgetID"])
            self.ftg.terminate("terminated normally")
            return 1
        return 0
