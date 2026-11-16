"""Automated headless unit test suite for NeuroOpticLauncher GUI controller."""

import os
import sys
import unittest
from unittest import mock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(__file__))

import customtkinter as ctk
from launcher import NeuroOpticLauncher


class HeadlessLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()
        cls.app = NeuroOpticLauncher(cls.root, headless=True)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.update()
        except (AttributeError, RuntimeError):  # hygiene: allow cleanup update; root might already be destroyed
            pass
        cls.root.destroy()

    def setUp(self):
        self.app.freq_var.set("40.0")
        self.app.waveform_var.set("Sine")
        self.app.mode_var.set("Full")
        self.app.duration_var.set("0.0")
        self.app.ramp_var.set("0.0")
        self.app.sham_var.set("None")
        self.app.gamma_var.set("1.0")
        self.app.brightness_var.set("1.0")
        self.app.phase_var.set("0.0")
        self.app.right_freq_var.set("0.0")
        self.app.right_phase_var.set("0.0")
        self.app.confirm_var.set(False)
        self.app.last_error = None
        self.app.last_warning = None
        self.app.update_safety_evaluation()

    def test_default_state_and_safe_badge(self):
        self.assertEqual(self.app.freq_var.get(), "40.0")
        self.assertEqual(self.app.waveform_var.get(), "Sine")
        self.assertEqual(self.app.mode_var.get(), "Full")
        self.assertIn("[SAFE]", self.app.safety_badge.cget("text"))
        self.assertEqual(self.app.launch_btn.cget("state"), "normal")
        self.assertEqual(self.app.abort_btn.cget("state"), "disabled")
        self.assertIsNotNone(self.app.quick_gamma_btn)
        self.assertIsNotNone(self.app.quick_alpha_btn)
        self.assertIsNotNone(self.app.tabview)
        self.assertIsNotNone(self.app.freq_slider)
        self.assertIsNotNone(self.app.waveform_seg)

    def test_tabview_and_slider_synchronization(self):
        # Tabview switching
        self.assertEqual(self.app.tabview.get(), "⚡ Protocol & Session")
        self.app.tabview.set("🔬 Advanced & Sham")
        self.assertEqual(self.app.tabview.get(), "🔬 Advanced & Sham")
        self.app.tabview.set("⚡ Protocol & Session")

        # Slider to var
        self.app._on_slider_change(25.0)
        self.assertEqual(self.app.freq_var.get(), "25.0")

        # Var to slider
        self.app.freq_var.set("18.5")
        self.assertAlmostEqual(self.app.freq_slider.get(), 18.5, delta=0.2)

    def test_quick_start_gamma(self):
        with mock.patch.object(self.app, "_probe_engine", return_value=(True, "")):
            with mock.patch("subprocess.Popen") as mock_popen:
                self.app.quick_start("gamma")
                self.assertEqual(self.app.freq_var.get(), "40.0")
                self.assertEqual(self.app.waveform_var.get(), "Sine")
                self.assertEqual(self.app.ramp_var.get(), "5.0")
                self.assertIn("[SAFE]", self.app.safety_badge.cget("text"))
                self.assertEqual(self.app.launch_btn.cget("state"), "normal")
                mock_popen.assert_called_once()

    def test_quick_start_alpha(self):
        with mock.patch.object(self.app, "_probe_engine", return_value=(True, "")):
            with mock.patch("subprocess.Popen") as mock_popen:
                self.app.quick_start("alpha")
                self.assertEqual(self.app.freq_var.get(), "10.0")
                self.assertEqual(self.app.waveform_var.get(), "Sine")
                self.assertEqual(self.app.ramp_var.get(), "5.0")
                self.assertIn("[CAUTION]", self.app.safety_badge.cget("text"))
                self.assertEqual(self.app.launch_btn.cget("state"), "normal")
                mock_popen.assert_called_once()

    def test_launch_preflight_blocks_display_incompatible_protocol(self):
        # ADR-007: the launcher preflights with the engine's dry-run, so a 40 Hz
        # request on a <85 Hz display stops with a remediation error, not a doomed window.
        self.app.freq_var.set("40.0")
        self.app.waveform_var.set("Sine")
        self.app.update_safety_evaluation()

        with mock.patch.object(self.app, "_probe_engine",
                               return_value=(False, "exceeds safe representable limit (29.5 Hz)")):
            with mock.patch("subprocess.Popen") as mock_popen:
                self.app.launch_engine()

        self.assertIsNotNone(self.app.last_error)
        self.assertEqual(self.app.last_error[0], "Launch preflight failed")
        self.assertIn("refresh", self.app.last_error[1])
        mock_popen.assert_not_called()

    def test_preset_change_theta_and_bands(self):
        self.app.on_preset_change("Theta (6Hz)")
        self.assertEqual(self.app.freq_var.get(), "6.0")

        self.app.on_preset_change("Alpha (10Hz)")
        self.assertEqual(self.app.freq_var.get(), "10.0")

        self.app.on_preset_change("Gamma (40Hz)")
        self.assertEqual(self.app.freq_var.get(), "40.0")

    def test_high_risk_pse_disables_start_button(self):
        self.app.freq_var.set("15.0")
        self.app.waveform_var.set("Square")
        self.app.update_safety_evaluation()

        self.assertIn("[HIGH RISK - PSE]", self.app.safety_badge.cget("text"))
        self.assertEqual(self.app.launch_btn.cget("state"), "disabled")

    def test_high_risk_authorization_enables_start_button(self):
        self.app.freq_var.set("15.0")
        self.app.waveform_var.set("Square")
        self.app.update_safety_evaluation()
        self.assertEqual(self.app.launch_btn.cget("state"), "disabled")

        # Authorize high risk
        self.app.confirm_var.set(True)
        self.app.update_safety_evaluation()
        self.assertEqual(self.app.launch_btn.cget("state"), "normal")

    def test_caution_tier_for_smooth_waveform_in_driving_band(self):
        self.app.freq_var.set("12.0")
        self.app.waveform_var.set("Sine")
        self.app.update_safety_evaluation()

        self.assertIn("[CAUTION]", self.app.safety_badge.cget("text"))
        self.assertEqual(self.app.launch_btn.cget("state"), "normal")

    def test_invalid_frequency_records_error_without_popup(self):
        self.app.freq_var.set("invalid_number")
        self.app.launch_engine()

        self.assertIsNotNone(self.app.last_error)
        self.assertEqual(self.app.last_error[0], "Invalid input")
        self.assertIn("Target Frequency must be a number", self.app.last_error[1])

    def test_negative_frequency_rejected(self):
        self.app.freq_var.set("-5.0")
        self.app.launch_engine()

        self.assertIsNotNone(self.app.last_error)
        self.assertEqual(self.app.last_error[0], "Invalid input")

    def test_right_frequency_warning_outside_split_mode(self):
        self.app.mode_var.set("Full")
        self.app.right_freq_var.set("12.0")

        with mock.patch.object(self.app, "_probe_engine", return_value=(True, "")):
            with mock.patch("subprocess.Popen") as mock_popen:
                self.app.launch_engine()

        self.assertIsNotNone(self.app.last_warning)
        self.assertEqual(self.app.last_warning[0], "Right frequency ignored")

    def test_mocked_launch_and_stop_lifecycle(self):
        mock_proc = mock.MagicMock()
        mock_proc.poll.return_value = None  # Running

        with mock.patch.object(self.app, "_probe_engine", return_value=(True, "")):
            with mock.patch("subprocess.Popen", return_value=mock_proc):
                self.app.launch_engine()
                self.assertEqual(self.app.current_process, mock_proc)
                self.assertEqual(self.app.abort_btn.cget("state"), "normal")

                self.app.stop_engine()
                self.assertIsNone(self.app.current_process)
                self.assertEqual(self.app.abort_btn.cget("state"), "disabled")
                mock_proc.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
