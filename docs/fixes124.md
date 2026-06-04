### I loved your script and put some effort in to update it to XPlane 12.

This patch improves stability in X-Plane 12, introduces accessibility enhancements, and resolves lifecycle-related crashes caused by stale XPLM object references.

* * *

### Key Fixes & Improvements

#### 1\. X-Plane 12 Stability Fix (Critical)

Handled `XPLM_MSG_SCENERY_LOADED` and `XPLM_MSG_AIRPORT_LOADED` messages to prevent crashes caused by stale `XPLMInstanceRef` / `XPLMObjectRef`.

-   On receiving either message:
    -   All active light instances are destroyed
    -   Cached object references are cleared
-   This prevents:
    -   `TypeError: mismatch in requested capsule type`
    -   Plugin freezes/crashes during scenery reloads

Implementation located in:

-   `PythonInterface.XPluginReceiveMessage()`
* * *

#### 2\. Safe Plugin Lifecycle Cleanup

Improved cleanup logic during plugin disable:

-   Added support for both `.terminate()` and `.stop()` methods
-   Ensures safe teardown of:
    -   `FollowTheGreens`
    -   `ShowTaxiways`
-   Prevents orphaned objects and dangling references
* * *

#### 3\. Deferred UI Actions (Thread-Safety / Timing Fix)

UI-triggered actions are now deferred instead of executed immediately.

-   Prevents race conditions and invalid state access
-   Introduces a pending action queue processed in the flight loop

Changes include:

-   New request methods:
    -   `requestFollowTheGreen`
    -   `requestNewGreen`
-   Flight loop handles execution safely
* * *

#### 4\. Flight Loop Improvements

-   Added deferred execution support
-   Fixed invalid f-string formatting with `strftime`
* * *

#### 5\. Colourblind Mode (Accessibility)

Colourblind-friendly lighting is now enabled by default:

-   Route lights → Cyan
-   Stop bars → Magenta

Implemented in:

-   `lightstring.py`
* * *

#### 6\. Plugin Import Reliability

-   Ensures plugin is imported as a proper package
-   Fixes relative import issues (`__init__.py` exports)
-   Adds PythonPlugins root to `sys.path`
* * *

### Files Modified

-   `PI_FollowTheGreens.py` (core plugin interface & lifecycle fixes)
-   `followthegreens.py` (deferred actions + queue system)
-   `flightloop.py` (deferred execution + formatting fix)
-   `ui.py` (deferred UI triggers)
-   `lightstring.py` (colourblind mode defaults)
* * *

### Result

-   Eliminates crashes during scenery/airport reloads
-   Improves robustness of plugin lifecycle handling
-   Makes UI interactions safer and more predictable
-   Adds accessibility support with colourblind-friendly lighting
* * *

### Notes

This patch prioritizes runtime safety and compatibility with X-Plane 12’s object lifecycle. All changes are backward-compatible with existing functionality.
