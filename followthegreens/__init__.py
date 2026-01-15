__NAME__ = "Follow the greens"
__DESCRIPTION__ = "Follow the greens, a 4D X-Plane ATC A-SMGCS experience"

from .version import __VERSION__

from .followthegreens import FollowTheGreens
from .showtaxiways import ShowTaxiways
from .globals import FTG_IS_RUNNING, FTG_PLUGIN_ROOT_PATH, RABBIT_MODE
from .globals import FTG_COMMAND, FTG_COMMAND_DESC, FTG_MENU
from .globals import STW_COMMAND, STW_COMMAND_DESC, STW_MENU
from .globals import FTG_CLEARANCE_COMMAND, FTG_CLEARANCE_COMMAND_DESC
from .globals import FTG_CANCEL_COMMAND, FTG_CANCEL_COMMAND_DESC
from .globals import FTG_OK_COMMAND, FTG_OK_COMMAND_DESC
from .globals import FTG_SPEED_COMMAND, FTG_SPEED_COMMAND_DESC
from .globals import FTG_BOOKMARK_COMMAND, FTG_BOOKMARK_COMMAND_DESC
