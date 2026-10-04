#include <Encoder.h>
#include <U8g2lib.h>

const uint8_t PIN_A = 2, PIN_B = 3, PIN_SW = 4;
const int COUNTS_PER_DETENT = 4;   // assumption: 24 detents / 24 pulses; verify against datasheet
const uint8_t CC_SCENE_SCROLL = 20, NOTE_SCENE_FIRE = 60, NAME_LEN = 20;

Encoder knob(PIN_A, PIN_B);
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);   // SSD1306 module? use U8G2_SSD1306_128X64_NONAME_F_HW_I2C

char names[3][NAME_LEN + 1];   // prev, current, next
bool haveState = false;
uint8_t rx[64];
uint16_t rxLen = 0;

void onSysEx(const uint8_t *d, uint16_t n, bool last) {
  if (rxLen + n > sizeof(rx)) { rxLen = 0; return; }
  memcpy(rx + rxLen, d, n);
  rxLen += n;
  if (!last) return;
  if (rxLen == 3 + 3 * NAME_LEN + 1 && rx[0] == 0xF0 && rx[1] == 0x7D && rx[2] == 0x02) {
    for (int r = 0; r < 3; r++) {
      memcpy(names[r], rx + 3 + r * NAME_LEN, NAME_LEN);
      names[r][NAME_LEN] = 0;
    }
    haveState = true;
    draw();
  }
  rxLen = 0;
}

void draw() {
  oled.clearBuffer();
  if (!haveState) {
    oled.setFont(u8g2_font_6x12_tr);
    oled.drawStr(20, 36, "waiting for Live");
  } else {
    oled.setFont(u8g2_font_6x12_tr);
    oled.drawStr(4, 12, names[0]);
    oled.drawStr(4, 60, names[2]);
    oled.drawBox(0, 19, 128, 24);
    oled.setDrawColor(0);
    oled.setFont(u8g2_font_6x13B_tr);
    oled.drawStr(4, 36, names[1]);
    oled.setDrawColor(1);
  }
  oled.sendBuffer();
}

void setup() {
  pinMode(PIN_SW, INPUT_PULLUP);
  oled.begin();
  usbMIDI.setHandleSystemExclusive(onSysEx);
  draw();
}

void loop() {
  usbMIDI.read();

  long steps = knob.read() / COUNTS_PER_DETENT;
  if (steps) {
    knob.write(knob.read() - steps * COUNTS_PER_DETENT);
    usbMIDI.sendControlChange(CC_SCENE_SCROLL, steps > 0 ? steps : 128 + steps, 1);
    usbMIDI.send_now();
  }

  // Detent = both pins high. Bounce can leave the count off by a click fraction;
  // at rest, snap to the nearest multiple of COUNTS_PER_DETENT so reversals stay immediate.
  static long lastCount = 0;
  static uint32_t lastMove = 0;
  long count = knob.read();
  if (count != lastCount) {
    lastCount = count;
    lastMove = millis();
  } else if (millis() - lastMove > 20 && digitalRead(PIN_A) && digitalRead(PIN_B)) {
    long off = ((count + COUNTS_PER_DETENT / 2) % COUNTS_PER_DETENT + COUNTS_PER_DETENT) % COUNTS_PER_DETENT - COUNTS_PER_DETENT / 2;
    if (off) knob.write(count - off);
  }

  static bool down = false;
  static uint32_t changed = 0;
  bool pressed = digitalRead(PIN_SW) == LOW;
  if (pressed != down && millis() - changed > 20) {
    down = pressed;
    changed = millis();
    if (down) usbMIDI.sendNoteOn(NOTE_SCENE_FIRE, 127, 1);
    else usbMIDI.sendNoteOff(NOTE_SCENE_FIRE, 0, 1);
    usbMIDI.send_now();
  }
}
