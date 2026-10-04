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
        self._playing = False
        self._tempo = 0.0
        self._running = False
        self._ticks = 0
        song = self.song()
        song.view.add_selected_scene_listener(self._on_scene_selected)
        song.add_scenes_listener(self._mark_dirty)
        self.log_message("NavigatorT2: loaded")

    def disconnect(self):
        song = self.song()
        song.view.remove_selected_scene_listener(self._on_scene_selected)
        song.remove_scenes_listener(self._mark_dirty)
        super().disconnect()

    def _mark_dirty(self):
        self._dirty = True

    def _on_scene_selected(self):
        self._send_state(*self._snapshot())

    def _snapshot(self):
        song = self.song()
        scenes = list(song.scenes)
        index = scenes.index(song.view.selected_scene)
        # the LOM has no scene-level "playing"; count the scene as playing if any track plays its slot
        # 2 = empty scene (is_empty is not observable, so it is polled here)
        playing = 2 if scenes[index].is_empty else int(any(t.playing_slot_index == index for t in song.tracks))
        return song, scenes, index, playing

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
        song, scenes, index, playing = self._snapshot()
        if playing != self._playing or song.tempo != self._tempo or song.is_playing != self._running:
            self._playing = playing
            self._tempo = song.tempo
            self._running = song.is_playing
            self._dirty = True
        if self._dirty:
            self._send_state(song, scenes, index, playing)

    def _send_state(self, song, scenes, index, playing):
        self._dirty = False
        # unnamed scenes read as empty in the LOM but show as numbers in Live
        scene = scenes[index]
        name = scene.name or str(index + 1)
        # a scene without its own tempo / time signature leaves the song's unchanged on launch
        scene_bpm = scene.tempo if scene.tempo_enabled else song.tempo
        sig = ((scene.time_signature_numerator, scene.time_signature_denominator)
               if scene.time_signature_enabled else (song.signature_numerator, song.signature_denominator))
        self._send_midi(scene_message(name, index, playing, self._tempo,
                                       song.current_song_time if self._running else None,
                                       scene_bpm, sig))
