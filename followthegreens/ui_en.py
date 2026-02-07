# FtG Mutlilingual hook (for later)
# Replace static strings by these
# print("We could not find airport named {icao}.")
# print(UI_TEXT["ERROR"]["APT"] % (icao))
UI_TEXT = {
    "BUTTON": {
        "CLOSE": "Close",
        "CANCEL": "Cancel Follow the greens",
        "FINISH": "Finish",
        "CLEARANCE": "Clearance received",
        "CANCELSHORT": "Cancel",
        "CONTINUE": "Continue",
        "IAMLOST": "New green please",
        "NEWDEST": "New destination"
    },
    "ERROR": {
        "APT":  "We could not find airport named '%s'.",
        "TXW":  "We could not find smooth taxiway lines for airport named '%s'.",
        "NET":  "We could not find runways for %s.",
        "RMP":  "We could not find ramps/parking for %s.",
        "LOB":  "Could not load light objects.",
        "POB":  "Could not place light objects.",
    },
    "DIALOG": {
        "DST": f"Destination %s not valid for %s",
    },
}
