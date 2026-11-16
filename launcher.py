import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Tuple
import customtkinter as ctk

from core.protocol import PRESETS, StimulationMode, WaveformType
from core.safety import RiskTier, calculate_photic_risk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class NeuroOpticLauncher:
    def __init__(self, root, headless: bool = False):
        self.root = root
        self.headless = headless
        self.last_error: Optional[Tuple[str, str]] = None
        self.last_warning: Optional[Tuple[str, str]] = None
        self.current_process: Optional[subprocess.Popen] = None

        if hasattr(self.root, "title"):
            self.root.title("NeuroOptic Controller")
            self.root.geometry("520x680")

        # --- Header ---
        header_box = ctk.CTkFrame(root, fg_color="transparent")
        header_box.pack(pady=(10, 2))
        header = ctk.CTkLabel(header_box, text="NEUROOPTIC", font=("Segoe UI", 20, "bold"), text_color="#f3f4f6")
        header.pack()
        sub_header = ctk.CTkLabel(header_box, text="Visual Entrainment & Photic Oscillator",
                                  font=("Segoe UI", 10), text_color="#9ca3af")
        sub_header.pack()

        # --- Main Container ---
        main_frame = ctk.CTkFrame(root, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=16, pady=2)

        # --- Tabview Workspace ---
        self.tabview = ctk.CTkTabview(main_frame, height=340)
        self.tabview.pack(fill="x", pady=(0, 4))
        self.tab_session = self.tabview.add("⚡ Protocol & Session")
        self.tab_advanced = self.tabview.add("🔬 Advanced & Sham")

        # === TAB 1: Protocol & Session ===
        quick_frame = self.create_group_frame(self.tab_session, "Quick Brainwave Presets")
        self.quick_gamma_btn = ctk.CTkButton(
            quick_frame, text="⚡ 40Hz Gamma (Focus)",
            command=lambda: self.quick_start("gamma"),
            fg_color="#2b8a3e", hover_color="#237032", height=30
        )
        self.quick_gamma_btn.grid(row=1, column=0, padx=6, pady=4, sticky="ew")
        self.quick_alpha_btn = ctk.CTkButton(
            quick_frame, text="⚡ 10Hz Alpha (Relax)",
            command=lambda: self.quick_start("alpha"),
            fg_color="#1971c2", hover_color="#1864ab", height=30
        )
        self.quick_alpha_btn.grid(row=1, column=1, padx=6, pady=4, sticky="ew")
        quick_frame.columnconfigure((0, 1), weight=1)

        self.preset_var = ctk.StringVar(value="Custom")
        preset_values = ['Custom', 'Delta (2Hz)', 'Theta (6Hz)', 'Alpha (10Hz)', 'Beta (20Hz)', 'Gamma (40Hz)', 'High Gamma (80Hz)']
        ctk.CTkLabel(quick_frame, text="All Bands:").grid(row=2, column=0, sticky="w", padx=10, pady=(2, 6))
        self.preset_combo = ctk.CTkComboBox(quick_frame, variable=self.preset_var, state="readonly",
                                            values=preset_values, command=self.on_preset_change)
        self.preset_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=(2, 6))

        freq_frame = self.create_group_frame(self.tab_session, "Frequency & Waveform")
        ctk.CTkLabel(freq_frame, text="Target Frequency (Hz):").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.freq_var = ctk.StringVar(value="40.0")
        self.freq_var.trace_add("write", self.update_safety_evaluation)
        self.freq_entry = ctk.CTkEntry(freq_frame, textvariable=self.freq_var, width=80)
        self.freq_entry.grid(row=1, column=1, sticky="e", padx=10, pady=4)

        self.freq_slider = ctk.CTkSlider(freq_frame, from_=1.0, to=80.0, command=self._on_slider_change)
        self.freq_slider.set(40.0)
        self.freq_slider.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 6))

        ctk.CTkLabel(freq_frame, text="Waveform Profile:").grid(row=3, column=0, sticky="w", padx=10, pady=(4, 2))
        self.waveform_var = ctk.StringVar(value="Sine")
        self.waveform_var.trace_add("write", self.update_safety_evaluation)
        self.waveform_seg = ctk.CTkSegmentedButton(freq_frame, values=['Sine', 'Square', 'AM', 'Triangle'],
                                                  variable=self.waveform_var,
                                                  command=lambda _: self.update_safety_evaluation())
        self.waveform_seg.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8))
        self.waveform_combo = self.waveform_seg
        freq_frame.columnconfigure((0, 1), weight=1)

        session_frame = self.create_group_frame(self.tab_session, "Session Timing")
        ctk.CTkLabel(session_frame, text="Duration (s, 0=Inf):").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.duration_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(session_frame, textvariable=self.duration_var, width=70).grid(row=1, column=1, sticky="e", padx=6, pady=4)

        ctk.CTkLabel(session_frame, text="Ramp Up (s):").grid(row=1, column=2, sticky="w", padx=10, pady=4)
        self.ramp_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(session_frame, textvariable=self.ramp_var, width=70).grid(row=1, column=3, sticky="e", padx=10, pady=4)
        session_frame.columnconfigure((0, 1, 2, 3), weight=1)

        # === TAB 2: Advanced & Sham ===
        vis_frame = self.create_group_frame(self.tab_advanced, "Stimulation Mode & Phase")
        ctk.CTkLabel(vis_frame, text="Mode:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.mode_var = ctk.StringVar(value="Full")
        self.mode_combo = ctk.CTkComboBox(vis_frame, variable=self.mode_var, state="readonly", width=120,
                                          values=['Full', 'Ring', 'Left', 'Right', 'Split', 'Quad_TL', 'Quad_TR', 'Quad_BL', 'Quad_BR'])
        self.mode_combo.grid(row=1, column=1, sticky="e", padx=6, pady=4)

        ctk.CTkLabel(vis_frame, text="Phase (°):").grid(row=1, column=2, sticky="w", padx=10, pady=4)
        self.phase_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(vis_frame, textvariable=self.phase_var, width=65).grid(row=1, column=3, sticky="e", padx=10, pady=4)
        vis_frame.columnconfigure((0, 1, 2, 3), weight=1)

        split_frame = self.create_group_frame(self.tab_advanced, "Split Hemifield / Binaural")
        ctk.CTkLabel(split_frame, text="R-Freq (Hz):").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.right_freq_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(split_frame, textvariable=self.right_freq_var, width=65).grid(row=1, column=1, sticky="e", padx=6, pady=4)

        ctk.CTkLabel(split_frame, text="R-Phase (°):").grid(row=1, column=2, sticky="w", padx=10, pady=4)
        self.right_phase_var = ctk.StringVar(value="0.0")
        ctk.CTkEntry(split_frame, textvariable=self.right_phase_var, width=65).grid(row=1, column=3, sticky="e", padx=10, pady=4)
        split_frame.columnconfigure((0, 1, 2, 3), weight=1)

        sham_frame = self.create_group_frame(self.tab_advanced, "Research / Sham Placebo")
        ctk.CTkLabel(sham_frame, text="Sham Condition:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.sham_var = ctk.StringVar(value="None")
        self.sham_combo = ctk.CTkComboBox(sham_frame, variable=self.sham_var, state="readonly",
                                          values=['None', 'Detune', 'Low_Amp', 'Jitter', 'Static'])
        self.sham_combo.grid(row=1, column=1, sticky="e", padx=10, pady=4)
        sham_frame.columnconfigure((0, 1), weight=1)

        display_frame = self.create_group_frame(self.tab_advanced, "Display Calibration")
        ctk.CTkLabel(display_frame, text="Gamma:").grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.gamma_var = ctk.StringVar(value="1.0")
        ctk.CTkEntry(display_frame, textvariable=self.gamma_var, width=65).grid(row=1, column=1, sticky="e", padx=6, pady=4)

        ctk.CTkLabel(display_frame, text="Brightness:").grid(row=1, column=2, sticky="w", padx=10, pady=4)
        self.brightness_var = ctk.StringVar(value="1.0")
        ctk.CTkEntry(display_frame, textvariable=self.brightness_var, width=65).grid(row=1, column=3, sticky="e", padx=10, pady=4)
        display_frame.columnconfigure((0, 1, 2, 3), weight=1)

        # === PERSISTENT FOOTER: Bio-Safety & Controls ===
        safety_frame = self.create_group_frame(main_frame, "Bio-Safety & Photic Assessment")
        self.safety_badge = ctk.CTkLabel(safety_frame, text="[SAFE] Low photic driving risk",
                                         font=("Segoe UI", 11, "bold"), text_color="#2f9e44")
        self.safety_badge.grid(row=1, column=0, columnspan=4, sticky="w", padx=10, pady=(2, 2))

        self.confirm_var = ctk.BooleanVar(value=False)
        self.confirm_chk = ctk.CTkCheckBox(safety_frame, text="Authorize high-risk photic stimulation (PSE window)",
                                           variable=self.confirm_var, command=self.update_safety_evaluation)
        self.confirm_chk.grid(row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(2, 6))

        # Action Buttons
        btn_box = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_box.pack(fill="x", pady=(6, 2))
        self.launch_btn = ctk.CTkButton(btn_box, text="START", command=self.launch_engine,
                                        font=("Segoe UI", 12, "bold"), height=36,
                                        fg_color="#059669", hover_color="#047857")
        self.launch_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.abort_btn = ctk.CTkButton(btn_box, text="STOP", command=self.stop_engine,
                                       font=("Segoe UI", 12, "bold"), height=36,
                                       fg_color="#c92a2a", hover_color="#a61e1e", state="disabled")
        self.abort_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))

        ctk.CTkLabel(main_frame, text="Press ESC in engine window or click STOP to exit.",
                     font=("Segoe UI", 9, "italic"), text_color="#6b7280").pack(pady=(2, 4))
        self.update_safety_evaluation()

    def _on_slider_change(self, val):
        self.freq_var.set(f"{val:.1f}")

    def create_group_frame(self, parent, title):
        frame = ctk.CTkFrame(parent)
        frame.pack(fill="x", pady=3)
        if title:
            title_lbl = ctk.CTkLabel(frame, text=title, font=("Segoe UI", 11, "bold"), text_color="#cbd5e1")
            title_lbl.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(3, 0))
        return frame
        frame.pack(fill="x", pady=4)
        title_lbl = ctk.CTkLabel(frame, text=title, font=("Segoe UI", 12, "bold"))
        title_lbl.grid(row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(4, 0))
        return frame

    def create_help_btn(self, parent, message):
        return ctk.CTkButton(parent, text="?", width=18, height=18, corner_radius=9,
                             fg_color="transparent", border_width=1, border_color="gray",
                             text_color="gray", hover_color=("#444", "#444"),
                             command=lambda: messagebox.showinfo("Help", message) if not self.headless else None)

    def report_error(self, title: str, message: str):
        self.last_error = (title, message)
        if not self.headless:
            messagebox.showerror(title, message)

    def report_warning(self, title: str, message: str):
        self.last_warning = (title, message)
        if not self.headless:
            messagebox.showwarning(title, message)

    def quick_start(self, preset: str = "gamma"):
        """One-click start with verified bio-safe parameters (PRINCIPLE-011)."""
        is_alpha = preset.lower() == "alpha"
        self.freq_var.set("10.0" if is_alpha else "40.0")
        self.preset_var.set("Alpha (10Hz)" if is_alpha else "Gamma (40Hz)")
        self.waveform_var.set("Sine")
        self.mode_var.set("Full")
        self.ramp_var.set("5.0")
        self.sham_var.set("None")
        self.duration_var.set("0.0")
        self.update_safety_evaluation()
        self.launch_engine()

    def on_preset_change(self, choice):
        for name, hz in PRESETS.items():
            if name.lower() in choice.lower():
                self.freq_var.set(str(hz))
                break
        self.update_safety_evaluation()

    def update_safety_evaluation(self, *args):
        try:
            freq = float(str(self.freq_var.get()).strip())
            if hasattr(self, "freq_slider") and 1.0 <= freq <= 80.0:
                try:
                    if abs(self.freq_slider.get() - freq) > 0.05:
                        self.freq_slider.set(freq)
                except (ValueError, RuntimeError, tk.TclError):  # hygiene: allow slider sync ignore; slider might be unmapped during headless init
                    pass
            wf_str = str(self.waveform_var.get()).upper()
            wf = WaveformType[wf_str]
        except (ValueError, KeyError):
            return

        assessment = calculate_photic_risk(freq, wf)
        if assessment.tier == RiskTier.HIGH_RISK_PSE:
            self.safety_badge.configure(text=f"[HIGH RISK - PSE] {assessment.warning_message}", text_color="#e03131")
            self.launch_btn.configure(state="normal" if self.confirm_var.get() else "disabled")
        elif assessment.tier == RiskTier.CAUTION:
            self.safety_badge.configure(text=f"[CAUTION] {assessment.warning_message}", text_color="#f59f00")
            self.launch_btn.configure(state="normal")
        else:
            self.safety_badge.configure(text="[SAFE] Low photic driving risk", text_color="#2f9e44")
            self.launch_btn.configure(state="normal")

    def _parse_float(self, raw, label, min_val=None, max_val=None):
        try:
            val = float(str(raw).strip())
        except (TypeError, ValueError):
            self.report_error("Invalid input", f"{label} must be a number (got {raw!r}).")
            return None
        if min_val is not None and val < min_val:
            self.report_error("Invalid input", f"{label} must be >= {min_val} (got {val}).")
            return None
        if max_val is not None and val > max_val:
            self.report_error("Invalid input", f"{label} must be <= {max_val} (got {val}).")
            return None
        return val

    def launch_engine(self):
        script_path = os.path.join(os.path.dirname(__file__), 'entrainment_engine.py')
        if not os.path.exists(script_path):
            self.report_error("Error", f"Could not find engine script at:\n{script_path}")
            return

        sham = self.sham_var.get().lower()
        if sham not in ('none', 'detune', 'low_amp', 'jitter', 'static'):
            self.report_error("Invalid input", f"Unknown sham condition: {self.sham_var.get()!r}.")
            return
        waveform = self.waveform_var.get().lower()
        if waveform not in ('sine', 'square', 'am', 'triangle'):
            self.report_error("Invalid input", f"Unknown waveform: {self.waveform_var.get()!r}.")
            return
        mode = self.mode_var.get().lower()
        if mode not in ('full', 'ring', 'left', 'right', 'split', 'quad_tl', 'quad_tr', 'quad_bl', 'quad_br'):
            self.report_error("Invalid input", f"Unknown mode: {self.mode_var.get()!r}.")
            return

        freq = self._parse_float(self.freq_var.get(), "Target Frequency", min_val=0.0)
        if freq is None or (freq <= 0 and sham != 'static'):
            if freq == 0 and sham != 'static':
                self.report_error("Invalid input", "Target Frequency must be > 0 unless Sham is Static.")
            return

        duration = self._parse_float(self.duration_var.get(), "Duration", min_val=0.0)
        ramp = self._parse_float(self.ramp_var.get(), "Ramp Up", min_val=0.0)
        gamma = self._parse_float(self.gamma_var.get(), "Gamma", min_val=0.1, max_val=4.0)
        brightness = self._parse_float(self.brightness_var.get(), "Brightness", min_val=0.0, max_val=1.0)
        phase = self._parse_float(self.phase_var.get(), "Phase", min_val=0.0, max_val=360.0)
        r_freq = self._parse_float(self.right_freq_var.get(), "R-Freq", min_val=0.0)
        r_phase = self._parse_float(self.right_phase_var.get(), "R-Phase", min_val=0.0, max_val=360.0)
        if None in (duration, ramp, gamma, brightness, phase, r_freq, r_phase):
            return

        if mode != 'split' and r_freq not in (0.0, freq):
            self.report_warning("Right frequency ignored",
                                f"R-Freq ({r_freq} Hz) only takes effect in Split mode; display will use {freq} Hz.")

        cmd = [sys.executable, script_path, '--freq', str(freq), '--waveform', waveform, '--mode', mode,
               '--duration', str(duration), '--ramp', str(ramp), '--sham', sham, '--gamma', str(gamma),
               '--brightness', str(brightness), '--phase', str(phase), '--phase-right', str(r_phase)]
        if r_freq > 0:
            cmd.extend(['--freq-right', str(r_freq)])

        try:
            self.current_process = subprocess.Popen(cmd)  # hygiene: allow fire-and-forget launch; the engine must outlive the launcher
            self.abort_btn.configure(state="normal")
        except Exception as e:
            self.report_error("Launch Error", str(e))

    def stop_engine(self):
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            self.current_process = None
        self.abort_btn.configure(state="disabled")


if __name__ == "__main__":
    root = ctk.CTk()
    app = NeuroOpticLauncher(root)
    root.mainloop()
