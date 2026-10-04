#include <Encoder.h>
#include <U8g2lib.h>

const uint8_t PIN_A = 2, PIN_B = 3, PIN_SW = 4;
const int COUNTS_PER_DETENT = 4;   // assumption: 24 detents / 24 pulses; verify against datasheet
const uint8_t CC_SCENE_SCROLL = 20, NOTE_SCENE_FIRE = 60, NAME_LEN = 20;
const uint8_t CC_TRACK_SCROLL = 21, NOTE_TRACK_CLICK = 61;
const uint32_t LONG_PRESS_MS = 500;
bool trackMode = false;   // resolved here, never sent; Live only sees which CC / note arrives
char trackName[NAME_LEN + 1];
uint16_t trackNum = 0;
uint8_t trackKind = 0;   // 0 audio, 1 MIDI, 2 open group, 3 folded group
const char *const TRACK_KIND_LABEL[] = {"Audio", "MIDI", "Group: open", "Group: folded"};

Encoder knob(PIN_A, PIN_B);
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);   // SSD1306 module? use U8G2_SSD1306_128X64_NONAME_F_HW_I2C

char name[NAME_LEN + 1];
bool haveState = false, needDraw = false, stopped = false;
uint8_t playState = 0;   // 0 not playing, 1 playing, 2 empty scene
const char EMPTY_MSG[] = "<no clips>";
const char ENDED_MSG[] = "<clip ended>";
const uint32_t STOP_SETTLE_MS = 1000, STOP_MSG_MS = 1000, STOP_SCENE_MS = 1000, LIVE_TIMEOUT_MS = 5000;
uint32_t lastRx = 0, cycleStart = 0;
const uint32_t BLINK_LATENCY_MS = 0;   // raise if the blink leads the audible beat (audio output latency)
uint16_t sceneNum = 0, tempoX10 = 1200;
uint32_t blinkAnchor = 0;
uint16_t sceneTempoX10 = 1200;
uint8_t sigNum = 4, sigDen = 4;
const int NAME_FIT = 124, SCROLL_GAP = 40, SCROLL_PX_PER_S = 40;
const uint32_t SCROLL_DELAY_MS = 1000;
uint32_t scrollStart = 0;
uint8_t progState = 0;   // 0 none, 1 looping clip, 2 one-shot, 3 one-shot finished
uint32_t progStart = 0, progTotalMs = 0, finishedStart = 0;
int nameW = 0;
uint8_t rx[64];
uint16_t rxLen = 0;

void onSysEx(const uint8_t *d, uint16_t n, bool last) {
  if (rxLen + n > sizeof(rx)) { rxLen = 0; return; }
  memcpy(rx + rxLen, d, n);
  rxLen += n;
  if (!last) return;
  const int TRK = 14 + NAME_LEN + 5;
  if (rxLen == TRK + 3 + NAME_LEN + 1 && rx[0] == 0xF0 && rx[1] == 0x7D && rx[2] == 0x02) {
    uint16_t num = rx[3] << 7 | rx[4];
    playState = rx[5];
    tempoX10 = rx[6] << 7 | rx[7];
    uint16_t phase = rx[8] << 7 | rx[9];
    sceneTempoX10 = rx[10] << 7 | rx[11];
    sigNum = rx[12];
    sigDen = rx[13];
    bool nowStopped = phase == 0x3FFF;
    if (nowStopped && (!stopped || !haveState)) cycleStart = millis() - STOP_SCENE_MS;
    stopped = nowStopped;
    lastRx = millis();
    if (!stopped) blinkAnchor = millis() - (uint32_t)((uint64_t)phase * beatMs() / 0x3FFF);
    char incoming[NAME_LEN + 1];
    memcpy(incoming, rx + 14, NAME_LEN);
    incoming[NAME_LEN] = 0;
    for (int i = NAME_LEN - 1; i >= 0 && incoming[i] == ' '; i--) incoming[i] = 0;
    char trackIncoming[NAME_LEN + 1];
    memcpy(trackIncoming, rx + TRK + 3, NAME_LEN);
    trackIncoming[NAME_LEN] = 0;
    for (int i = NAME_LEN - 1; i >= 0 && trackIncoming[i] == ' '; i--) trackIncoming[i] = 0;
    if (num != sceneNum || strcmp(incoming, name) || (trackMode && strcmp(trackIncoming, trackName))) {
      scrollStart = millis();
      cycleStart = millis() - (STOP_SCENE_MS - STOP_SETTLE_MS);
    }
    uint8_t newProg = rx[14 + NAME_LEN];
    uint32_t leftMs = (rx[15 + NAME_LEN] << 7 | rx[16 + NAME_LEN]) * 100UL;
    progTotalMs = (rx[17 + NAME_LEN] << 7 | rx[18 + NAME_LEN]) * 100UL;
    if (newProg == 3 && progState != 3) finishedStart = millis();
    progState = newProg;
    progStart = millis() - (progTotalMs - leftMs);
    sceneNum = num;
    strcpy(name, incoming);
    trackNum = rx[TRK] << 7 | rx[TRK + 1];
    trackKind = rx[TRK + 2] & 3;
    strcpy(trackName, trackIncoming);
    haveState = true;
    needDraw = true;
  }
  rxLen = 0;
}

uint32_t beatMs() {
  return tempoX10 ? 600000UL / tempoX10 : 500;
}

bool blinkOn() {
  uint32_t period = beatMs();   // one on/off cycle per beat, "on" starts at the beat
  return (millis() - blinkAnchor - BLINK_LATENCY_MS) % period < period / 2;
}

bool showMessage() {
  if (!stopped || !haveState) return false;
  return (millis() - cycleStart) % (STOP_MSG_MS + STOP_SCENE_MS) >= STOP_SCENE_MS;
}

bool emptyMsg() {
  if (playState != 2 || stopped || !haveState) return false;
  return (millis() - cycleStart) % (STOP_MSG_MS + STOP_SCENE_MS) >= STOP_SCENE_MS;
}

int scrollOffset() {
  uint32_t t = millis() - scrollStart;
  return t < SCROLL_DELAY_MS ? 0 : (uint64_t)(t - SCROLL_DELAY_MS) * SCROLL_PX_PER_S / 1000 % (nameW + SCROLL_GAP);
}

int progFill() {
  if (stopped) return 0;
  if (progState == 3) return 128;
  if (!progState || !progTotalMs) return 0;
  uint32_t t = millis() - progStart;
  if (progState == 1) t %= progTotalMs;
  else if (t > progTotalMs) t = progTotalMs;
  return (uint64_t)t * 128 / progTotalMs;
}

bool finishedOn() {
  return (millis() - finishedStart) % 2000 < 1000;
}

void drawCentered(int y, const char *s) {
  oled.drawStr((128 - oled.getStrWidth(s)) / 2, y, s);
}

void drawName(const char *s) {
  if (nameW <= NAME_FIT) {
    drawCentered(40, s);
  } else {
    int x = 2 - scrollOffset();
    oled.drawStr(x, 40, s);
    oled.drawStr(x + nameW + SCROLL_GAP, 40, s);
  }
}

void draw() {
  oled.clearBuffer();
  if (!haveState) {
    oled.setFont(u8g2_font_6x12_tr);
    oled.drawStr(20, 36, "waiting for Live");
  } else if (showMessage()) {
    oled.setFont(u8g2_font_helvB12_tr);
    drawCentered(28, "Live stopped.");
    drawCentered(50, "Push play.");
  } else if (trackMode) {
    oled.setFont(u8g2_font_6x12_tr);
    char hdr[16];
    if (trackNum) snprintf(hdr, sizeof(hdr), "Track %u", trackNum);
    else snprintf(hdr, sizeof(hdr), "Track -");
    drawCentered(11, hdr);
    drawCentered(62, TRACK_KIND_LABEL[trackKind]);
    oled.drawHLine(0, 17, 128);
    oled.drawHLine(0, 46, 128);
    oled.setFont(u8g2_font_fub20_tr);
    nameW = oled.getStrWidth(trackName);
    drawName(trackName);
  } else {
    oled.setFont(u8g2_font_6x12_tr);
    bool show = playState || stopped || progState == 3 || blinkOn();
    if (show) {
      char hdr[16];
      snprintf(hdr, sizeof(hdr), "Scene %u", sceneNum);
      drawCentered(11, hdr);
      char row[24];
      snprintf(row, sizeof(row), "%u.%u BPM %u/%u", sceneTempoX10 / 10, sceneTempoX10 % 10, sigNum, sigDen);
      drawCentered(62, row);
    }
    oled.drawHLine(0, 17, 128);
    oled.drawHLine(0, 46, 128);
    bool msg = emptyMsg() || (progState == 3 && !stopped && !finishedOn());
    int fill = progFill();
    if (progState == 3) fill = 0;
    if (msg) fill = 128;
    if (fill) oled.drawBox(0, 18, fill, 28);
    oled.setDrawColor(2);
    const char *mid = msg ? (playState == 2 ? EMPTY_MSG : ENDED_MSG) : name;
    oled.setFont(msg ? u8g2_font_fub14_tr : u8g2_font_fub20_tr);
    nameW = oled.getStrWidth(mid);
    if (show) {
      if (msg) drawCentered(38, mid);
      else drawName(mid);
    }
  }
  oled.setDrawColor(1);
  oled.sendBuffer();
}

void setup() {
  pinMode(PIN_SW, INPUT_PULLUP);
  oled.begin();
  oled.setFontMode(1);
  usbMIDI.setHandleSystemExclusive(onSysEx);
  draw();
}

void loop() {
  for (int i = 0; i < 64; i++) usbMIDI.read();   // one call consumes one 3-byte event; a SysEx is 12

  static bool lastBlink = false;
  if (haveState && !trackMode && playState == 0 && !stopped && progState != 3 && blinkOn() != lastBlink) {
    lastBlink = !lastBlink;
    needDraw = true;
  }

  static bool lastMsg = false;
  if ((showMessage() || emptyMsg()) != lastMsg) {
    lastMsg = !lastMsg;
    needDraw = true;
  }

  if (haveState && millis() - lastRx > LIVE_TIMEOUT_MS) {
    haveState = false;
    trackMode = false;
    needDraw = true;
  }

  static int lastOffset = -1;
  if (haveState && nameW > NAME_FIT && scrollOffset() != lastOffset) {
    lastOffset = scrollOffset();
    needDraw = true;
  }

  static int lastFill = -1;
  int fill = haveState && !trackMode && !showMessage() ? progFill() + (progState == 3 && !stopped && finishedOn()) : 0;
  if (fill != lastFill) {
    lastFill = fill;
    needDraw = true;
  }

  if (needDraw) {
    needDraw = false;
    draw();
  }

  long steps = knob.read() / COUNTS_PER_DETENT;
  if (steps) {
    knob.write(knob.read() - steps * COUNTS_PER_DETENT);
    usbMIDI.sendControlChange(trackMode ? CC_TRACK_SCROLL : CC_SCENE_SCROLL, steps > 0 ? steps : 128 + steps, 1);
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

  // Click fires on release so a hold can switch mode without also launching;
  // the hold acts while still down and longHandled swallows the release.
  static bool down = false, longHandled = false;
  static uint32_t changed = 0;
  bool pressed = digitalRead(PIN_SW) == LOW;
  if (pressed != down && millis() - changed > 20) {
    down = pressed;
    changed = millis();
    if (down) {
      longHandled = false;
    } else if (!longHandled) {
      uint8_t note = trackMode ? NOTE_TRACK_CLICK : NOTE_SCENE_FIRE;
      usbMIDI.sendNoteOn(note, 127, 1);
      usbMIDI.sendNoteOff(note, 0, 1);
      usbMIDI.send_now();
    }
  }
  if (down && !longHandled && millis() - changed > LONG_PRESS_MS) {
    longHandled = true;
    if (haveState) {
      trackMode = !trackMode;
      scrollStart = millis();
      needDraw = true;
    }
  }
}
