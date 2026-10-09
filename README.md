# Tuya IR Climate

Home Assistant climate entities for air conditioners controlled through a
Tuya / Smart Life IR blaster, without a Tuya developer account.

The official [Tuya integration](https://www.home-assistant.io/integrations/tuya)
lists these air conditioner remotes as "unsupported" and gives them no
entities. The Tuya cloud does accept commands for them, and does report their
state, over the connection that integration already has. This integration
reuses that connection and adds the missing `climate` entities.

## What you get

For each air conditioner remote set up under an IR blaster in the Smart Life
app:

- A `climate` entity with on/off, mode, target temperature and fan speed.
- State that follows Smart Life: a change made in the app shows up in Home
  Assistant within seconds, and the other way round.
- A `tuya_ir_climate.send_commands` action that sends raw commands, for
  working out what a unit understands.

## Requirements

- Home Assistant 2026.8 or newer. It is only tested on 2026.8.
- The official Tuya integration, set up and working.
- The air conditioner already added as a remote under the IR blaster in the
  Smart Life or Tuya app. The IR codes come from there; nothing is learned in
  Home Assistant.

## Installation

### HACS

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/gabrieldutra/ha-tuya-ir-climate` with type
   **Integration**.
3. Install **Tuya IR Climate** and restart Home Assistant.

### Manual

Copy `custom_components/tuya_ir_climate` into the `custom_components` folder
of your Home Assistant configuration and restart.

### Setup

Go to **Settings > Devices & services > Add integration** and add **Tuya IR
Climate**. There is nothing to configure. One climate entity appears for each
IR air conditioner on your Tuya account.

## Limitations

- **Infrared is one-way.** The state is whatever Tuya last sent to the unit.
  The physical remote goes unnoticed, by Home Assistant and by Smart Life.
- **State starts empty.** Tuya only reports a remote's state when it changes,
  so after a Home Assistant restart an entity shows what it last knew until
  the next change.
- **It needs the cloud.** Commands go through the Tuya cloud, like the rest of
  the official integration.
- **Mode and fan numbers are assumed.** Modes are sent as 0 cool, 1 heat,
  2 auto, 3 fan only, 4 dry, and fan speeds as 0 auto, 1 low, 2 medium,
  3 high. Only cool and auto fan are confirmed on a real unit. If yours
  differs, please open an issue.
- **It relies on internals.** It reads the official integration's connection
  object and the `tuya-device-sharing-sdk` library. A Home Assistant update
  can break it until it is patched.
- **Each unit shows as two devices.** One is the Tuya integration's
  "unsupported" device, the other holds the climate entity. An integration
  cannot add entities to another integration's device.

Tested with a Zigbee IR blaster (Tuya category `wnykq`) and its air
conditioner remotes (category `infrared_ac`).

## How it works

- **Commands:** the cloud advertises the functions `PowerOn`, `PowerOff`,
  `M` (mode), `T` (temperature) and `F` (fan) for an `infrared_ac` device.
  They are sent one per request, a second apart, because the cloud rejects a
  request carrying more than one (error 1109).
- **State:** the Tuya library only subscribes to push updates for devices
  that have an entity in the official integration. This integration subscribes
  to the remotes itself, then reads the `power`, `mode`, `temp` and `wind`
  values the cloud pushes.

## Finding out what your unit understands

`tuya_ir_climate.send_commands` sends commands as given and leaves the
entity's state alone:

```yaml
action: tuya_ir_climate.send_commands
target:
  entity_id: climate.living_room_ac
data:
  commands:
    - code: M
      value: 4
```

## Disclaimer

This project is not affiliated with Tuya or Home Assistant.
