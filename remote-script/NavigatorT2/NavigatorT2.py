import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.EncoderElement import EncoderElement
from _Framework.ButtonElement import ButtonElement

from .protocol import scene_message

CHANNEL = 0  # MIDI channel 1
CC_SCENE_SCROLL = 20
NOTE_SCENE_FIRE = 60

# update_display() runs on Live's ~100ms timer; this resends about every two
# seconds so a device plugged in after Live, or a renamed scene, catches up.
RESEND_TICKS = 20


class NavigatorT2(ControlSurface):

    def __init__(self, c_instance):
        super().__init__(c_instance)
        with self.component_guard():
            self._encoder = EncoderElement(
                MIDI_CC_TYPE, CHANNEL, CC_SCENE_SCROLL,
                Live.MidiMap.MapMode.relative_two_compliment)
            self._button = ButtonElement(
                True, MIDI_NOTE_TYPE, CHANNEL, NOTE_SCENE_FIRE)
            self._encoder.add_value_listener(self._on_scroll)
            self._button.add_value_listener(self._on_fire)

        self._dirty = True
        self._ticks = 0
        song = self.song()
        song.view.add_selected_scene_listener(self._mark_dirty)
        song.add_scenes_listener(self._mark_dirty)
        self.log_message("NavigatorT2: loaded")

    def disconnect(self):
        song = self.song()
        song.view.remove_selected_scene_listener(self._mark_dirty)
        song.remove_scenes_listener(self._mark_dirty)
        super().disconnect()

    def _mark_dirty(self):
        self._dirty = True

    def _on_scroll(self, value):
        delta = value - 128 if value >= 64 else value
        song = self.song()
        scenes = list(song.scenes)
        index = scenes.index(song.view.selected_scene)
        song.view.selected_scene = scenes[max(0, min(len(scenes) - 1, index + delta))]

    def _on_fire(self, value):
        if value:
            self.song().view.selected_scene.fire()

    def refresh_state(self):
        super().refresh_state()
        self._dirty = True

    def update_display(self):
        super().update_display()
        self._ticks += 1
        if self._ticks >= RESEND_TICKS:
            self._ticks = 0
            self._dirty = True
        if self._dirty:
            self._dirty = False
            song = self.song()
            scenes = list(song.scenes)
            # unnamed scenes read as empty in the LOM but show as numbers in Live
            names = [s.name or str(i + 1) for i, s in enumerate(scenes)]
            index = scenes.index(song.view.selected_scene)
            self._send_midi(scene_message(names, index))
