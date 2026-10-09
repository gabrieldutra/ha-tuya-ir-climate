"""Climate entities for Tuya IR air conditioners."""

import asyncio
import json
from typing import Any

from tuya_sharing import CustomerDevice, Manager
import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CATEGORY_INFRARED_AC,
    CODE_FAN,
    CODE_MODE,
    CODE_POWER_OFF,
    CODE_POWER_ON,
    CODE_TEMPERATURE,
    DOMAIN,
    LOGGER,
    STATUS_FAN,
    STATUS_MODE,
    STATUS_POWER,
    STATUS_TEMPERATURE,
    TUYA_DOMAIN,
    TUYA_HA_SIGNAL_UPDATE_ENTITY,
)

# Values of the "M" and "F" functions, as used by the Tuya IR remotes
HVAC_MODES = {
    0: HVACMode.COOL,
    1: HVACMode.HEAT,
    2: HVACMode.AUTO,
    3: HVACMode.FAN_ONLY,
    4: HVACMode.DRY,
}
FAN_MODES = {0: FAN_AUTO, 1: FAN_LOW, 2: FAN_MEDIUM, 3: FAN_HIGH}

SERVICE_SEND_COMMANDS = "send_commands"
ATTR_COMMANDS = "commands"

# Seconds between two commands to the same unit
COMMAND_INTERVAL = 1

DEFAULT_MIN_TEMP = 16
DEFAULT_MAX_TEMP = 30
DEFAULT_TEMP = 24


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a climate entity for each IR air conditioner known to Tuya."""
    entity_platform.async_get_current_platform().async_register_entity_service(
        SERVICE_SEND_COMMANDS,
        {vol.Required(ATTR_COMMANDS): [dict]},
        "async_send_raw_commands",
    )

    async_add_entities(
        TuyaIrClimate(tuya_entry.entry_id, device)
        for tuya_entry in hass.config_entries.async_loaded_entries(TUYA_DOMAIN)
        for device in tuya_entry.runtime_data.manager.device_map.values()
        if device.category == CATEGORY_INFRARED_AC
    )


def _function_range(device: CustomerDevice, code: str) -> tuple[int, int] | None:
    """Return the (min, max) the device advertises for a function."""
    if (function := device.function.get(code)) is None:
        return None
    try:
        values = json.loads(function.values)
        return int(values["min"]), int(values["max"])
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    """Return a status value as a number; Tuya sends some as strings."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TuyaIrClimate(ClimateEntity, RestoreEntity):
    """An air conditioner controlled through a Tuya IR blaster.

    Infrared is one-way, so the state is what Tuya last sent to the unit,
    from here or from Smart Life. The physical remote goes unnoticed.
    """

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_target_temperature_step = 1
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, tuya_entry_id: str, device: CustomerDevice) -> None:
        """Init the entity from the Tuya device."""
        self._tuya_entry_id = tuya_entry_id
        self._device_id = device.id
        self._attr_unique_id = f"{device.id}_climate"
        # A device of our own: one integration cannot add entities to a device
        # that another integration registered
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer="Tuya",
            model=device.product_name,
            name=device.name,
        )

        self._attr_supported_features = (
            ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        )

        self._attr_hvac_modes = [HVACMode.OFF]
        if mode_range := _function_range(device, CODE_MODE):
            self._attr_hvac_modes += [
                mode
                for value, mode in HVAC_MODES.items()
                if mode_range[0] <= value <= mode_range[1]
            ]
        self._attr_hvac_mode = HVACMode.OFF
        # Mode to go back to when turned on without one
        self._last_on_mode = next(
            (mode for mode in self._attr_hvac_modes if mode != HVACMode.OFF), None
        )

        if temp_range := _function_range(device, CODE_TEMPERATURE):
            self._attr_supported_features |= ClimateEntityFeature.TARGET_TEMPERATURE
        self._attr_min_temp, self._attr_max_temp = temp_range or (
            DEFAULT_MIN_TEMP,
            DEFAULT_MAX_TEMP,
        )
        self._attr_target_temperature = DEFAULT_TEMP

        self._attr_fan_modes = None
        self._attr_fan_mode = None
        if fan_range := _function_range(device, CODE_FAN):
            self._attr_supported_features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = [
                mode
                for value, mode in FAN_MODES.items()
                if fan_range[0] <= value <= fan_range[1]
            ]
            self._attr_fan_mode = self._attr_fan_modes[0]

    @property
    def _manager(self) -> Manager | None:
        """Return the Tuya connection, which is replaced when Tuya reloads."""
        tuya_entry = self.hass.config_entries.async_get_entry(self._tuya_entry_id)
        if tuya_entry is None or tuya_entry.state is not ConfigEntryState.LOADED:
            return None
        return tuya_entry.runtime_data.manager

    @property
    def available(self) -> bool:
        """Return if the remote, and so its IR blaster, is online."""
        if (manager := self._manager) is None:
            return False
        device = manager.device_map.get(self._device_id)
        return device is not None and device.online

    async def async_added_to_hass(self) -> None:
        """Restore the last sent state and follow online/offline updates."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_hvac_modes:
                self._attr_hvac_mode = HVACMode(last_state.state)
                if self._attr_hvac_mode != HVACMode.OFF:
                    self._last_on_mode = self._attr_hvac_mode
            if (temperature := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = temperature
            if (fan_mode := last_state.attributes.get(ATTR_FAN_MODE)) in (
                self._attr_fan_modes or []
            ):
                self._attr_fan_mode = fan_mode

        await self.hass.async_add_executor_job(self._subscribe)
        if tuya_entry := self.hass.config_entries.async_get_entry(self._tuya_entry_id):
            # A reload of Tuya starts a new connection without our devices
            self.async_on_remove(
                tuya_entry.async_on_state_change(self._handle_tuya_entry_state)
            )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self._device_id}",
                self._handle_tuya_update,
            )
        )

    def _subscribe(self) -> None:
        """Ask Tuya to push this device's updates.

        It only does so for devices that have an entity in the Tuya
        integration, which these remotes do not.
        """
        if (manager := self._manager) is None or manager.mq is None:
            return
        device = manager.device_map.get(self._device_id)
        if device is None or device.set_up:
            return
        device.set_up = True
        try:
            manager.mq.subscribe_device(device.id, device)
        except AttributeError:
            # Not connected yet: the device is subscribed once it connects
            pass

    @callback
    def _handle_tuya_entry_state(self) -> None:
        """Subscribe again after the Tuya integration reloads."""
        self.hass.async_add_executor_job(self._subscribe)
        self.async_write_ha_state()

    @callback
    def _handle_tuya_update(
        self, updated_status_properties: list[str] | None = None, *args: Any
    ) -> None:
        """Called when Tuya reports a change, such as going offline."""
        if updated_status_properties:
            self._update_from_tuya()
        self.async_write_ha_state()

    def _update_from_tuya(self) -> None:
        """Take over the state Tuya reported, which Smart Life shares."""
        if (manager := self._manager) is None:
            return
        if (device := manager.device_map.get(self._device_id)) is None:
            return
        status = device.status

        if (temperature := _as_int(status.get(STATUS_TEMPERATURE))) is not None:
            self._attr_target_temperature = temperature
        fan_mode = FAN_MODES.get(_as_int(status.get(STATUS_FAN)))
        if fan_mode in (self._attr_fan_modes or []):
            self._attr_fan_mode = fan_mode
        hvac_mode = HVAC_MODES.get(_as_int(status.get(STATUS_MODE)))
        if hvac_mode in self._attr_hvac_modes:
            self._last_on_mode = hvac_mode

        power = status.get(STATUS_POWER)
        if power is False:
            self._attr_hvac_mode = HVACMode.OFF
        elif power is True and self._last_on_mode is not None:
            self._attr_hvac_mode = self._last_on_mode

    async def _async_send_commands(self, commands: list[dict[str, Any]]) -> None:
        """Send commands to the remote through the Tuya cloud."""
        if (manager := self._manager) is None:
            raise HomeAssistantError("The Tuya integration is not loaded")
        LOGGER.debug("Sending commands for device %s: %s", self._device_id, commands)
        # The cloud rejects several commands in one request (error 1109), and
        # each one is a separate IR transmission the unit needs time to take
        for index, command in enumerate(commands):
            if index:
                await asyncio.sleep(COMMAND_INTERVAL)
            try:
                await self.hass.async_add_executor_job(
                    manager.send_commands, self._device_id, [command]
                )
            except Exception as err:
                # The Tuya library raises a bare Exception when the cloud refuses
                raise HomeAssistantError(f"Tuya rejected {command}: {err}") from err

    async def async_send_raw_commands(self, commands: list[dict[str, Any]]) -> None:
        """Send commands as given, without touching the assumed state."""
        await self._async_send_commands(commands)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the mode, turning the air conditioner on or off as needed."""
        if hvac_mode == HVACMode.OFF:
            await self._async_send_commands(
                [{"code": CODE_POWER_OFF, "value": CODE_POWER_OFF}]
            )
        else:
            value = next(v for v, mode in HVAC_MODES.items() if mode == hvac_mode)
            commands = [{"code": CODE_MODE, "value": value}]
            if self._attr_hvac_mode == HVACMode.OFF:
                commands.insert(0, {"code": CODE_POWER_ON, "value": CODE_POWER_ON})
            await self._async_send_commands(commands)
            self._last_on_mode = hvac_mode
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on in the mode it was last on in."""
        if self._last_on_mode is None:
            await self._async_send_commands(
                [{"code": CODE_POWER_ON, "value": CODE_POWER_ON}]
            )
            return
        await self.async_set_hvac_mode(self._last_on_mode)

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature, and the mode when given one."""
        if (hvac_mode := kwargs.get(ATTR_HVAC_MODE)) is not None:
            await self.async_set_hvac_mode(hvac_mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self._async_send_commands(
            [{"code": CODE_TEMPERATURE, "value": int(temperature)}]
        )
        self._attr_target_temperature = int(temperature)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed."""
        value = next(v for v, mode in FAN_MODES.items() if mode == fan_mode)
        await self._async_send_commands([{"code": CODE_FAN, "value": value}])
        self._attr_fan_mode = fan_mode
        self.async_write_ha_state()
