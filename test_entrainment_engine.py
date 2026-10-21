"""Regression shield for NeuroOptic's pure engine logic; no window or GL context is needed."""

import math
import random
import sys
import unittest

import entrainment_engine as engine


class FrequencyManagerTests(unittest.TestCase):
    def test_band_names_cover_preset_ranges(self):
        self.assertEqual(engine.FrequencyManager.get_band_name(2.0), "Delta")
        self.assertEqual(engine.FrequencyManager.get_band_name(10.0), "Alpha")
        self.assertEqual(engine.FrequencyManager.get_band_name(40.0), "Gamma")
        self.assertEqual(engine.FrequencyManager.get_band_name(150.0), "Custom")

    def test_frequency_above_nyquist_limit_is_rejected(self):
        with self.assertRaises(ValueError):
            engine.FrequencyManager.validate_frequency(40.0, 60, engine.WaveformType.SINE)

    def test_non_positive_frequency_is_rejected(self):
        with self.assertRaises(ValueError):
            engine.FrequencyManager.validate_frequency(0.0, 60, engine.WaveformType.SINE)

    def test_square_with_non_integer_frames_switches_to_sine(self):
        freq, waveform = engine.FrequencyManager.validate_frequency(7.0, 60, engine.WaveformType.SQUARE)
        self.assertEqual((freq, waveform), (7.0, engine.WaveformType.SINE))

    def test_square_with_integer_frames_is_kept(self):
        freq, waveform = engine.FrequencyManager.validate_frequency(10.0, 60, engine.WaveformType.SQUARE)
        self.assertEqual((freq, waveform), (10.0, engine.WaveformType.SQUARE))


class PhaseOscillatorTests(unittest.TestCase):
    def test_step_accumulates_phase_per_frame(self):
        osc = engine.PhaseOscillator(10.0, engine.WaveformType.SINE)
        osc.step(60.0)
        self.assertAlmostEqual(osc.phase, 2 * math.pi * 10.0 / 60.0)

    def test_phase_wraps_within_one_cycle(self):
        osc = engine.PhaseOscillator(10.0, engine.WaveformType.SINE, phase_offset=2 * math.pi - 1e-9)
        osc.step(60.0)
        self.assertLess(osc.phase, 2 * math.pi)

    def test_carrier_advances_only_for_am_waveform(self):
        am = engine.PhaseOscillator(10.0, engine.WaveformType.AM_CARRIER)
        am.set_carrier_frequency(30.0)
        am.step(60.0)
        self.assertAlmostEqual(am.carrier_phase, 2 * math.pi * 30.0 / 60.0)
        sine = engine.PhaseOscillator(10.0, engine.WaveformType.SINE)
        sine.step(60.0)
        self.assertEqual(sine.carrier_phase, 0.0)

    def test_jitter_stays_bounded_and_reproducible(self):
        osc = engine.PhaseOscillator(10.0, engine.WaveformType.SINE, rng=random.Random(7))
        osc.set_phase_jitter(0.5)
        phases = [osc.get_phase_state()[0] for _ in range(100)]
        self.assertTrue(all(0.0 <= p < 2 * math.pi for p in phases))
        twin = engine.PhaseOscillator(10.0, engine.WaveformType.SINE, rng=random.Random(7))
        twin.set_phase_jitter(0.5)
        self.assertEqual([twin.get_phase_state()[0] for _ in range(100)], phases)


class SignalMathTests(unittest.TestCase):
    def setUp(self):
        self.engine = engine.EntrainmentEngine(target_freq=10.0, waveform=engine.WaveformType.SINE)

    def test_sine_signal_swings_full_range(self):
        self.assertAlmostEqual(self.engine.compute_cpu_signal(engine.WaveformType.SINE, math.pi / 2, 0.0), 1.0)
        self.assertAlmostEqual(self.engine.compute_cpu_signal(engine.WaveformType.SINE, 3 * math.pi / 2, 0.0), 0.0)

    def test_square_signal_is_binary(self):
        self.assertEqual(self.engine.compute_cpu_signal(engine.WaveformType.SQUARE, 0.0, 0.0), 1.0)
        self.assertEqual(self.engine.compute_cpu_signal(engine.WaveformType.SQUARE, 3 * math.pi / 2, 0.0), 0.0)

    def test_triangle_signal_peaks_at_half_cycle(self):
        self.assertAlmostEqual(self.engine.compute_cpu_signal(engine.WaveformType.TRIANGLE, math.pi, 0.0), 1.0)
        self.assertAlmostEqual(self.engine.compute_cpu_signal(engine.WaveformType.TRIANGLE, 0.0, 0.0), 0.0)

    def test_am_signal_multiplies_carrier_and_modulator(self):
        self.assertAlmostEqual(
            self.engine.compute_cpu_signal(engine.WaveformType.AM_CARRIER, math.pi / 2, math.pi / 2), 1.0)
        self.assertAlmostEqual(
            self.engine.compute_cpu_signal(engine.WaveformType.AM_CARRIER, 0.0, 0.0), 0.25)


class ShamControlTests(unittest.TestCase):
    def test_static_sham_zeroes_frequency(self):
        subject = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                           sham_type=engine.ShamType.STATIC)
        self.assertEqual(subject.target_freq, 0.0)

    def test_detune_sham_shifts_frequency_deterministically(self):
        subject = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                           sham_type=engine.ShamType.DETUNE, sham_seed=3)
        twin = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                        sham_type=engine.ShamType.DETUNE, sham_seed=3)
        self.assertNotEqual(subject.target_freq, 40.0)
        self.assertEqual(subject.target_freq, twin.target_freq)


class ArgumentParsingTests(unittest.TestCase):
    def test_defaults_match_documented_values(self):
        original = sys.argv
        sys.argv = ["entrainment_engine.py"]
        try:
            args = engine.parse_arguments()
        finally:
            sys.argv = original
        self.assertEqual(args.freq, 40.0)
        self.assertEqual(args.waveform, "sine")
        self.assertEqual(args.mode, "full")
        self.assertEqual(args.sham, "none")


if __name__ == "__main__":
    unittest.main()
