import time

import Live
from _Framework.ControlSurface import ControlSurface
from _Framework.InputControlElement import MIDI_CC_TYPE, MIDI_NOTE_TYPE
from _Framework.EncoderElement import EncoderElement
from _Framework.ButtonElement import ButtonElement

from .protocol import clip_progress, scene_message

CHANNEL = 0  # MIDI channel 1
CC_SCENE_SCROLL = 20
NOTE_SCENE_FIRE = 60

# update_display() runs on Live's ~100ms timer; this resends about every two
# seconds so a device plugged in after Live, or a renamed scene, catches up.
RESEND_TICKS = 20

# A one-shot seen with less than this left when nothing plays any more is
# treated as having finished, not as having been stopped.
FINISHED_LEFT_S = 0.3

# The device free-runs its bar between messages; resend at once when the
# playhead is further than this from where that free-run says it should be
# (a relaunch, a jump, a tempo change).
PROGRESS_DRIFT_S = 0.3


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
        self._prog = (0, 0.0, 0.0)
        self._prog_clip = None
        self._prog_t = 0.0
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

    def _progress(self, song):
        """(state, left, total) for the longest playing clip of the row Live is playing, whatever is selected.

        The row is the one holding the most playing clips (ties go to the topmost); a long
        one-shot beside a short loop is shown until it ends, then the loop takes over.
        With nothing playing, a one-shot that was last seen at its end stays "finished" (3)
        until another clip starts.
        """
        counts = {}
        for t in song.tracks:
            i = t.playing_slot_index
            if i >= 0:
                counts[i] = counts.get(i, 0) + 1
        clip = None
        if counts:
            row = max(sorted(counts), key=lambda r: counts[r])
            for t in song.tracks:
                if t.playing_slot_index == row and t.clip_slots[row].has_clip:
                    c = t.clip_slots[row].clip
                    if c.is_playing and (clip is None or c.length > clip.length):
                        clip = c
        if clip is None:
            last = self._prog
            if last[0] == 3 or (last[0] == 2 and last[1] < FINISHED_LEFT_S):
                prog = (3, 0.0, last[2])
            else:
                prog = (0, 0.0, 0.0)
        else:
            left, total, looping = clip_progress(clip, song.tempo)
            prog = (1 if looping else 2, left, total)
        self._prog_clip = clip
        self._prog = prog
        self._prog_t = time.monotonic()
        return prog


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
        old_clip, old_prog, old_t = self._prog_clip, self._prog, self._prog_t
        prog = self._progress(song)
        if self._prog_clip != old_clip or prog[0] != old_prog[0] or abs(prog[2] - old_prog[2]) > 0.05:
            self._dirty = True
        elif prog[0] in (1, 2) and prog[2] > 0:
            expected = old_prog[1] - (self._prog_t - old_t)
            if prog[0] == 1:
                expected %= prog[2]
            drift = abs(prog[1] - expected)
            if min(drift, prog[2] - drift) > PROGRESS_DRIFT_S:
                self._dirty = True
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
                                       scene_bpm, sig, self._progress(song)))
