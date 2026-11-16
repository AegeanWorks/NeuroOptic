"""
NeuroOptic - Generalized Visual Entrainment Engine (Gamma-Optimized)

A precision frequency-configurable visual oscillator designed for research
applications. Implements hardware-aware rendering, monotonic phase accumulation,
and strict safety limits based on monitor refresh rates.
"""

import sys
import time
import math
import platform as sys_platform
import random
import csv
import os
from datetime import datetime
import ctypes
import gc
import logging
import argparse
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Tuple
import json

from core.protocol import (
    EntrainmentProtocol,
    ShamType,
    StimulationMode,
    WaveformType,
)
from core.safety import calculate_photic_risk, validate_hardware_limits

import glfw
import numpy as np
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [NeuroOptic] - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FrequencyBand:
    name: str
    min_hz: float
    max_hz: float


class FrequencyManager:
    """
    Manages frequency bands and validates targets against hardware limits.
    """
    BANDS = [
        FrequencyBand("Delta", 1, 4),
        FrequencyBand("Theta", 4, 8),
        FrequencyBand("Alpha", 8, 12),
        FrequencyBand("Beta", 12, 30),
        FrequencyBand("Gamma", 30, 80),
        FrequencyBand("High Gamma", 80, 120),
    ]

    @staticmethod
    def get_band_name(frequency: float) -> str:
        for band in FrequencyManager.BANDS:
            if band.min_hz <= frequency <= band.max_hz:
                return band.name
        return "Custom"

    @staticmethod
    def validate_frequency(target_freq: float, refresh_rate: int, waveform: WaveformType,
                           allow_zero: bool = False) -> Tuple[float, WaveformType]:
        """
        Calculates safe frequency ceiling (Nyquist limit) and validates.
        Returns the (target_freq, waveform) tuple, degrading SQUARE to SINE when the
        display cannot render a 50% duty cycle. Delegates to
        core.safety.validate_hardware_limits, the single validation authority shared
        with SessionController, so assessment and execution can never diverge.
        """
        return validate_hardware_limits(target_freq, refresh_rate, waveform, allow_zero=allow_zero)


class PhaseOscillator:
    """
    True Frame-Locked Phase Accumulator.
    Derives phase from frame index steps rather than CPU time.
    
    Model: phase[n] = (phase[n-1] + 2π * f / R) % 2π
    """

    def __init__(self, frequency: float, waveform: WaveformType, phase_offset: float = 0.0, rng: random.Random = None):
        self.frequency = frequency
        self.waveform = waveform
        self.phase = phase_offset  # Current accumulated phase
        self.carrier_freq = 0.0  # Only for AM_CARRIER
        self.carrier_phase = 0.0
        self.phase_jitter = 0.0
        self.rng = rng if rng else random.Random()

    def set_phase_jitter(self, amount: float):
        self.phase_jitter = amount

    def set_carrier_frequency(self, freq: float):
        self.carrier_freq = freq

    def set_frequency(self, new_freq: float, current_t: float):
        """
        Updates frequency. Phase continuity is automatically preserved 
        because we accumulate onto the existing phase state.
        """
        self.frequency = new_freq
        # current_t is ignored in frame-locked model, kept for API compatibility

    def update_phase(self, delta_rad: float):
        """
        Injects a phase shift (e.g., for closed-loop error correction).
        """
        self.phase = (self.phase + delta_rad) % (2 * math.pi)

    def step(self, refresh_rate: float):
        """
        Advances the oscillator by one frame step.
        """
        # Deterministic phase step
        increment = (2 * math.pi * self.frequency) / refresh_rate
        self.phase = (self.phase + increment) % (2 * math.pi)

        if self.waveform == WaveformType.AM_CARRIER:
            c_inc = (2 * math.pi * self.carrier_freq) / refresh_rate
            self.carrier_phase = (self.carrier_phase + c_inc) % (2 * math.pi)

    def get_phase_state(self) -> Tuple[float, float]:
        """
        Returns (modulator_phase, carrier_phase) with jitter applied.
        """
        jitter = 0.0
        if self.phase_jitter > 0:
            jitter = self.rng.uniform(-self.phase_jitter, self.phase_jitter)
        
        return (self.phase + jitter) % (2 * math.pi), self.carrier_phase


class StimulusRenderer:
    """
    Modern OpenGL (GLSL) Renderer.
    Handles high-precision luminance calculation and photometric calibration on GPU.
    """
    
    VERTEX_SRC = """
    #version 330 core
    layout (location = 0) in vec2 aPos;
    layout (location = 1) in vec2 aTexCoord;
    out vec2 TexCoords;
    void main() {
        gl_Position = vec4(aPos, 0.0, 1.0);
        TexCoords = aTexCoord;
    }
    """

    FRAGMENT_SRC = """
    #version 330 core
    out vec4 FragColor;
    in vec2 TexCoords;

    uniform float u_phase_left;
    uniform float u_phase_right;
    uniform float u_c_phase_left; // Carrier
    uniform float u_c_phase_right;

    uniform int u_wf_left; // 1:SQUARE, 2:SINE, 3:AM, 4:TRIANGLE
    uniform int u_wf_right;

    uniform float u_amp_left;
    uniform float u_amp_right;
    uniform int u_mode; // 1:FULL, 2:RING, 3:LEFT, 4:RIGHT, 5:SPLIT, 6-9:QUADS

    uniform sampler1D u_lut;
    uniform int u_use_lut;
    uniform float u_gamma;

    const float PI = 3.14159265359;

    float get_signal(int wf, float ph, float c_ph) {
        if (wf == 1) return sin(ph) >= 0.0 ? 1.0 : 0.0; // SQUARE
        if (wf == 2) return 0.5 + 0.5 * sin(ph);        // SINE
        if (wf == 3) {                                  // AM
            float car = 0.5 + 0.5 * sin(c_ph);
            float mod = 0.5 + 0.5 * sin(ph);
            return car * mod;
        }
        if (wf == 4) {                                  // TRIANGLE
            float p = mod(ph, 2.0 * PI) / (2.0 * PI);
            return 1.0 - abs(2.0 * p - 1.0);
        }
        return 0.0;
    }

    void main() {
        vec2 uv = TexCoords;
        bool use_left = false;
        bool use_right = false;

        // Spatial Mode Logic
        if (u_mode == 1) { use_left = true; } // FULL
        else if (u_mode == 2) { // RING
            if (distance(uv, vec2(0.5)) > 0.15) use_left = true; // 0.3 NDC radius
        }
        else if (u_mode == 3) { if (uv.x < 0.5) use_left = true; } // LEFT
        else if (u_mode == 4) { if (uv.x >= 0.5) use_left = true; } // RIGHT (Uses Left Osc settings)
        else if (u_mode == 5) { // SPLIT
            if (uv.x < 0.5) use_left = true; else use_right = true;
        }
        else if (u_mode == 6) { if (uv.x < 0.5 && uv.y > 0.5) use_left = true; } // TL
        else if (u_mode == 7) { if (uv.x >= 0.5 && uv.y > 0.5) use_left = true; } // TR
        else if (u_mode == 8) { if (uv.x < 0.5 && uv.y <= 0.5) use_left = true; } // BL
        else if (u_mode == 9) { if (uv.x >= 0.5 && uv.y <= 0.5) use_left = true; } // BR

        float raw = 0.0;
        if (use_left) raw = get_signal(u_wf_left, u_phase_left, u_c_phase_left) * u_amp_left;
        else if (use_right) raw = get_signal(u_wf_right, u_phase_right, u_c_phase_right) * u_amp_right;

        // Photometric Calibration
        float final = raw;
        if (u_use_lut == 1) {
            final = texture(u_lut, raw).r;
        } else if (u_gamma != 1.0 && raw > 0.0) {
            final = pow(raw, 1.0 / u_gamma);
        }

        FragColor = vec4(final, final, final, 1.0);
    }
    """

    def __init__(self):
        self.shader = None
        self.vao = None
        self.lut_tex = None
        self.lut_active = False
        self.query = None
        self.gpu_timer_available = False

    def init_gl(self):
        # Compile Shader
        self.shader = compileProgram(
            compileShader(self.VERTEX_SRC, GL_VERTEX_SHADER),
            compileShader(self.FRAGMENT_SRC, GL_FRAGMENT_SHADER)
        )

        # Setup Fullscreen Quad
        vertices = np.array([
            # Pos        # Tex
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
            -1.0,  1.0,  0.0, 1.0,
             1.0,  1.0,  1.0, 1.0
        ], dtype=np.float32)

        self.vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)

        # Pos
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(0))
        # Tex
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * 4, ctypes.c_void_p(2 * 4))

        # Setup GPU Timer Queries
        try:
            # PyOpenGL returns a numpy array for queries; extract scalar ID
            queries = glGenQueries(1)
            self.query = int(queries[0]) if hasattr(queries, '__len__') else int(queries)
            self.gpu_timer_available = True
        except Exception as e:
            logger.warning(f"GPU Timer Queries not supported: {e}")

    def load_calibration(self, filepath: str):
        """Loads a CSV (Input, Output) and creates a 1D Texture LUT."""
        try:
            data = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                # First row is usually the header; only skip it silently when both
                # columns are non-numeric (e.g. Input,Output). A half-numeric
                # first row like 0.0,bad is malformed data and must warn.
                for line_number, row in enumerate(reader, 1):
                    try:
                        data.append(float(row[1]))  # Assuming Col 0=Input, Col 1=Output
                    except (ValueError, IndexError):
                        def _is_number(text):
                            try:
                                float(text)
                                return True
                            except (TypeError, ValueError):
                                return False
                        is_header = (
                            line_number == 1
                            and len(row) >= 2
                            and not _is_number(row[0])
                            and not _is_number(row[1])
                        )
                        if not is_header:
                            logger.warning(
                                f"Skipping malformed calibration row {line_number} in {filepath}: {row!r}")
            
            if not data:
                logger.warning(f"Calibration file has no usable rows: {filepath}")
                return
            
            # Create Texture
            lut_data = np.array(data, dtype=np.float32)
            self.lut_tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_1D, self.lut_tex)
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_1D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage1D(GL_TEXTURE_1D, 0, GL_R32F, len(lut_data), 0, GL_RED, GL_FLOAT, lut_data)
            self.lut_active = True
            logger.info(f"Photometric Calibration Loaded: {len(lut_data)} points.")
        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")

    def get_last_gpu_duration(self):
        """Returns the GPU execution time of the previous frame in nanoseconds."""
        if not self.gpu_timer_available:
            return 0
        
        # Check if result is available (non-blocking)
        # We typically call this at the start of the NEXT frame, so result should be ready.
        try:
            available = glGetQueryObjectiv(self.query, GL_QUERY_RESULT_AVAILABLE)
            if available:
                return glGetQueryObjectuiv(self.query, GL_QUERY_RESULT)
        except Exception as e:
            logger.debug(f"GPU timer query read failed: {e}")
        return 0

    def render(self, phase_l, c_phase_l, phase_r, c_phase_r, 
               wf_l, wf_r, amp_l, amp_r, mode, gamma):
        glUseProgram(self.shader)
        
        glUniform1f(glGetUniformLocation(self.shader, "u_phase_left"), phase_l)
        glUniform1f(glGetUniformLocation(self.shader, "u_phase_right"), phase_r)
        glUniform1f(glGetUniformLocation(self.shader, "u_c_phase_left"), c_phase_l)
        glUniform1f(glGetUniformLocation(self.shader, "u_c_phase_right"), c_phase_r)
        
        # Map Enums to Ints (1-based for shader)
        glUniform1i(glGetUniformLocation(self.shader, "u_wf_left"), wf_l.value)
        glUniform1i(glGetUniformLocation(self.shader, "u_wf_right"), wf_r.value)
        
        glUniform1f(glGetUniformLocation(self.shader, "u_amp_left"), amp_l)
        glUniform1f(glGetUniformLocation(self.shader, "u_amp_right"), amp_r)
        
        # Map Mode Enum to Int
        # FULL=1, RING=2, LEFT=3, RIGHT=4, SPLIT=5, Q_TL=6...
        mode_map = {
            StimulationMode.FULL_SCREEN: 1, StimulationMode.PERIPHERAL_RING: 2,
            StimulationMode.HEMIFIELD_LEFT: 3, StimulationMode.HEMIFIELD_RIGHT: 4,
            StimulationMode.SPLIT_HEMIFIELD: 5,
            StimulationMode.QUADRANT_TL: 6, StimulationMode.QUADRANT_TR: 7,
            StimulationMode.QUADRANT_BL: 8, StimulationMode.QUADRANT_BR: 9
        }
        glUniform1i(glGetUniformLocation(self.shader, "u_mode"), mode_map.get(mode, 1))
        
        glUniform1f(glGetUniformLocation(self.shader, "u_gamma"), gamma)
        glUniform1i(glGetUniformLocation(self.shader, "u_use_lut"), 1 if self.lut_active else 0)
        
        if self.lut_active:
            glActiveTexture(GL_TEXTURE0)
            glBindTexture(GL_TEXTURE_1D, self.lut_tex)
            glUniform1i(glGetUniformLocation(self.shader, "u_lut"), 0)

        glBindVertexArray(self.vao)
        
        if self.gpu_timer_available:
            glBeginQuery(GL_TIME_ELAPSED, self.query)
            
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        
        if self.gpu_timer_available:
            glEndQuery(GL_TIME_ELAPSED)


class EntrainmentEngine:
    def __init__(
            self,
            target_freq: float,
            waveform: WaveformType,
            mode: StimulationMode = StimulationMode.FULL_SCREEN,
            ramp_duration: float = 0.0,
            session_duration: float = 0.0,
            sham_type: ShamType = ShamType.NONE,
            sham_seed: Optional[int] = None,
            gamma: float = 1.0,
            brightness: float = 1.0,
            phase_offset: float = 0.0,
            right_freq: Optional[float] = None,
            right_phase_offset: float = 0.0,
            calibration_file: Optional[str] = None,
            compat_mode: str = 'standard'
    ):
        self.target_freq = target_freq
        self.waveform = waveform
        self.waveform_left = waveform
        self.waveform_right = waveform
        self.mode = mode
        self.ramp_duration = ramp_duration
        self.session_duration = session_duration
        self.gamma = gamma
        self.max_brightness = brightness
        self.phase_offset_rad = math.radians(phase_offset)
        self.calibration_file = calibration_file
        self.compat_mode = compat_mode
        
        # Dual Hemifield Logic
        self.right_freq = right_freq if right_freq is not None else target_freq
        self.right_phase_rad = math.radians(right_phase_offset)
        
        self.sham_type = sham_type

        # 11️⃣ Deterministic Randomness Scope
        if sham_seed is None:
            sham_seed = random.randint(0, 100000)
        self.sham_seed = sham_seed
        self.rng = random.Random(self.sham_seed)

        if self.sham_type != ShamType.NONE:
            logger.warning(f"⚠ SHAM MODE ACTIVE: {self.sham_type.name} | Seed: {self.sham_seed}")
            if self.sham_type == ShamType.DETUNE:
                # Detune by +/- 5-10%
                detune_factor = self.rng.choice([0.90, 0.95, 1.05, 1.10])
                self.target_freq *= detune_factor
                self.right_freq *= detune_factor # Detune both
                logger.info(f"Sham: Frequency detuned to {self.target_freq:.2f} Hz")

            elif self.sham_type == ShamType.STATIC:
                self.target_freq = 0.0
                self.right_freq = 0.0
                # STATIC must be truly non-flickering at mean luminance (0.5 x brightness).
                # SINE at phase 0 holds 0.5; SQUARE/TRIANGLE hold phase-dependent
                # extremes and AM still advances its carrier, so normalize.
                self.waveform = WaveformType.SINE
                self.waveform_left = WaveformType.SINE
                self.waveform_right = WaveformType.SINE
                self.phase_offset_rad = 0.0
                self.right_phase_rad = 0.0
                logger.info("Sham: Frequency set to 0 Hz (Static, SINE hold at 0.5)")

        self.window = None
        self.monitor_refresh_rate = 60  # Default fallback
        self.oscillator_left: Optional[PhaseOscillator] = None
        self.oscillator_right: Optional[PhaseOscillator] = None
        self.gpu_info = {}
        self.running = False
        self.renderer = StimulusRenderer()

        self.phase_jitter_amount = 0.0
        if self.sham_type == ShamType.PHASE_JITTER:
            self.phase_jitter_amount = 0.5  # Significant jitter

        self.frame_data = []  # Stores (timestamp, delta, luminance) for audit
        self.dropped_frame_log = []  # Defer logging to avoid I/O latency during render loop

    def initialize_hardware(self):
        """
        Initializes GLFW, detects monitor specs, and sets up the window.
        """
        if not glfw.init():
            logger.error("Failed to initialize GLFW")
            sys.exit(1)

        # Get Primary Monitor and Video Mode
        monitor = glfw.get_primary_monitor()
        mode = glfw.get_video_mode(monitor)
        self.monitor_refresh_rate = mode.refresh_rate

        logger.info(f"Hardware Detected: {mode.size.width}x{mode.size.height} @ {self.monitor_refresh_rate} Hz")

        # Validate Frequencies against Hardware
        try:
            # STATIC sham holds 0 Hz on both hemifields; every other path validates unchanged.
            allow_zero = (self.sham_type == ShamType.STATIC)
            # Validate Left (Main)
            self.target_freq, self.waveform_left = FrequencyManager.validate_frequency(self.target_freq,
                                                                                  self.monitor_refresh_rate,
                                                                                  self.waveform_left,
                                                                                  allow_zero=allow_zero)
            # Validate Right
            self.right_freq, self.waveform_right = FrequencyManager.validate_frequency(self.right_freq,
                                                                                  self.monitor_refresh_rate,
                                                                                  self.waveform_right,
                                                                                  allow_zero=allow_zero)
            if self.mode != StimulationMode.SPLIT_HEMIFIELD and self.right_freq != self.target_freq:
                logger.warning(
                    f"Right frequency ({self.right_freq} Hz) is ignored unless mode is SPLIT; "
                    f"using left ({self.target_freq} Hz) for the full display.")

            # Create Oscillator AFTER validation to ensure settings (like jitter) aren't overwritten
            self.oscillator_left = PhaseOscillator(self.target_freq, self.waveform_left, phase_offset=self.phase_offset_rad, rng=self.rng)
            self.oscillator_right = PhaseOscillator(self.right_freq, self.waveform_right, phase_offset=self.right_phase_rad, rng=self.rng)

            # Apply Sham / Advanced Settings
            if self.phase_jitter_amount > 0:
                self.oscillator_left.set_phase_jitter(self.phase_jitter_amount)
                self.oscillator_right.set_phase_jitter(self.phase_jitter_amount)

            band = "Static" if (allow_zero and self.target_freq == 0) else FrequencyManager.get_band_name(self.target_freq)
            logger.info(f"Target Frequency: {self.target_freq} Hz ({band}) - SAFE")
        except ValueError as e:
            logger.critical(str(e))
            glfw.terminate()
            sys.exit(1)

        # If AM Carrier, set carrier to max safe frequency (Nyquist)
        # STATIC is normalized to SINE above, so no carrier flicker in sham hold.
        if self.waveform_left == WaveformType.AM_CARRIER or self.waveform_right == WaveformType.AM_CARRIER:
            carrier = self.monitor_refresh_rate / 2.0
            self.oscillator_left.set_carrier_frequency(carrier)
            self.oscillator_right.set_carrier_frequency(carrier)
            logger.info(f"AM Carrier Frequency set to: {carrier} Hz")

        # Create Window (Fullscreen recommended for immersion, windowed for dev)
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        glfw.window_hint(glfw.RESIZABLE, glfw.FALSE)
        
        # Exclusive Mode Hints (Bypass Compositor/DWM where possible)
        glfw.window_hint(glfw.AUTO_ICONIFY, glfw.FALSE) # Keep app running if focus shifts
        glfw.window_hint(glfw.FLOATING, glfw.TRUE)      # Request "Always on Top" priority
        glfw.window_hint(glfw.CENTER_CURSOR, glfw.TRUE) # Capture mouse

        # Create a fullscreen window on the primary monitor
        self.window = glfw.create_window(mode.size.width, mode.size.height, "NeuroOptic Engine", monitor, None)

        if not self.window:
            logger.error("Failed to create GLFW window")
            glfw.terminate()
            sys.exit(1)

        glfw.make_context_current(self.window)

        # Enable VSync - Crucial for timing accuracy
        glfw.swap_interval(1)

        # Center and show (if windowed, but we are fullscreen)
        glfw.show_window(self.window)

        # OpenGL Setup
        glClearColor(0.0, 0.0, 0.0, 1.0)
        
        # Initialize Renderer & Calibration
        self.renderer.init_gl()
        if self.calibration_file:
            self.renderer.load_calibration(self.calibration_file)

        # 3️⃣ Hardware Abstraction Layer - Metadata Collection
        # We query OpenGL after context is current
        renderer = glGetString(GL_RENDERER).decode('utf-8')
        version = glGetString(GL_VERSION).decode('utf-8')
        
        self.gpu_info['renderer'] = renderer
        self.gpu_info['version'] = version

        # Color depth
        depth = mode.bits.red + mode.bits.green + mode.bits.blue

        logger.info("=== Hardware Abstraction Layer ===")
        logger.info(f"GPU: {renderer}")
        logger.info(f"Driver: {version}")
        logger.info(f"Display: {mode.size.width}x{mode.size.height} @ {self.monitor_refresh_rate} Hz")
        logger.info(f"Color Depth: {depth}-bit (R{mode.bits.red}G{mode.bits.green}B{mode.bits.blue})")
        logger.info(f"VSync: Enabled (Double Buffered)")
        logger.info("==================================")

    def set_frequency(self, freq: float):
        # Updates main (left) oscillator
        if self.oscillator_left:
            self.oscillator_left.set_frequency(freq, glfw.get_time())

    def update_phase(self, delta_deg: float):
        if self.oscillator_left:
            self.oscillator_left.update_phase(math.radians(delta_deg))

    def compute_cpu_signal(self, waveform: WaveformType, phase: float, carrier_phase: float) -> float:
        """
        Mirrors the GLSL shader logic to compute exact signal value on CPU for logging.
        """
        if waveform == WaveformType.SQUARE:
            return 1.0 if math.sin(phase) >= 0.0 else 0.0
        elif waveform == WaveformType.SINE:
            return 0.5 + 0.5 * math.sin(phase)
        elif waveform == WaveformType.AM_CARRIER:
            car = 0.5 + 0.5 * math.sin(carrier_phase)
            mod = 0.5 + 0.5 * math.sin(phase)
            return car * mod
        elif waveform == WaveformType.TRIANGLE:
            p = (phase % (2 * math.pi)) / (2 * math.pi)
            return 1.0 - abs(2.0 * p - 1.0)
        return 0.0

    def run(self):
        """
        Main Rendering Loop.
        """
        self.running = True

        # Timing variables for drift control and logging
        start_time = glfw.get_time()
        frame_count = 0
        last_log_time = start_time

        expected_frame_time = 1.0 / self.monitor_refresh_rate
        last_frame_time = start_time
        last_gpu_time_ns = 0

        logger.info("Engine Started. Press ESC to exit.")
        logger.info(f"Recording session data... (Expected IFI: {expected_frame_time * 1000:.2f} ms)")

        # OPTIMIZATION: Disable GC during render loop to prevent micro-stutters
        gc.disable()

        while not glfw.window_should_close(self.window) and self.running:
            # 1. Monotonic Clock Sampling
            current_time = glfw.get_time()
            delta_time = current_time - last_frame_time
            elapsed_time = current_time - start_time

            # Retrieve GPU timing from the PREVIOUS frame (to avoid stalling pipeline)
            last_gpu_time_ns = self.renderer.get_last_gpu_duration()

            # Session Duration Check
            if self.session_duration > 0 and elapsed_time > self.session_duration:
                logger.info("Session duration reached. Stopping.")
                self.running = False

            # 2. Frame Drop Detection
            # If delta is significantly larger than expected (allowing 10% jitter), log it.
            if delta_time > (expected_frame_time * 1.1):
                # OPTIMIZATION: Store drop data now, log later. Printing here causes more drops.
                self.dropped_frame_log.append((len(self.frame_data), delta_time))

            last_frame_time = current_time

            # 3. Ramp-Up & Amplitude Calculation
            amplitude_scalar = 1.0
            if self.ramp_duration > 0 and elapsed_time < self.ramp_duration:
                amplitude_scalar = elapsed_time / self.ramp_duration

            # Sham: Low Amplitude
            if self.sham_type == ShamType.LOW_AMP:
                amplitude_scalar *= 0.15  # Cap at 15% brightness

            # 4. Frame-Locked Phase Update
            self.oscillator_left.step(self.monitor_refresh_rate)
            self.oscillator_right.step(self.monitor_refresh_rate)
            
            # Get current phase states (with jitter)
            ph_l, c_ph_l = self.oscillator_left.get_phase_state()
            ph_r, c_ph_r = self.oscillator_right.get_phase_state()
            
            # Calculate Amplitudes (Ramp * Global Cap)
            amp_l = amplitude_scalar * self.max_brightness
            amp_r = amplitude_scalar * self.max_brightness

            # Compute CPU-side signal value for accurate logging/analysis
            # Mirroring shader logic to capture actual waveform dynamics
            raw_signal = self.compute_cpu_signal(self.waveform_left, ph_l, c_ph_l)
            logged_luminance = raw_signal * amp_l

            # Record Metric (Skip first frame initialization delta)
            if self.frame_data or frame_count > 0:
                self.frame_data.append((current_time, delta_time, logged_luminance, last_gpu_time_ns))

            # 4. Render
            glClearColor(0.0, 0.0, 0.0, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)
            
            self.renderer.render(
                ph_l, c_ph_l, ph_r, c_ph_r,
                self.waveform_left, self.waveform_right,
                amp_l, amp_r, self.mode, self.gamma
            )

            # 5. VSync Swap
            glfw.swap_buffers(self.window)
            glfw.poll_events()

            # Input handling
            if glfw.get_key(self.window, glfw.KEY_ESCAPE) == glfw.PRESS:
                self.running = False

            # Logging stats every second
            frame_count += 1
            if current_time - last_log_time >= 1.0:
                fps = frame_count / (current_time - last_log_time)
                # logger.debug(f"FPS: {fps:.2f} | Luminance: {luminance:.2f}")
                frame_count = 0
                last_log_time = current_time

        gc.enable()  # Re-enable GC for analysis
        self.analyze_session()
        self.cleanup()

    def analyze_session(self):
        """
        Computes session metrics and saves a publishable CSV report.
        """
        if not self.frame_data:
            logger.warning("No frame data recorded.")
            return

        # Convert to numpy for stats
        timestamps = np.array([x[0] for x in self.frame_data])
        deltas = np.array([x[1] for x in self.frame_data])
        luminances = np.array([x[2] for x in self.frame_data])
        gpu_times = np.array([x[3] for x in self.frame_data])

        # 1. Compute Metrics
        mean_ifi = np.mean(deltas) * 1000.0  # ms
        std_ifi = np.std(deltas) * 1000.0  # ms
        min_ifi = np.min(deltas) * 1000.0  # ms
        max_ifi = np.max(deltas) * 1000.0  # ms
        p99_ifi = np.percentile(deltas, 99) * 1000.0  # ms
        mean_gpu = np.mean(gpu_times) / 1_000_000.0 # ns to ms

        expected_ifi = (1.0 / self.monitor_refresh_rate)
        # Frame drop defined as deviation > 10% of expected interval
        drop_threshold = expected_ifi * 1.1
        dropped_frames = np.sum(deltas > drop_threshold)
        drop_pct = (dropped_frames / len(deltas)) * 100.0

        effective_fps = 1.0 / np.mean(deltas)
        
        # Statistical Delivered Frequency
        effective_delivered_freq = 0.0
        drift = 0.0
        if self.target_freq > 0:
            frames_per_cycle = self.monitor_refresh_rate / self.target_freq
            effective_delivered_freq = effective_fps / frames_per_cycle
            drift = abs(self.target_freq - effective_delivered_freq)
            # Note: This drift is purely statistical (jitter-induced). 
            # The deterministic phase accumulator has 0.00 Hz drift.

        # 2. Compute Actual Delivered Frequency (Zero-Crossing Analysis)
        # Remove DC offset to center signal around 0
        dc_offset = np.mean(luminances)
        ac_signal = luminances - dc_offset

        # Find zero crossings (where sign changes)
        crossings = np.diff(np.signbit(ac_signal))
        crossing_indices = np.where(crossings)[0]

        measured_freq = 0.0

        if len(crossing_indices) > 1:
            t_start = timestamps[crossing_indices[0]]
            t_end = timestamps[crossing_indices[-1]]
            duration = t_end - t_start

            # Cycles = (Number of crossings) / 2
            if duration > 0:
                # Correction: N crossings define N-1 intervals
                measured_freq = ((len(crossing_indices) - 1) / 2.0) / duration

        logger.info("=== Session Integrity Report ===")
        logger.info(f"Total Frames: {len(deltas)}")
        logger.info(f"Frame Interval Metrics:")
        logger.info(f"  - Mean: {mean_ifi:.3f} ms (σ = {std_ifi:.3f} ms)")
        logger.info(f"  - Min / Max: {min_ifi:.3f} ms / {max_ifi:.3f} ms")
        logger.info(f"  - 99th Percentile: {p99_ifi:.3f} ms")
        logger.info(f"Effective Refresh Rate: {effective_fps:.2f} Hz")
        logger.info(f"GPU Render Time (Mean): {mean_gpu:.3f} ms")
        logger.info(f"Frame Drops: {dropped_frames} ({drop_pct:.2f}%)")
        logger.info(f"Frequency Analysis:")
        logger.info(f"  - Target: {self.target_freq:.4f} Hz")
        logger.info(f"  - Delivered (Statistical): {effective_delivered_freq:.4f} Hz")
        if drift < 0.01:
            drift_grade = "EXCELLENT"
        elif drift < 0.10:
            drift_grade = "GOOD"
        elif drift < 0.50:
            drift_grade = "ACCEPTABLE"
        else:
            drift_grade = "POOR - check frame drops/refresh rate"
        logger.info(f"  - Drift: {drift:.4f} Hz ({drift_grade})")
        logger.info(f"  - Measured (Signal Zero-Crossing): {measured_freq:.3f} Hz")
        logger.info(f"Phase Consistency: Frame-Locked (No cumulative phase error from OS jitter)")

        if self.compat_mode == 'ptb':
            logger.info("=== PTB Compatibility Summary ===")
            logger.info(f"  Missed Deadlines: {dropped_frames}")
            logger.info(f"  Std Dev (Jitter): {std_ifi:.3f} ms")
            logger.info("=================================")

        if self.dropped_frame_log:
            logger.warning(f"Performance Alert: {len(self.dropped_frame_log)} frames dropped during session.")
            # Log first 5 drops details to avoid spamming console
            for i, (idx, dt) in enumerate(self.dropped_frame_log[:5]):
                logger.warning(f"  - Drop at frame {idx}: {dt * 1000:.2f}ms")
            if len(self.dropped_frame_log) > 5:
                logger.warning(f"  - ... and {len(self.dropped_frame_log) - 5} more.")
        logger.info("================================")

        # 2. Save CSV
        os.makedirs("session_data", exist_ok=True)
        filename = f"session_data/neurooptic_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # 12️⃣ Log More Metadata (Header Block)
                writer.writerow(["# === Session Metadata ==="])
                writer.writerow(["# OS", f"{sys_platform.system()} {sys_platform.release()}"])
                writer.writerow(["# Python", sys.version.split()[0]])
                writer.writerow(["# GPU", self.gpu_info.get('renderer', 'Unknown')])
                writer.writerow(["# Driver", self.gpu_info.get('version', 'Unknown')])
                writer.writerow(["# Refresh Rate", f"{self.monitor_refresh_rate} Hz"])
                writer.writerow(["# VSync", "Enabled"])
                writer.writerow(["# Mode", self.mode.name])
                writer.writerow(["# Waveform (Left)", self.waveform_left.name])
                writer.writerow(["# Frequency (Left)", f"{self.target_freq} Hz"])
                writer.writerow(["# Phase (Left)", f"{math.degrees(self.phase_offset_rad):.1f} deg"])
                if self.mode == StimulationMode.SPLIT_HEMIFIELD:
                    writer.writerow(["# Waveform (Right)", self.waveform_right.name])
                    writer.writerow(["# Frequency (Right)", f"{self.right_freq} Hz"])
                    writer.writerow(["# Phase (Right)", f"{math.degrees(self.right_phase_rad):.1f} deg"])
                writer.writerow(["# Ramp Duration", f"{self.ramp_duration} s"])
                writer.writerow(["# Session Duration", f"{self.session_duration} s"])
                writer.writerow(["# Gamma", self.gamma])
                writer.writerow(["# Brightness Cap", self.max_brightness])
                writer.writerow(["# Sham Type", self.sham_type.name])
                writer.writerow(["# Mean IFI", f"{mean_ifi:.3f} ms"])
                writer.writerow(["# Std IFI", f"{std_ifi:.3f} ms"])
                writer.writerow(["# 99th % IFI", f"{p99_ifi:.3f} ms"])
                writer.writerow(["# Mean GPU Time", f"{mean_gpu:.3f} ms"])
                writer.writerow(["# Delivered Freq", f"{effective_delivered_freq:.4f} Hz"])
                writer.writerow(["# Freq Drift", f"{drift:.4f} Hz"])
                writer.writerow(["# Calibration File", self.calibration_file if self.calibration_file else "None"])
                writer.writerow(["# Sham Seed", self.sham_seed])
                writer.writerow(["# ========================"])
                
                # Header
                if self.compat_mode == 'ptb':
                    writer.writerow(["frame_idx", "vbl_timestamp", "ifi", "stimulus_val", "target_freq", "sham_mode", "gpu_ns"])
                else:
                    writer.writerow(["Frame_ID", "Timestamp_Monotonic", "Delta_Time_Sec", "Luminance_NDC", "Target_Freq_Hz",
                                     "Sham_Mode", "GPU_Render_Time_ns"])
                # Data
                for i, (ts, dt, lum, gpu) in enumerate(self.frame_data):
                    writer.writerow([i, f"{ts:.6f}", f"{dt:.6f}", f"{lum:.4f}", self.target_freq, self.sham_type.name, gpu])

            logger.info(f"Session data saved to: {os.path.abspath(filename)}")
            
            if self.compat_mode == 'ptb':
                self.generate_matlab_loader(filename)

        except IOError as e:
            logger.error(f"Failed to save session data: {e}")

    def generate_matlab_loader(self, csv_path):
        m_path = csv_path.replace('.csv', '.m')
        try:
            with open(m_path, 'w', encoding='utf-8') as f:
                f.write(f"% NeuroOptic Session Loader (PTB Compatibility Mode)\n")
                f.write(f"% Generated: {datetime.now()}\n\n")
                f.write(f"fname = '{os.path.basename(csv_path)}';\n")
                f.write("opts = detectImportOptions(fname);\n")
                f.write("opts.CommentStyle = '#';\n")
                f.write("opts.VariableNamingRule = 'preserve';\n")
                f.write("data = readtable(fname, opts);\n\n")
                f.write("% PTB-style Validation Plot\n")
                f.write("figure; subplot(2,1,1);\n")
                f.write("plot(data.vbl_timestamp(2:end), diff(data.vbl_timestamp)*1000);\n")
                f.write("title('Frame Intervals (IFI)'); ylabel('ms'); xlabel('Frame');\n")
                f.write("subplot(2,1,2);\n")
                f.write("plot(data.vbl_timestamp, data.stimulus_val);\n")
                f.write("title('Stimulus Trace'); ylabel('Luminance'); xlabel('Time (s)');\n")
            logger.info(f"MATLAB pipeline script generated: {m_path}")
        except Exception as e:
            logger.error(f"Could not generate MATLAB script: {e}")

    def cleanup(self):
        logger.info("Shutting down engine...")
        if self.window:
            # Restore cursor or gamma if needed (not implemented here)
            glfw.destroy_window(self.window)
        glfw.terminate()


def parse_arguments():
    parser = argparse.ArgumentParser(description="NeuroOptic Visual Entrainment Engine")

    parser.add_argument(
        '--freq',
        type=float,
        default=40.0,
        help='Target frequency in Hz (Default: 40.0)'
    )

    parser.add_argument(
        '--waveform',
        type=str,
        choices=['sine', 'square', 'am', 'triangle'],
        default='sine',
        help='Waveform type: sine (default), square, am, or triangle'
    )

    parser.add_argument(
        '--mode',
        type=str,
        choices=['full', 'ring', 'left', 'right', 'split', 'quad_tl', 'quad_tr', 'quad_bl', 'quad_br'],
        default='full',
        help='Stimulation mode: full (default), ring (peripheral), left (hemifield), right (hemifield)'
    )

    parser.add_argument(
        '--preset',
        type=str,
        choices=['delta', 'theta', 'alpha', 'beta', 'gamma', 'high_gamma'],
        help='Use a predefined frequency band preset (Overrides --freq)'
    )

    parser.add_argument(
        '--protocol',
        type=str,
        help='Path to a declarative JSON protocol file (overrides individual arguments)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate parameters and log configuration plan without initializing display window'
    )

    parser.add_argument(
        '--ramp',
        type=float,
        default=0.0,
        help='Ramp-up duration in seconds (Default: 0.0)'
    )

    parser.add_argument(
        '--duration',
        type=float,
        default=0.0,
        help='Session duration in seconds (0.0 = Infinite)'
    )

    parser.add_argument(
        '--sham',
        type=str,
        choices=['none', 'detune', 'low_amp', 'jitter', 'static'],
        default='none',
        help='Activate sham mode for research control conditions'
    )

    parser.add_argument(
        '--sham-seed',
        type=int,
        default=None,
        help='Deterministic seed for sham modes (replayable research conditions). Defaults to a random seed.'
    )

    parser.add_argument(
        '--gamma',
        type=float,
        default=1.0,
        help='Display gamma correction value (e.g., 2.2). Default 1.0 (Linear/None).'
    )

    parser.add_argument(
        '--brightness',
        type=float,
        default=1.0,
        help='Global brightness cap (0.0 - 1.0). Scales output.'
    )

    parser.add_argument(
        '--phase',
        type=float,
        default=0.0,
        help='Initial phase offset in degrees (0-360).'
    )

    parser.add_argument(
        '--freq-right',
        type=float,
        help='Target frequency for Right Hemifield (Split mode only). Defaults to --freq if unset.'
    )

    parser.add_argument(
        '--phase-right',
        type=float,
        default=0.0,
        help='Phase offset for Right Hemifield in degrees (0-360).'
    )

    parser.add_argument(
        '--calib-file',
        type=str,
        help='Path to photometric calibration CSV (Input, Output).'
    )

    parser.add_argument(
        '--compat',
        type=str,
        choices=['standard', 'ptb'],
        default='standard',
        help='Output compatibility mode: standard (default) or ptb (Psychtoolbox/MATLAB friendly)'
    )

    return parser.parse_args()


def build_engine_from_args(args) -> Tuple[EntrainmentEngine, bool]:
    """Constructs an EntrainmentEngine from parsed CLI arguments or a declarative JSON protocol."""
    wf_map = {
        'sine': WaveformType.SINE,
        'square': WaveformType.SQUARE,
        'am': WaveformType.AM_CARRIER,
        'triangle': WaveformType.TRIANGLE
    }

    mode_map = {
        'full': StimulationMode.FULL_SCREEN,
        'ring': StimulationMode.PERIPHERAL_RING,
        'left': StimulationMode.HEMIFIELD_LEFT,
        'right': StimulationMode.HEMIFIELD_RIGHT,
        'split': StimulationMode.SPLIT_HEMIFIELD,
        'quad_tl': StimulationMode.QUADRANT_TL,
        'quad_tr': StimulationMode.QUADRANT_TR,
        'quad_bl': StimulationMode.QUADRANT_BL,
        'quad_br': StimulationMode.QUADRANT_BR
    }

    sham_map = {
        'none': ShamType.NONE,
        'detune': ShamType.DETUNE,
        'low_amp': ShamType.LOW_AMP,
        'jitter': ShamType.PHASE_JITTER,
        'static': ShamType.STATIC
    }

    if getattr(args, 'protocol', None):
        with open(args.protocol, 'r', encoding='utf-8') as f:
            data = json.load(f)
        proto = EntrainmentProtocol.from_dict(data)
        target_freq = proto.target_freq
        waveform = proto.waveform
        mode = proto.mode
        ramp = proto.ramp
        duration = proto.duration
        sham = proto.sham
        sham_seed = proto.sham_seed
        gamma = proto.gamma
        brightness = proto.brightness
        phase = proto.phase
        freq_right = proto.right_freq
        phase_right = proto.right_phase
        calib_file = proto.calibration_file
        compat = proto.compat_mode
    else:
        target_freq = args.freq
        if getattr(args, 'preset', None):
            presets = {
                'delta': 2.0,
                'theta': 6.0,
                'alpha': 10.0,
                'beta': 20.0,
                'gamma': 40.0,
                'high_gamma': 80.0
            }
            target_freq = presets[args.preset]
            logger.info(f"Loaded Preset: {args.preset.upper()} ({target_freq} Hz)")

        waveform = wf_map[args.waveform]
        mode = mode_map.get(args.mode, StimulationMode.FULL_SCREEN)
        ramp = args.ramp
        duration = args.duration
        sham = sham_map[args.sham]
        sham_seed = args.sham_seed
        gamma = args.gamma
        brightness = args.brightness
        phase = args.phase
        freq_right = args.freq_right
        phase_right = args.phase_right
        calib_file = args.calib_file
        compat = args.compat

    engine = EntrainmentEngine(
        target_freq=target_freq,
        waveform=waveform,
        mode=mode,
        ramp_duration=ramp,
        session_duration=duration,
        sham_type=sham,
        sham_seed=sham_seed,
        gamma=gamma,
        brightness=brightness,
        phase_offset=phase,
        right_freq=freq_right,
        right_phase_offset=phase_right,
        calibration_file=calib_file,
        compat_mode=compat
    )
    return engine, bool(getattr(args, 'dry_run', False))


def detect_monitor_refresh_rate(default: int = 60) -> int:
    """
    Queries the primary monitor refresh rate via GLFW without creating a window.
    Falls back to `default` (with a warning) when GLFW cannot answer, e.g. headless runs.
    """
    try:
        if not glfw.init():
            logger.warning(f"GLFW init failed; assuming {default} Hz refresh rate.")
            return default
        try:
            monitor = glfw.get_primary_monitor()
            mode = glfw.get_video_mode(monitor) if monitor else None
        finally:
            glfw.terminate()
        if mode and mode.refresh_rate > 1:
            return int(mode.refresh_rate)
    except Exception as exc:
        logger.warning(f"Could not detect monitor refresh rate ({exc}); assuming {default} Hz.")
        return default
    logger.warning(f"Could not detect monitor refresh rate; assuming {default} Hz.")
    return default


if __name__ == "__main__":
    args = parse_arguments()
    engine, is_dry_run = build_engine_from_args(args)
    if is_dry_run:
        # Dry-run is a safety probe: it applies the same frequency validation the live
        # path enforces at window creation (Nyquist ceiling, duty-cycle symmetry),
        # against the detected monitor refresh rate, and reports the photic risk tier.
        dry_run_refresh_hz = detect_monitor_refresh_rate()
        allow_zero = (engine.sham_type == ShamType.STATIC)
        try:
            engine.target_freq, engine.waveform = FrequencyManager.validate_frequency(
                engine.target_freq, dry_run_refresh_hz, engine.waveform, allow_zero=allow_zero)
            if engine.mode == StimulationMode.SPLIT_HEMIFIELD and engine.right_freq > 0:
                engine.right_freq, engine.waveform_right = FrequencyManager.validate_frequency(
                    engine.right_freq, dry_run_refresh_hz, engine.waveform_right, allow_zero=allow_zero)
        except ValueError as exc:
            logger.error(
                f"DRY RUN failed validation.\nWhy: {exc}\n"
                f"Fix: lower the target frequency or run on a display with a higher refresh rate.")
            sys.exit(1)
        risk = calculate_photic_risk(engine.target_freq, engine.waveform)
        logger.info(f"DRY RUN: Validated {engine.target_freq} Hz, waveform={engine.waveform.name}, "
                    f"mode={engine.mode.name}, photic risk={risk.tier.name} ({risk.score:.2f})")
        sys.exit(0)

    engine.initialize_hardware()
    engine.run()