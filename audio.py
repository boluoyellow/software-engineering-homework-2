"""Small procedural soundtrack and sound effects with no external assets."""

import math
from array import array

import pygame


SAMPLE_RATE = 44100
MAX_SAMPLE = 32767


def _wave_sample(phase, waveform):
    if waveform == "square":
        return 1.0 if math.sin(phase) >= 0 else -1.0
    if waveform == "triangle":
        return 2.0 / math.pi * math.asin(math.sin(phase))
    return math.sin(phase) + 0.18 * math.sin(phase * 2.0)


def _envelope(position, duration, attack=0.012, release=0.10):
    fade_in = min(1.0, position / max(attack, 0.001))
    fade_out = min(1.0, (duration - position) / max(release, 0.001))
    return max(0.0, min(fade_in, fade_out))


def _make_sound(events, duration, master_volume=0.35):
    """Render [(start, duration, frequency, level, waveform), ...] to stereo PCM."""
    sample_count = int(duration * SAMPLE_RATE)
    mixed = [0.0] * sample_count

    for start, note_duration, frequency, level, waveform in events:
        first = int(start * SAMPLE_RATE)
        count = min(int(note_duration * SAMPLE_RATE), sample_count - first)
        for index in range(max(0, count)):
            time_in_note = index / SAMPLE_RATE
            phase = math.tau * frequency * time_in_note
            value = _wave_sample(phase, waveform)
            value *= _envelope(time_in_note, note_duration)
            mixed[first + index] += value * level

    pcm = array("h")
    for value in mixed:
        sample = int(max(-1.0, min(1.0, value * master_volume)) * MAX_SAMPLE)
        pcm.append(sample)
        pcm.append(sample)
    return pygame.mixer.Sound(buffer=pcm.tobytes())


class SoundManager:
    def __init__(self):
        self.enabled = False
        self.clear_sounds = []
        self.blocked_sound = None
        self.restart_sound = None
        self.victory_music = None
        self.victory_channel = None

        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2, buffer=512)
            self._build_library()
            self.enabled = True
        except (pygame.error, MemoryError):
            # Audio should never prevent the game itself from starting.
            self.enabled = False

    def _build_library(self):
        # Sixteen half-step stages make consecutive clears climb smoothly instead
        # of jumping through five broad intervals.  The register is also shifted
        # upward and spans more than an octave (C5 to E-flat6).
        clear_roots = [523.25 * (2.0 ** (step / 12.0)) for step in range(16)]
        for root in clear_roots:
            self.clear_sounds.append(
                _make_sound(
                    [
                        (0.00, 0.16, root, 0.68, "sine"),
                        (0.075, 0.20, root * 1.5, 0.48, "triangle"),
                        (0.145, 0.18, root * 2.0, 0.22, "sine"),
                    ],
                    0.38,
                    0.30,
                )
            )

        self.blocked_sound = _make_sound(
            [
                (0.00, 0.18, 92.0, 0.72, "square"),
                (0.025, 0.20, 117.0, 0.48, "triangle"),
                (0.105, 0.18, 63.0, 0.60, "square"),
            ],
            0.32,
            0.25,
        )

        self.restart_sound = _make_sound(
            [
                (0.00, 0.11, 261.6, 0.52, "triangle"),
                (0.08, 0.13, 392.0, 0.58, "triangle"),
                (0.17, 0.18, 659.3, 0.60, "sine"),
            ],
            0.40,
            0.30,
        )

        melody = [
            (0.00, 0.22, 523.3),
            (0.22, 0.22, 659.3),
            (0.44, 0.24, 784.0),
            (0.68, 0.42, 1046.5),
            (1.18, 0.18, 784.0),
            (1.36, 0.18, 880.0),
            (1.54, 0.18, 987.8),
            (1.72, 0.52, 1046.5),
            (2.30, 0.20, 1318.5),
            (2.50, 0.64, 1568.0),
        ]
        victory_events = []
        for start, note_duration, frequency in melody:
            victory_events.append((start, note_duration, frequency, 0.55, "triangle"))
            victory_events.append((start, note_duration, frequency * 0.5, 0.22, "sine"))
        victory_events.extend(
            [
                (0.00, 0.66, 130.8, 0.24, "sine"),
                (0.68, 0.42, 196.0, 0.24, "sine"),
                (1.18, 0.54, 174.6, 0.22, "sine"),
                (1.72, 0.52, 261.6, 0.26, "sine"),
                (2.30, 0.84, 392.0, 0.25, "sine"),
            ]
        )
        self.victory_music = _make_sound(victory_events, 3.25, 0.24)

    def play_clear(self, combo):
        if self.enabled:
            self.clear_sounds[min(max(combo - 1, 0), len(self.clear_sounds) - 1)].play()

    def play_blocked(self):
        if self.enabled:
            self.blocked_sound.play()

    def play_restart(self):
        if self.enabled:
            self.restart_sound.play()

    def play_victory(self):
        if self.enabled:
            self.victory_channel = self.victory_music.play()

    def stop_victory(self):
        if self.enabled and self.victory_channel is not None:
            self.victory_channel.stop()
            self.victory_channel = None
