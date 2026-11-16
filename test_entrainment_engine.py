"""Regression shield for NeuroOptic's pure engine logic; no window or GL context is needed."""

import math
import os
import random
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import entrainment_engine as engine


class FrequencyManagerTests(unittest.TestCase):
    def test_band_names_cover_preset_ranges(self):
        self.assertEqual(engine.FrequencyManager.get_band_name(2.0), "Delta")
        self.assertEqual(engine.FrequencyManager.get_band_name(10.0), "Alpha")
        self.assertEqual(engine.FrequencyManager.get_band_name(40.0), "Gamma")
        self.assertEqual(engine.FrequencyManager.get_band_name(150.0), "Custom")

    def test_band_name_covers_alpha_beta_boundary(self):
        self.assertEqual(engine.FrequencyManager.get_band_name(12.5), "Beta")

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

    def test_zero_allowed_only_with_explicit_static_opt_in(self):
        with self.assertRaises(ValueError):
            engine.FrequencyManager.validate_frequency(0.0, 60, engine.WaveformType.SINE)
        self.assertEqual(
            engine.FrequencyManager.validate_frequency(0.0, 60, engine.WaveformType.SINE, allow_zero=True),
            (0.0, engine.WaveformType.SINE))
        with self.assertRaises(ValueError):
            engine.FrequencyManager.validate_frequency(-1.0, 60, engine.WaveformType.SINE, allow_zero=True)


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

    def test_static_sham_zeroes_both_hemifields(self):
        subject = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                           sham_type=engine.ShamType.STATIC, sham_seed=1)
        self.assertEqual(subject.target_freq, 0.0)
        self.assertEqual(subject.right_freq, 0.0)
        self.assertEqual(
            engine.FrequencyManager.validate_frequency(
                subject.target_freq, 60, subject.waveform, allow_zero=True)[0], 0.0)

    def test_detune_sham_shifts_frequency_deterministically(self):
        subject = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                           sham_type=engine.ShamType.DETUNE, sham_seed=3)
        twin = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.SINE,
                                        sham_type=engine.ShamType.DETUNE, sham_seed=3)
        self.assertNotEqual(subject.target_freq, 40.0)
        self.assertEqual(subject.target_freq, twin.target_freq)

    def test_static_sham_normalizes_to_sine_hold(self):
        subject = engine.EntrainmentEngine(target_freq=40.0, waveform=engine.WaveformType.AM_CARRIER,
                                           sham_type=engine.ShamType.STATIC, sham_seed=1,
                                           phase_offset=90.0, right_phase_offset=180.0)
        self.assertEqual(subject.waveform, engine.WaveformType.SINE)
        self.assertEqual(subject.waveform_left, engine.WaveformType.SINE)
        self.assertEqual(subject.waveform_right, engine.WaveformType.SINE)
        self.assertEqual(subject.phase_offset_rad, 0.0)
        self.assertEqual(subject.right_phase_rad, 0.0)
        # Mean-luminance hold: SINE at phase 0 is 0.5
        self.assertAlmostEqual(
            subject.compute_cpu_signal(engine.WaveformType.SINE, 0.0, 0.0), 0.5)

    def test_allow_zero_normalizes_negative_zero(self):
        freq, _ = engine.FrequencyManager.validate_frequency(
            -0.0, 60, engine.WaveformType.SINE, allow_zero=True)
        self.assertEqual(freq, 0.0)
        self.assertFalse(str(freq).startswith("-"))


class CalibrationLoaderTests(unittest.TestCase):
    def _renderer_without_gl(self):
        renderer = engine.StimulusRenderer()
        for name, kwargs in (
            ("glGenTextures", {"return_value": 1}),
            ("glBindTexture", {}),
            ("glTexParameteri", {}),
            ("glTexImage1D", {}),
        ):
            patcher = mock.patch.object(engine, name, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        return renderer

    def _write(self, text):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                         encoding="utf-8", newline="") as handle:
            handle.write(text)
            path = handle.name
        self.addCleanup(os.unlink, path)
        return path

    def test_malformed_row_is_warned_and_skipped(self):
        renderer = self._renderer_without_gl()
        path = self._write("Input,Output\n0.0,0.1\n0.5,bad\n1.0,0.9\n")
        with self.assertLogs(engine.logger, level="WARNING") as logs:
            renderer.load_calibration(path)
        self.assertTrue(renderer.lut_active)
        self.assertTrue(any("Skipping malformed calibration row 3" in line for line in logs.output))

    def test_file_without_usable_rows_is_reported(self):
        renderer = self._renderer_without_gl()
        path = self._write("Input,Output\nbad,data\n")
        with self.assertLogs(engine.logger, level="WARNING") as logs:
            renderer.load_calibration(path)
        self.assertFalse(renderer.lut_active)
        self.assertTrue(any("no usable rows" in line for line in logs.output))

    def test_malformed_first_data_row_without_header_warns(self):
        renderer = self._renderer_without_gl()
        path = self._write("0.0,bad\n1.0,0.9\n")
        with self.assertLogs(engine.logger, level="WARNING") as logs:
            renderer.load_calibration(path)
        self.assertTrue(renderer.lut_active)
        self.assertTrue(any("Skipping malformed calibration row 1" in line for line in logs.output))


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
        self.assertFalse(args.dry_run)
        self.assertIsNone(args.protocol)

    def test_preset_theta_sets_frequency(self):
        original = sys.argv
        sys.argv = ["entrainment_engine.py", "--preset", "theta"]
        try:
            args = engine.parse_arguments()
            eng, _ = engine.build_engine_from_args(args)
        finally:
            sys.argv = original
        self.assertEqual(eng.target_freq, 6.0)

    def test_dry_run_flag_enabled(self):
        original = sys.argv
        sys.argv = ["entrainment_engine.py", "--dry-run", "--freq", "25.0"]
        try:
            args = engine.parse_arguments()
            eng, is_dry = engine.build_engine_from_args(args)
        finally:
            sys.argv = original
        self.assertTrue(is_dry)
        self.assertEqual(eng.target_freq, 25.0)

    def test_build_engine_from_declarative_protocol(self):
        import json
        proto_data = {
            "target_freq": 10.0,
            "waveform": "square",
            "mode": "split",
            "duration": 120.0,
            "ramp": 3.0,
            "sham": "none",
            "gamma": 2.2,
            "brightness": 0.8,
            "phase": 45.0,
            "right_freq": 12.0,
            "right_phase": 90.0
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(proto_data, tmp)
            tmp_path = tmp.name
        self.addCleanup(os.unlink, tmp_path)

        original = sys.argv
        sys.argv = ["entrainment_engine.py", "--protocol", tmp_path, "--dry-run"]
        try:
            args = engine.parse_arguments()
            eng, is_dry = engine.build_engine_from_args(args)
        finally:
            sys.argv = original

        self.assertTrue(is_dry)
        self.assertEqual(eng.target_freq, 10.0)
        self.assertEqual(eng.waveform, engine.WaveformType.SQUARE)
        self.assertEqual(eng.mode, engine.StimulationMode.SPLIT_HEMIFIELD)
        self.assertEqual(eng.session_duration, 120.0)
        self.assertEqual(eng.right_freq, 12.0)

    def test_sham_seed_propagates_from_cli(self):
        original = sys.argv
        sys.argv = ["entrainment_engine.py", "--sham", "detune", "--sham-seed", "42"]
        try:
            args = engine.parse_arguments()
            eng, _ = engine.build_engine_from_args(args)
        finally:
            sys.argv = original
        self.assertEqual(eng.sham_seed, 42)
        self.assertEqual(eng.target_freq, engine.EntrainmentEngine(
            target_freq=40.0, waveform=engine.WaveformType.SINE,
            sham_type=engine.ShamType.DETUNE, sham_seed=42).target_freq)

    def test_sham_seed_propagates_from_declarative_protocol(self):
        import json
        proto_data = {"target_freq": 40.0, "sham": "jitter", "sham_seed": 7}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(proto_data, tmp)
            tmp_path = tmp.name
        self.addCleanup(os.unlink, tmp_path)

        original = sys.argv
        sys.argv = ["entrainment_engine.py", "--protocol", tmp_path, "--dry-run"]
        try:
            args = engine.parse_arguments()
            eng, _ = engine.build_engine_from_args(args)
        finally:
            sys.argv = original
        self.assertEqual(eng.sham_seed, 7)


class DryRunSafetyTests(unittest.TestCase):
    """Dry-run must apply the same hardware validation the live path enforces."""

    @classmethod
    def setUpClass(cls):
        cls.cwd = os.path.dirname(os.path.abspath(__file__))

    def test_dry_run_rejects_impossible_frequency(self):
        # 500 Hz exceeds the Nyquist ceiling of any consumer display.
        proc = subprocess.run(
            [sys.executable, "entrainment_engine.py", "--dry-run", "--freq", "500.0"],
            capture_output=True, text=True, timeout=30, cwd=self.cwd)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("safe representable limit", proc.stderr)

    def test_dry_run_accepts_safe_frequency_and_reports_risk(self):
        # 10 Hz is below the Nyquist ceiling of every consumer display.
        proc = subprocess.run(
            [sys.executable, "entrainment_engine.py", "--dry-run", "--freq", "10.0"],
            capture_output=True, text=True, timeout=30, cwd=self.cwd)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("photic risk", proc.stderr)


if __name__ == "__main__":
    unittest.main()
