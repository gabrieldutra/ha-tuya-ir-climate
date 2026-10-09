"""Climate entities for air conditioners behind a Tuya IR blaster.

The Tuya integration lists these remotes as unsupported, but the cloud
accepts commands for them. This integration reuses its connection and
only adds the missing climate entities.
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import TUYA_DOMAIN

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the climate entities once the Tuya integration is connected."""
    if not hass.config_entries.async_loaded_entries(TUYA_DOMAIN):
        raise ConfigEntryNotReady("The Tuya integration is not loaded")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the climate entities."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
