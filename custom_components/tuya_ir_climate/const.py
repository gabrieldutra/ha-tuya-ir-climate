"""Constants for the Tuya IR Climate integration."""

import logging

DOMAIN = "tuya_ir_climate"
LOGGER = logging.getLogger(__package__)

TUYA_DOMAIN = "tuya"
# Dispatcher signal the Tuya integration sends on device updates
TUYA_HA_SIGNAL_UPDATE_ENTITY = "tuya_entry_update"

# Tuya category of an air conditioner remote set up under an IR blaster
CATEGORY_INFRARED_AC = "infrared_ac"

# Function codes the Tuya cloud accepts for an infrared_ac device
CODE_POWER_ON = "PowerOn"
CODE_POWER_OFF = "PowerOff"
CODE_MODE = "M"
CODE_TEMPERATURE = "T"
CODE_FAN = "F"

# Status codes the Tuya cloud pushes for an infrared_ac device, which is the
# state Smart Life shows
STATUS_POWER = "power"
STATUS_MODE = "mode"
STATUS_TEMPERATURE = "temp"
STATUS_FAN = "wind"
