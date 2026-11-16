# Codebase Map & Symbol Catalog 🗺️

> **AUTO-GENERATED & VERIFIED BY `scripts/update_knowledge_base.py`**
> This document catalogues Python modules, classes, and exported functions. See Map Coverage for any stack it does not index.

---

## 📊 Codebase Metrics
- **Total Python Modules**: `11`
- **Total Classes**: `26`
- **Total Top-Level Functions**: `8`
- **Total Class Methods**: `112`
- **Total Source Lines**: `2700`

## 🧭 Map Coverage
- **Indexed**: python (`11` module(s))
- **Not indexed by this map**: none (no non-Python source files were found)

---

## 📦 Modules & Exported Symbols

### [`core/__init__.py`](core/__init__.py)
> *NeuroOptic Core: Headless mechanics, protocol schemas, and safety validation.*

**Size**: `35` lines (`718` bytes)

---

### [`core/protocol.py`](core/protocol.py)
> *Declarative protocol specification and parameter models for NeuroOptic entrainment.*

**Size**: `157` lines (`5367` bytes)

**Classes:**
- `class WaveformType`
- `class ShamType`
- `class StimulationMode`
- `class FrequencyBand`
- `class EntrainmentProtocol` - *Immutable, validated protocol definition for visual entrainment sessions.*
  - Method `.to_dict()` - *Serialize protocol parameters to a JSON-compatible dictionary.*
  - Method `.from_dict(data)` - *Reconstruct an EntrainmentProtocol from a dictionary with case-insensitive enums.*
  - Method `.to_cli_args()` - *Convert protocol parameters into CLI argument tokens for entrainment_engine.py.*

---

### [`core/safety.py`](core/safety.py)
> *Bio-safety calculations, photic risk scoring, and hardware Nyquist validation.*

**Size**: `115` lines (`4085` bytes)

**Classes:**
- `class RiskTier`
- `class PhoticRiskAssessment` - *Evaluation result of photic driving and seizure risk.*

**Functions:**
- `def calculate_photic_risk(freq, waveform, mode)` - *Evaluates photosensitive epilepsy (PSE) risk for given stimulation parameters.*
- `def validate_hardware_limits(target_freq, refresh_rate, waveform, allow_zero)` - *Validates stimulation frequency against display Nyquist limit and duty-cycle symmetry.*

---

### [`core/session_controller.py`](core/session_controller.py)
> *Headless session controller managing entrainment execution lifecycle and process supervision.*

**Size**: `88` lines (`3397` bytes)

**Classes:**
- `class SessionState`
- `class SessionController` - *Manages protocol validation, subprocess execution, and session lifecycle.*
  - Method `.__init__(protocol, engine_path)`
  - Method `.validate(refresh_rate)` - *Validates protocol against display refresh limits and calculates bio-safety risk.*
  - Method `.build_command(python_exe)` - *Constructs subprocess command line tokens for the entrainment engine.*
  - Method `.start_session(popen_fn)` - *Launches the entrainment engine subprocess under process tracking.*
  - Method `.stop_session()` - *Terminates the running engine subprocess safely.*

---

### [`entrainment_engine.py`](entrainment_engine.py)
> *NeuroOptic - Generalized Visual Entrainment Engine (Gamma-Optimized)*

**Size**: `1150` lines (`46804` bytes)

**Classes:**
- `class FrequencyBand`
- `class FrequencyManager` - *Manages frequency bands and validates targets against hardware limits.*
  - Method `.get_band_name(frequency)`
  - Method `.validate_frequency(target_freq, refresh_rate, waveform, allow_zero)` - *Calculates safe frequency ceiling (Nyquist limit) and validates.*
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
- `def build_engine_from_args(args)` - *Constructs an EntrainmentEngine from parsed CLI arguments or a declarative JSON protocol.*

---

### [`launcher.py`](launcher.py)
**Size**: `320` lines (`17692` bytes)

**Classes:**
- `class NeuroOpticLauncher`
  - Method `.__init__(root, headless)`
  - Method `._on_slider_change(val)`
  - Method `.create_group_frame(parent, title)`
  - Method `.create_help_btn(parent, message)`
  - Method `.report_error(title, message)`
  - Method `.report_warning(title, message)`
  - Method `.quick_start(preset)` - *One-click start with verified bio-safe parameters (PRINCIPLE-011).*
  - Method `.on_preset_change(choice)`
  - Method `.update_safety_evaluation(*args)`
  - Method `._parse_float(raw, label, min_val, max_val)`
  - Method `.launch_engine()`
  - Method `.stop_engine()`

---

### [`start.py`](start.py)
> *NeuroOptic One-Click Starter (PRINCIPLE-011).*

**Size**: `161` lines (`5643` bytes)

**Functions:**
- `def check_dependencies()` - *Check if all runtime dependencies are importable.*
- `def print_remediation_error(what, why, fix)` - *Print actionable remediation triad adhering to PRINCIPLE-011 R6.*
- `def build_quick_command(preset, dry_run)` - *Construct safe entrainment command for one-click start.*
- `def main()`

---

### [`test_entrainment_engine.py`](test_entrainment_engine.py)
> *Regression shield for NeuroOptic's pure engine logic; no window or GL context is needed.*

**Size**: `266` lines (`12073` bytes)

**Classes:**
- `class FrequencyManagerTests`
  - Method `.test_band_names_cover_preset_ranges()`
  - Method `.test_band_name_covers_alpha_beta_boundary()`
  - Method `.test_frequency_above_nyquist_limit_is_rejected()`
  - Method `.test_non_positive_frequency_is_rejected()`
  - Method `.test_square_with_non_integer_frames_switches_to_sine()`
  - Method `.test_square_with_integer_frames_is_kept()`
  - Method `.test_zero_allowed_only_with_explicit_static_opt_in()`
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
  - Method `.test_static_sham_zeroes_both_hemifields()`
  - Method `.test_detune_sham_shifts_frequency_deterministically()`
  - Method `.test_static_sham_normalizes_to_sine_hold()`
  - Method `.test_allow_zero_normalizes_negative_zero()`
- `class CalibrationLoaderTests`
  - Method `._renderer_without_gl()`
  - Method `._write(text)`
  - Method `.test_malformed_row_is_warned_and_skipped()`
  - Method `.test_file_without_usable_rows_is_reported()`
  - Method `.test_malformed_first_data_row_without_header_warns()`
- `class ArgumentParsingTests`
  - Method `.test_defaults_match_documented_values()`
  - Method `.test_preset_theta_sets_frequency()`
  - Method `.test_dry_run_flag_enabled()`
  - Method `.test_build_engine_from_declarative_protocol()`

---

### [`test_launcher.py`](test_launcher.py)
> *Automated headless unit test suite for NeuroOpticLauncher GUI controller.*

**Size**: `173` lines (`6826` bytes)

**Classes:**
- `class HeadlessLauncherTests`
  - Method `.setUpClass()`
  - Method `.tearDownClass()`
  - Method `.setUp()`
  - Method `.test_default_state_and_safe_badge()`
  - Method `.test_tabview_and_slider_synchronization()`
  - Method `.test_quick_start_gamma()`
  - Method `.test_quick_start_alpha()`
  - Method `.test_preset_change_theta_and_bands()`
  - Method `.test_high_risk_pse_disables_start_button()`
  - Method `.test_high_risk_authorization_enables_start_button()`
  - Method `.test_caution_tier_for_smooth_waveform_in_driving_band()`
  - Method `.test_invalid_frequency_records_error_without_popup()`
  - Method `.test_negative_frequency_rejected()`
  - Method `.test_right_frequency_warning_outside_split_mode()`
  - Method `.test_mocked_launch_and_stop_lifecycle()`

---

### [`test_mechanics.py`](test_mechanics.py)
> *Unit test suite for NeuroOptic headless mechanics, protocol schemas, and safety validation.*

**Size**: `152` lines (`5697` bytes)

**Classes:**
- `class ProtocolModelTests`
  - Method `.test_presets_include_canonical_bands()`
  - Method `.test_protocol_default_construction()`
  - Method `.test_protocol_dict_roundtrip()`
  - Method `.test_protocol_cli_args_generation()`
- `class SafetyValidationTests`
  - Method `.test_square_wave_in_photic_window_is_high_risk()`
  - Method `.test_sine_wave_in_photic_window_is_caution()`
  - Method `.test_gamma_frequency_is_safe()`
  - Method `.test_static_hold_is_safe()`
  - Method `.test_nyquist_exceeded_raises_error()`
  - Method `.test_non_integer_square_degrades_to_sine()`
  - Method `.test_allow_zero_static_pass()`
- `class SessionControllerTests`
  - Method `.test_controller_initial_state_idle()`
  - Method `.test_controller_validation_updates_state()`
  - Method `.test_controller_build_command()`
  - Method `.test_controller_start_and_stop_mocked()`

---

### [`test_start.py`](test_start.py)
> *Unit tests for NeuroOptic One-Click Starter (start.py).*

**Size**: `83` lines (`3042` bytes)

**Classes:**
- `class StartScriptTests`
  - Method `.test_check_dependencies_returns_true_in_configured_environment()`
  - Method `.test_check_dependencies_detects_missing_module()`
  - Method `.test_build_quick_command_gamma()`
  - Method `.test_build_quick_command_alpha_dry_run()`
  - Method `.test_print_remediation_error_format()`
  - Method `.test_main_check_flag()`
  - Method `.test_main_dry_run_gamma()`
  - Method `.test_main_missing_dependencies_exits_one()`
  - Method `.test_main_quick_popen_invoked()`

---
