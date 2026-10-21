# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document provides an automated, up-to-date registry of all modules, classes, and exported functions across this repository.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `3`
- **Total Classes**: `14`
- **Total Top-Level Functions**: `1`
- **Total Class Methods**: `45`
- **Total Source Lines**: `1374`

---

## 📦 Modules & Exported Symbols

### [`entrainment_engine.py`](entrainment_engine.py)
> *NeuroOptic - Generalized Visual Entrainment Engine (Gamma-Optimized)*

**Size**: `1070` lines (`42603` bytes)

**Classes:**
- `class WaveformType`
- `class ShamType`
- `class StimulationMode`
- `class FrequencyBand`
- `class FrequencyManager` - *Manages frequency bands and validates targets against hardware limits.*
  - Method `.get_band_name(frequency)`
  - Method `.validate_frequency(target_freq, refresh_rate, waveform)` - *Calculates safe frequency ceiling (Nyquist limit) and validates.*
- `class PhaseOscillator` - *True Frame-Locked Phase Accumulator.*
  - Method `.__init__(frequency, waveform, phase_offset, rng)`
  - Method `.set_phase_jitter(amount)`
  - Method `.set_carrier_frequency(freq)`
  - Method `.set_frequency(new_freq, current_t)` - *Updates frequency. Phase continuity is automatically preserved *
  - Method `.update_phase(delta_rad)` - *Injects a phase shift (e.g., for closed-loop error correction).*
  - Method `.step(refresh_rate)` - *Advances the oscillator by one frame step.*
  - Method `.get_phase_state()` - *Returns (modulator_phase, carrier_phase) with jitter applied.*
- `class StimulusRenderer` - *Modern OpenGL (GLSL) Renderer.*
  - Method `.__init__()`
  - Method `.init_gl()`
  - Method `.load_calibration(filepath)` - *Loads a CSV (Input, Output) and creates a 1D Texture LUT.*
  - Method `.get_last_gpu_duration()` - *Returns the GPU execution time of the previous frame in nanoseconds.*
  - Method `.render(phase_l, c_phase_l, phase_r, c_phase_r, wf_l, wf_r, amp_l, amp_r, mode, gamma)`
- `class EntrainmentEngine`
  - Method `.__init__(target_freq, waveform, mode, ramp_duration, session_duration, sham_type, sham_seed, gamma, brightness, phase_offset, right_freq, right_phase_offset, calibration_file, compat_mode)`
  - Method `.initialize_hardware()` - *Initializes GLFW, detects monitor specs, and sets up the window.*
  - Method `.set_frequency(freq)`
  - Method `.update_phase(delta_deg)`
  - Method `.compute_cpu_signal(waveform, phase, carrier_phase)` - *Mirrors the GLSL shader logic to compute exact signal value on CPU for logging.*
  - Method `.run()` - *Main Rendering Loop.*
  - Method `.analyze_session()` - *Computes session metrics and saves a publishable CSV report.*
  - Method `.generate_matlab_loader(csv_path)`
  - Method `.cleanup()`

**Functions:**
- `def parse_arguments()`

---

### [`launcher.py`](launcher.py)
**Size**: `186` lines (`11757` bytes)

**Classes:**
- `class NeuroOpticLauncher`
  - Method `.__init__(root)`
  - Method `.create_group_frame(parent, title)`
  - Method `.create_help_btn(parent, message)`
  - Method `.on_preset_change(choice)`
  - Method `.launch_engine()`

---

### [`test_entrainment_engine.py`](test_entrainment_engine.py)
> *Regression shield for NeuroOptic's pure engine logic; no window or GL context is needed.*

**Size**: `118` lines (`5593` bytes)

**Classes:**
- `class FrequencyManagerTests`
  - Method `.test_band_names_cover_preset_ranges()`
  - Method `.test_frequency_above_nyquist_limit_is_rejected()`
  - Method `.test_non_positive_frequency_is_rejected()`
  - Method `.test_square_with_non_integer_frames_switches_to_sine()`
  - Method `.test_square_with_integer_frames_is_kept()`
- `class PhaseOscillatorTests`
  - Method `.test_step_accumulates_phase_per_frame()`
  - Method `.test_phase_wraps_within_one_cycle()`
  - Method `.test_carrier_advances_only_for_am_waveform()`
  - Method `.test_jitter_stays_bounded_and_reproducible()`
- `class SignalMathTests`
  - Method `.setUp()`
  - Method `.test_sine_signal_swings_full_range()`
  - Method `.test_square_signal_is_binary()`
  - Method `.test_triangle_signal_peaks_at_half_cycle()`
  - Method `.test_am_signal_multiplies_carrier_and_modulator()`
- `class ShamControlTests`
  - Method `.test_static_sham_zeroes_frequency()`
  - Method `.test_detune_sham_shifts_frequency_deterministically()`
- `class ArgumentParsingTests`
  - Method `.test_defaults_match_documented_values()`

---
