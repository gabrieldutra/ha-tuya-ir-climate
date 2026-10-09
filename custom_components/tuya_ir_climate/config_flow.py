"""Config flow for Tuya IR Climate."""

from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import DOMAIN


class TuyaIrClimateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Nothing to configure: the devices come from the Tuya integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the integration."""
        if user_input is not None:
            return self.async_create_entry(title="Tuya IR Climate", data={})
        return self.async_show_form(step_id="user")
