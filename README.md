# Ableton Navigator T2

A one-knob scene navigator for Ableton Live's Session view. Turn the knob to move through scenes, click to launch one. A small OLED shows the selected scene's number, name, tempo and time signature.

- Clockwise moves the selection down the scene list, counter-clockwise moves it up.
- Click launches the selected scene.
- The OLED shows three rows: "Scene N", the scene name (large; long names scroll), and the scene's tempo and time signature. All three blink on the beat while the selected scene isn't the one playing. Unnamed scenes show their number.

## Hardware

| Part | Notes |
|---|---|
| Teensy 4.1 | Appears to Live as a USB MIDI device |
| Bourns PEC11R-4220F-S0024 | 24 detents, 24 pulses per turn, push switch |
| 1.3" 128x64 I2C OLED | SH1106 controller (see below if yours is an SSD1306) |

| Encoder / OLED | Teensy pin |
|---|---|
| Encoder A / B | 2 / 3 |
| Encoder common | GND |
| Push switch | 4 and GND |
| OLED SDA / SCL | 18 / 19 |
| OLED VCC | 3.3 V (not 5 V) |

Internal pull-ups only, no external resistors. Swapping A and B reverses the knob direction.

## Setup

**1. Flash the firmware.** Needs [arduino-cli](https://arduino.github.io/arduino-cli/) with the Teensy core, plus the `Encoder` and `U8g2` libraries. USB type must be MIDI.

    arduino-cli compile --fqbn teensy:avr:teensy41:usb=midi firmware/navigator_t2
    arduino-cli upload  --fqbn teensy:avr:teensy41:usb=midi -p usb:<id> firmware/navigator_t2

`<id>` comes from `arduino-cli board list`. If the OLED shows garbage or is shifted by a couple of pixels, you have an SSD1306: change the constructor in the sketch to `U8G2_SSD1306_128X64_NONAME_F_HW_I2C`.

**2. Install the Remote Script.** Copy `remote-script/NavigatorT2/` into Live's User Library `Remote Scripts` folder (on macOS, `~/Music/Ableton/User Library/Remote Scripts/`), then restart Live.

**3. Enable it in Live.** Preferences > Link, Tempo & MIDI: set Control Surface to `NavigatorT2`, and Input and Output to `Teensy MIDI`. The OLED switches from "waiting for Live" to scene names within a couple of seconds.

Don't unplug the Teensy while Live is open. If the display sticks on "waiting for Live", set Output to None and back.

## How it works

```
knob  -> CC 20 (relative), button -> Note 60   ->  Remote Script moves / fires the scene
Live  -> SysEx F0 7D 02 <scene data><name> F7   ->  firmware redraws the OLED
```

The Remote Script decides what the display shows and resends it every ~2 seconds, so there is no handshake. Names are ASCII only, up to 20 characters. See `CLAUDE.md` for the protocol, the firmware's encoder handling, and known gaps.

## Test

    python3 tools/test_t2.py    # checks the SysEx encoder; prints PASS

The firmware and the Remote Script can only be checked on the device and inside Live.

## License

MIT, see `LICENSE`.
