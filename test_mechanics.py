"""Unit test suite for NeuroOptic headless mechanics, protocol schemas, and safety validation."""

import os
import sys
import unittest
from unittest import mock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

from core.protocol import (
    EntrainmentProtocol,
    PRESETS,
    ShamType,
    StimulationMode,
    WaveformType,
)
from core.safety import (
    RiskTier,
    calculate_photic_risk,
    validate_hardware_limits,
)
from core.session_controller import (
    SessionController,
    SessionState,
)


class ProtocolModelTests(unittest.TestCase):
    def test_presets_include_canonical_bands(self):
        self.assertIn("Delta", PRESETS)
        self.assertIn("Theta", PRESETS)
        self.assertEqual(PRESETS["Theta"], 6.0)
        self.assertIn("Alpha", PRESETS)
        self.assertIn("Beta", PRESETS)
        self.assertIn("Gamma", PRESETS)
        self.assertIn("High Gamma", PRESETS)

    def test_protocol_default_construction(self):
        proto = EntrainmentProtocol()
        self.assertEqual(proto.target_freq, 40.0)
        self.assertEqual(proto.waveform, WaveformType.SINE)
        self.assertEqual(proto.mode, StimulationMode.FULL_SCREEN)
        self.assertEqual(proto.duration, 0.0)

    def test_protocol_dict_roundtrip(self):
        proto = EntrainmentProtocol(
            target_freq=10.0,
            waveform=WaveformType.SQUARE,
            mode=StimulationMode.SPLIT_HEMIFIELD,
            duration=300.0,
            ramp=5.0,
            sham=ShamType.DETUNE,
            right_freq=11.0,
            right_phase=180.0,
        )
        data = proto.to_dict()
        reconstructed = EntrainmentProtocol.from_dict(data)
        self.assertEqual(proto, reconstructed)

    def test_protocol_cli_args_generation(self):
        proto = EntrainmentProtocol(
            target_freq=20.0,
            waveform=WaveformType.TRIANGLE,
            mode=StimulationMode.PERIPHERAL_RING,
            duration=60.0,
        )
        args = proto.to_cli_args()
        self.assertIn("--freq", args)
        self.assertIn("20.0", args)
        self.assertIn("--waveform", args)
        self.assertIn("triangle", args)
        self.assertIn("--mode", args)
        self.assertIn("ring", args)


class SafetyValidationTests(unittest.TestCase):
    def test_square_wave_in_photic_window_is_high_risk(self):
        assessment = calculate_photic_risk(15.0, WaveformType.SQUARE)
        self.assertEqual(assessment.tier, RiskTier.HIGH_RISK_PSE)
        self.assertTrue(assessment.requires_human_confirmation)
        self.assertGreaterEqual(assessment.score, 0.9)

    def test_sine_wave_in_photic_window_is_caution(self):
        assessment = calculate_photic_risk(10.0, WaveformType.SINE)
        self.assertEqual(assessment.tier, RiskTier.CAUTION)
        self.assertFalse(assessment.requires_human_confirmation)

    def test_gamma_frequency_is_safe(self):
        assessment = calculate_photic_risk(40.0, WaveformType.SINE)
        self.assertEqual(assessment.tier, RiskTier.SAFE)
        self.assertFalse(assessment.requires_human_confirmation)

    def test_static_hold_is_safe(self):
        assessment = calculate_photic_risk(0.0, WaveformType.SINE)
        self.assertEqual(assessment.tier, RiskTier.SAFE)
        self.assertEqual(assessment.score, 0.0)

    def test_nyquist_exceeded_raises_error(self):
        with self.assertRaises(ValueError):
            validate_hardware_limits(35.0, 60, WaveformType.SINE)

    def test_non_integer_square_degrades_to_sine(self):
        freq, wf = validate_hardware_limits(7.0, 60, WaveformType.SQUARE)
        self.assertEqual((freq, wf), (7.0, WaveformType.SINE))

    def test_allow_zero_static_pass(self):
        freq, wf = validate_hardware_limits(0.0, 60, WaveformType.SINE, allow_zero=True)
        self.assertEqual(freq, 0.0)


class SessionControllerTests(unittest.TestCase):
    def test_controller_initial_state_idle(self):
        proto = EntrainmentProtocol(target_freq=40.0)
        controller = SessionController(proto)
        self.assertEqual(controller.state, SessionState.IDLE)

    def test_controller_validation_updates_state(self):
        proto = EntrainmentProtocol(target_freq=40.0)
        controller = SessionController(proto)
        assessment = controller.validate(refresh_rate=120)
        self.assertEqual(controller.state, SessionState.VALIDATED)
        self.assertEqual(assessment.tier, RiskTier.SAFE)

    def test_controller_build_command(self):
        proto = EntrainmentProtocol(target_freq=10.0, waveform=WaveformType.SINE)
        controller = SessionController(proto, engine_path="/mock/engine.py")
        cmd = controller.build_command(python_exe="python")
        self.assertEqual(cmd[0], "python")
        self.assertEqual(cmd[1], "/mock/engine.py")
        self.assertIn("--freq", cmd)
        self.assertIn("10.0", cmd)

    def test_controller_start_and_stop_mocked(self):
        proto = EntrainmentProtocol(target_freq=40.0)
        mock_proc = mock.MagicMock()
        mock_proc.poll.return_value = None  # Process is running

        with mock.patch("os.path.exists", return_value=True):
            controller = SessionController(proto, engine_path="/mock/engine.py")
            controller.start_session(popen_fn=lambda cmd: mock_proc)
            self.assertEqual(controller.state, SessionState.RUNNING)
            self.assertEqual(controller.process, mock_proc)

            stopped = controller.stop_session()
            self.assertTrue(stopped)
            self.assertEqual(controller.state, SessionState.TERMINATED)
            mock_proc.terminate.assert_called_once()


class ProtocolDegrationTests(unittest.TestCase):
    """Controller must apply the degraded waveform so risk matches execution."""

    def test_validation_applies_duty_cycle_degradation_to_protocol(self):
        proto = EntrainmentProtocol(target_freq=13.0, waveform=WaveformType.SQUARE)
        controller = SessionController(proto)
        assessment = controller.validate(refresh_rate=60)
        self.assertEqual(controller.protocol.waveform, WaveformType.SINE)
        self.assertEqual(assessment.tier, RiskTier.CAUTION)
        self.assertFalse(assessment.requires_human_confirmation)

    def test_validation_keeps_exactly_representable_square(self):
        proto = EntrainmentProtocol(target_freq=10.0, waveform=WaveformType.SQUARE)
        controller = SessionController(proto)
        assessment = controller.validate(refresh_rate=60)
        self.assertEqual(controller.protocol.waveform, WaveformType.SQUARE)
        self.assertEqual(assessment.tier, RiskTier.HIGH_RISK_PSE)
        self.assertTrue(assessment.requires_human_confirmation)


class ShamSeedReproducibilityTests(unittest.TestCase):
    """Sham seed must survive a controller subprocess launch for replayable sham conditions."""

    def test_protocol_cli_args_include_explicit_sham_seed(self):
        proto = EntrainmentProtocol(target_freq=40.0, sham=ShamType.PHASE_JITTER, sham_seed=42)
        args = proto.to_cli_args()
        idx = args.index("--sham-seed")
        self.assertEqual(str(args[idx + 1]), "42")

    def test_protocol_cli_args_omit_unset_sham_seed(self):
        proto = EntrainmentProtocol(target_freq=40.0, sham=ShamType.PHASE_JITTER)
        self.assertNotIn("--sham-seed", proto.to_cli_args())


if __name__ == "__main__":
    unittest.main()
