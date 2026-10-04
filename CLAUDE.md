# CLAUDE.md

One-knob Ableton Live Session view controller: Teensy 4.1, PEC11R rotary encoder with push switch, 1.3" 128x64 I2C OLED. Knob scrolls scenes (clockwise = down), click launches, the OLED shows previous / current / next scene names.

- `firmware/navigator_t2/navigator_t2.ino` — device sketch
- `remote-script/NavigatorT2/` — Live MIDI Remote Script (Python)
- `tools/test_t2.py` — host-side check of the SysEx encoder

## Commands

    python3 tools/test_t2.py        # prints PASS; stdlib only, no Live needed

    arduino-cli compile --fqbn teensy:avr:teensy41:usb=midi firmware/navigator_t2
    arduino-cli upload  --fqbn teensy:avr:teensy41:usb=midi -p usb:<id> firmware/navigator_t2

`<id>` comes from `arduino-cli board list` (Teensy row, e.g. `usb:2110000`); plain `-p usb` fails. USB type must be `usb=midi` or `usbMIDI` does not exist. Libraries: `Encoder`, `U8g2`.

The Remote Script imports `Live` and `_Framework`, so it only runs inside Ableton. Before changing it, invoke the `ableton-lom-skill-main` skill rather than recalling LOM names from memory.

## Install the Remote Script

Live runs a copy, not the project files. After any edit, re-copy and restart Live:

    rsync -a --exclude __pycache__ remote-script/NavigatorT2 "$HOME/Music/Ableton/User Library/Remote Scripts/"

In Live: Preferences > Link, Tempo & MIDI > Control Surface = `NavigatorT2`, Input and Output = `Teensy MIDI`. Don't unplug the Teensy while Live is open; if the display sticks on "waiting for Live", toggle Output to None and back.

## Architecture

Two-way MIDI over USB; the Remote Script decides what the display shows.

```
knob turn  -> CC 20, ch1, two's-complement relative (1..63 = +, 65..127 = -)  -> _on_scroll  -> moves song.view.selected_scene (clamped, no wrap)
knob press -> Note 60 ch1 on/off                                               -> _on_fire    -> selected_scene.fire() on note-on
Live       -> SysEx F0 7D 02 <prev:20><cur:20><next:20> F7  (64 bytes)         -> firmware stores 3 names and redraws
```

Defined in two places; change both or neither:
- CC number, note number, channel: `CC_SCENE_SCROLL` / `NOTE_SCENE_FIRE` in `NavigatorT2.py` and `navigator_t2.ino`.
- SysEx format: `protocol.py` (encoder: `NAME_LEN = 20`, manufacturer ID `0x7D`, type `0x02`) and `onSysEx()` in the `.ino` (decoder: length `3 + 3*NAME_LEN + 1`, header bytes). `test_t2.py` asserts the 64-byte length. Keep `protocol.py` free of `Live` imports so the test can load it.

Names are ASCII-only (non-ASCII becomes `?`), padded to 20. Neighbours past either end of the list are blank. Unnamed scenes are sent as their 1-based number, since the LOM reports an empty name.

Display refresh is dirty-flag driven: scene selection and scene-list listeners set `_dirty`, and `update_display()` (Live's ~100 ms tick) sends only when dirty. It also resends every `RESEND_TICKS` (20, about 2 s) so a device connected after Live catches up; there is no handshake message.

Firmware `loop()` is one non-blocking pass: `usbMIDI.read()`, encoder, then button (20 ms debounce). Encoder counts are divided by `COUNTS_PER_DETENT` and the remainder is written back so partial detents are kept. Contact bounce can leave the count off by a fraction of a click, which makes the first click after a reversal not fire; so when the count has been still for 20 ms and A and B are both high (the detent level, measured), the count is snapped to the nearest multiple of `COUNTS_PER_DETENT`.

## Hardware

- Encoder A / B = pins 2 / 3, common to GND; switch = pin 4 to GND. Internal pull-ups, no external resistors. Swapping A and B reverses direction.
- OLED on 3.3 V, SDA = pin 18, SCL = pin 19. Constructor is `U8G2_SH1106_128X64_NONAME_F_HW_I2C`; an SSD1306 module needs `U8G2_SSD1306_128X64_NONAME_F_HW_I2C`.
- Encoder is Bourns PEC11R-4220F-S0024 (datasheet Rev. 04/26): 24 detents and 24 pulses per turn, so `COUNTS_PER_DETENT = 4`. Datasheet contact bounce is 2.0 ms max at 15 RPM *with* Bourns' RC filter (10k + 0.01 µF per channel); this build has no hardware filter, hence the rest resync in `loop()`.

## Gotchas

- `onSysEx()` calls `draw()` before its definition; this works because the Arduino preprocessor generates prototypes. Keep it a single `.ino` in its folder.
- `_on_scroll` and `update_display` call `scenes.index(selected_scene)`, which raises if the selected scene is not in the list. Not guarded.
