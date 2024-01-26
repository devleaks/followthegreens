# User Interface Utility Class
# Creates FTG windows.
#
import logging
from random import random

import xp

from .globals import ARRIVAL, DEPARTURE, GOOD
from .globals import MAINWINDOW_AUTOHIDE, MAINWINDOW_DISPLAY_TIME
from .globals import MAINWINDOW_WIDTH, MAINWINDOW_HEIGHT
from .globals import MAINWINDOW_FROM_LEFT, MAINWINDOW_FROM_BOTTOM


# Some texts we need to recognize. May be later translated.
CLOSE_TEXT = "Close"
CANCEL_TEXT = "Cancel follow the greens"
FINISH_TEXT = "Finish"
CLEARANCE_TEXT = "Clearance received"
CANCELSHORT_TEXT = "Cancel"
CONTINUE_TEXT = "Continue"
IAMLOST_TEXT = "New green please"
NEWDEST_TEXT = "New destination"

WINDOW_DISPLAY_TIME = 30 # secs


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
        self.canHide = True
        self.displayTime = 0
        self.search = ''
        self.searchBackup = ''


    def window(self, strings, btns):
        if self.mainWindow and "widgetID" in self.mainWindow.keys():  # We create a new window each time we are called.
            xp.destroyWidget(self.mainWindow['widgetID'], 1)
            self.mainWindow = None

        widgetWindow = {'widgetID': None,   # the ID of the main window containing all other widgets
                        'widgets': {}       # hash of all child widgets we care about
                        }
        self.mainWindow = widgetWindow

        self.fontID = xp.Font_Proportional
        _w, strHeight, _ignore = xp.getFontDimensions(self.fontID)
        self.strHeight = strHeight
        linespace = 2.0

        self.wLeft = MAINWINDOW_FROM_LEFT
        self.wTop = MAINWINDOW_FROM_BOTTOM + MAINWINDOW_HEIGHT + len(strings) * int(linespace * self.strHeight)
        self.wRight = MAINWINDOW_FROM_LEFT + MAINWINDOW_WIDTH
        self.wBottom = MAINWINDOW_FROM_BOTTOM
        widgetCenter = int(self.wLeft + (self.wRight - self.wLeft) / 2)

        widgetWindow['widgetID'] = xp.createWidget(self.wLeft, self.wTop, self.wRight, self.wBottom, 0, "Follow the greens",
                                                   1, 0, xp.WidgetClass_MainWindow)

        xp.addWidgetCallback(widgetWindow['widgetID'], self.cbMainWindow)

        # xp.setWidgetProperty(widgetWindow['widgetID'], xp.Property_MainWindowType, xp.MainWindowStyle_Translucent)
        xp.setWidgetProperty(widgetWindow['widgetID'], xp.Property_MainWindowHasCloseBoxes, 1)

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
            xp.createWidget(left, top, right, bottom, 1, s, 0, widgetWindow['widgetID'], xp.WidgetClass_Caption)

        # Line of buttons
        buttons, bwidth = self.mkButtons(btns)
        top = int(self.wBottom + 30)
        bottom = int(top - 1.2 * self.strHeight)
        left0 = int(widgetCenter - bwidth / 2)
        for k,btn in buttons.items():
            left = left0 + btn["left"]
            right = left0 + btn["right"]
            widgetWindow['widgets'][btn["name"]] = xp.createWidget(left, top, right, bottom,
                                                                   1, btn["text"], 0, widgetWindow['widgetID'],
                                                                   xp.WidgetClass_Button)
            if btn["cb"]:
                xp.addWidgetCallback(widgetWindow['widgets'][btn["name"]], btn["cb"])

        self.canHide = True  # new window can always be hidden
        return widgetWindow['widgetID']


    def mkButtons(self, btns):
        buttons = {}
        prev = False

        for b,cb in btns.items():
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
        return self.mainWindow and "widgetID" in self.mainWindow.keys()


    def isMainWindowVisible(self):
        if self.mainWindowExists():
            return xp.isWidgetVisible(self.mainWindow['widgetID'])
        return False


    def showMainWindow(self, canHide=True):
        if self.mainWindowExists():
            xp.showWidget(self.mainWindow['widgetID'])
            if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
                xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Checked)
                logging.debug(f"showMainWindow: menu checked ({self.ftg.pi.menuIdx})")
            else:
                logging.debug(f"showMainWindow: menu not checked ({self.ftg.pi.menuIdx})")
            self.canHide = canHide
            self.displayTime = 0


    def hideMainWindowIfOk(self, elapsed=0):
        # We always hide it on request, even if canHide is False
        self.displayTime += elapsed
        if MAINWINDOW_AUTOHIDE and self.mainWindowExists() and self.displayTime > WINDOW_DISPLAY_TIME and self.canHide:
            xp.hideWidget(self.mainWindow['widgetID'])
            if MAINWINDOW_AUTOHIDE and self.displayTime > MAINWINDOW_DISPLAY_TIME and self.canHide:
               self.hideMainWindow()



    def hideMainWindow(self):
        # We always hide it on request, even if canHide is False
        if self.mainWindowExists():
            xp.hideWidget(self.mainWindow['widgetID'])
            if self.ftg.pi is not None and self.ftg.pi.menuIdx is not None and self.ftg.pi.menuIdx >= 0:
                xp.checkMenuItem(xp.findPluginsMenu(), self.ftg.pi.menuIdx, xp.Menu_Unchecked)
                logging.debug(f"hideMainWindowIfOk: menu checked ({self.ftg.pi.menuIdx})")
            else:
                logging.debug(f"hideMainWindowIfOk: menu not checked ({self.ftg.pi.menuIdx})")


    def toggleVisibilityMainWindow(self):
        if self.mainWindowExists():
            logging.debug("UIUtil::toggleVisibilityMainWindow: isMainWindowVisible(): %d.", self.isMainWindowVisible())
            if self.isMainWindowVisible():
                self.hideMainWindow()
            else:
                self.showMainWindow()


    def destroyMainWindow(self):
        if self.mainWindowExists():
            xp.hideWidget(self.mainWindow['widgetID'])
            xp.destroyWidget(self.mainWindow['widgetID'], 1)
            self.mainWindow = None


    #
    #
    # MAIN WINDOW prompts
    #
    def greetings(self, text="Good %s."):
        h = self.ftg.aircraft.hourOfDay()
        logging.debug("UIUtil::nextLeg: bye: %d.", h)
        ss = list(GOOD.keys())[-1]
        for k, v in GOOD.items():
            if h > v:
                ss = k
        return text % ss

    def promptForAirport(self):
        # Create a window to prompt for airport ICAO code
        prompt = "Please enter this airport ICAO code"
        widgetWindow = self.window([
            "Welcome. We could not find the airport where you are located.",
            prompt
        ], {
            "Follow the greens": self.cbAirport,
            CANCELSHORT_TEXT: self.cbCancel
        })

        left = self.linetops[1][1] + 10
        right = int(left + 100)
        top = self.linetops[2][0]
        bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, 'icao', 0,
                                 self.mainWindow['widgetID'],
                                 xp.WidgetClass_TextField)
        self.mainWindow['widgets']['icao'] = widget

        return widgetWindow

    def promptForWindow(self, status=""):
        # Create a window to prompt for a local airport destination, either a runway or a parking position
        move = self.ftg.move
        welcome = "Welcome. We could not guess where you want to taxi."
        if status != "":
            welcome = status + " Try again. Where do you want to taxi?"

        button = "None"
        prompt = "Wait while loading"
        text   = "LOADING"

        widgetWindow = self.window([
            welcome,
            prompt,
            "Click inside the text box and use UP and DOWN arrow to cycle through values.",
            "Key in first 3 digits. Backspace to start from new entry"
        ], {
            "Follow the green": None,
            CANCELSHORT_TEXT: self.cbCancel
        })


        left = self.linetops[1][1] + 10
        right = int(left + 150)
        top = self.linetops[1][0] - 2
        bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, text, 0,
                                 self.mainWindow['widgetID'],
                                 xp.WidgetClass_TextField)
        self.mainWindow['widgets']['dest'] = widget
        xp.addWidgetCallback(self.mainWindow['widgets']['dest'], self.cbUpDown)

        strWidth = xp.measureString(self.fontID, button)
        left = right + 20  # after the above textfield
        right = int(left + 1.1 * strWidth)
        # top = int(self.wTop - 40 - self.strHeight)
        # bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, button, 0,
                                 widgetWindow,
                                 xp.WidgetClass_Button)
        self.mainWindow['widgets']['move'] = widget
        xp.addWidgetCallback(self.mainWindow['widgets']['move'], self.cbMovement)

        return widgetWindow


    def promptForDestination(self, status=""):
        # Create a window to prompt for a local airport destination, either a runway or a parking position
        move = self.ftg.move
        welcome = "Welcome. We could not guess where you want to taxi."
        if status != "":
            welcome = status + " Try again. Where do you want to taxi?"

        button = None
        prompt = None
        text   = None
        if move == DEPARTURE:
            self.validDestinations = self.ftg.airport.getDestinations(DEPARTURE)
            prompt = "Please enter runway for departure"
            button = "It is an arrival"
            text   = "RWY/HLD"
        else:
            self.validDestinations = self.ftg.airport.getDestinations(ARRIVAL)
            prompt = "Please enter parking for arrival"
            button = "It is a departure"
            text   = "RAMP"

        if len(self.validDestinations) > 0:
            self.validDestinations.sort()
            self.validDestIdxs = list(map(lambda x: x[0:3].upper(), self.validDestinations))
            # logging.debug("ui: added %d ramp", self.validDestIdxs)
            self.destinationIdx = int(random() * len(self.validDestinations))
            text = self.validDestinations[self.destinationIdx]

        widgetWindow = self.window([
            welcome,
            prompt,
            "Click inside the text box and use UP and DOWN arrow to cycle through values.",
            "Key in first 3 digits. Backspace to start from new entry"
        ], {
            "Follow the greens": self.cbDestination,
            CANCELSHORT_TEXT: self.cbCancel
        })


        left = self.linetops[1][1] + 10
        right = int(left + 150)
        top = self.linetops[1][0] - 2
        bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, text, 0,
                                 self.mainWindow['widgetID'],
                                 xp.WidgetClass_TextField)
        self.mainWindow['widgets']['dest'] = widget
        xp.addWidgetCallback(self.mainWindow['widgets']['dest'], self.cbUpDown)

        strWidth = xp.measureString(self.fontID, button)
        left = right + 20  # after the above textfield
        right = int(left + 1.1 * strWidth)
        # top = int(self.wTop - 40 - self.strHeight)
        # bottom = int(top - self.strHeight)
        widget = xp.createWidget(left, top, right, bottom, 1, button, 0,
                                 widgetWindow,
                                 xp.WidgetClass_Button)
        self.mainWindow['widgets']['move'] = widget
        xp.addWidgetCallback(self.mainWindow['widgets']['move'], self.cbMovement)

        return widgetWindow


    def followTheGreen(self):
        btns = {
            CANCEL_TEXT: self.cbCancel
        }
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        return self.window([
            "Follow the greens.",
            "(You can close this window with the little x in the above window title bar.)"
        ], btns)


    def promptForClearance(self):
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        btns = {
            CLEARANCE_TEXT: self.cbClearance,
            CANCELSHORT_TEXT: self.cbCancel
        }
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        return self.window([
            "Follow the greens until you encounter a line of red stop lights.",
            "At the stop lights, contact TOWER for clearance. Press Continue when cleared."
        ], btns)


    def tryAgain(self, text):
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        btns = {
            NEWDEST_TEXT: self.cbNewDestination,
            CANCEL_TEXT: self.cbCancel
        }
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        return self.window([
            "We could not find a route to your destination.",
            "Get closer to taxiways and try again."
        ], btns)


    def promptForDeparture(self):
        # In front of the last stopbar, ask to ask for clearance for departure and press continue when clearance obtained.
        return self.window([
            "Follow the greens until you encounter a line of red stop lights at departure runway.",
            "Press Continue when cleared for runway."
        ], {
            CLEARANCE_TEXT: self.cbClearance,
            CANCELSHORT_TEXT: self.cbCancel
        })


    def promptForParked(self):
        btns = {
            CONTINUE_TEXT: self.cbClearance,
            CANCELSHORT_TEXT: self.cbCancel
        }
        if self.dest:
            btns[IAMLOST_TEXT] = self.cbNewGreen
        # In front of a stopbar, ask to ask for clearance and press continue when clearance obtained.
        return self.window([
            "Follow the greens to the designated parking area.",
            "Press Continue when parked."
        ], btns)


    def bye(self):
        return self.window([
            "You have reached your destination.",
            self.greetings("Enjoy your %s.")
        ], {
            FINISH_TEXT: self.cbBye
        })


    def enjoy(self):
        return self.window([
            "All taxiways in the network are lit. Press "+FINISH_TEXT+" to hide them.",
            self.greetings("Enjoy your %s.")
        ], {
            FINISH_TEXT: self.cbBye
        })


    def sorry(self, message):
        # Open a window with explanation.
        return self.window([
            "We are sorry. We cannot provide Follow The Greens service at this airport.",
            message
        ], {
            CLOSE_TEXT: self.cbClose
        })

    #
    #
    # CALLBACK for buttons and caption
    #
    def cbMainWindow(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Router for all window events (when button pressed)
        if inMessage == xp.Message_CloseButtonPushed:
            xp.hideWidget(self.mainWindow['widgetID'])
            return 1
        return 0

    def cbAirport(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if 'icao' in self.mainWindow['widgets'].keys():
                self.icao = xp.GetWidgetDescriptor(self.mainWindow['widgets']['icao'])
                logging.debug("UIUtil::cbAirport:airport: %s", self.icao)
                xp.hideWidget(self.mainWindow['widgetID'])
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
                logging.debug("UIUtil::cbUpDown:search before: %s", self.search)
                self.searchBackup = self.search
                self.search = ''.join((str(self.search), c))
                logging.debug("UIUtil::cbUpDown:search after: %s", self.search)
                logging.debug("UIUtil.:cbUpDown:search %s", self.search in self.validDestIdxs)
                match_idx = [x for x, wort in enumerate(self.validDestIdxs) if self.search in wort]
                logging.debug("UIUtil::cbUpDown:search indexes found: %s", str(match_idx))
                if len(match_idx) == 0:
                    logging.debug("UIUtil::cbUpDown:search index NOT found: %s", self.search)
                    self.search = self.searchBackup
                else:
                    logging.debug("UIUtil::cbUpDown:search index found: %s", str(match_idx[0]))
                    self.destinationIdx = match_idx[0]
                    xp.setWidgetDescriptor(widgetID, self.validDestinations[self.destinationIdx])
                return 1
            if param1[2] == xp.VK_BACK:
                self.search = ''
                xp.setWidgetDescriptor(widgetID, self.validDestinations[0])
                return 1
            # if any other key as been pressed, we ignore it.
            return 1
        return 0

    def cbDestination(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if 'dest' in self.mainWindow['widgets'].keys():
                self.dest = xp.getWidgetDescriptor(self.mainWindow['widgets']['dest'])
                logging.debug("UIUtil::cbDestination:destination: %s", self.dest)
                xp.hideWidget(self.mainWindow['widgetID'])
                nextWindow = self.ftg.followTheGreen(self.dest)
                xp.showWidget(nextWindow)
            return 1
        return 0

    def cbNewDestination(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            nextWindow = self.promptForDestination()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbNewGreen(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            if not self.dest:
                return 0
            xp.hideWidget(self.mainWindow['widgetID'])
            nextWindow = self.ftg.newGreen(self.dest)
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbMovement(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            if self.ftg.move == DEPARTURE:
                self.ftg.move = ARRIVAL
            else:
                self.ftg.move = DEPARTURE
            nextWindow = self.promptForDestination()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbClearance(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            nextWindow = self.ftg.nextLeg()
            xp.showWidget(nextWindow)
            return 1
        return 0

    def cbClose(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Just closes the window. Do no alter any other process.
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            return 1
        return 0

    def cbCancel(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Cancels FollowTheGreen
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            self.ftg.cancel("user cancelled")
            return 1
        return 0

    def cbBye(self, inMessage, inWidget, inParam1, inParam2):
        # pylint: disable=unused-argument
        # Cancels FollowTheGreen
        if inMessage == xp.Msg_PushButtonPressed:
            xp.hideWidget(self.mainWindow['widgetID'])
            self.ftg.cancel("terminated normally")
            return 1
        return 0
