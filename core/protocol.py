"""Declarative protocol specification and parameter models for NeuroOptic entrainment."""

from dataclasses import asdict, dataclass
from enum import Enum, auto
import json
from typing import Any, Dict, List, Optional


class WaveformType(Enum):
    SQUARE = auto()
    SINE = auto()
    AM_CARRIER = auto()
    TRIANGLE = auto()


class ShamType(Enum):
    NONE = auto()
    DETUNE = auto()
    LOW_AMP = auto()
    PHASE_JITTER = auto()
    STATIC = auto()


class StimulationMode(Enum):
    FULL_SCREEN = auto()
    PERIPHERAL_RING = auto()
    HEMIFIELD_LEFT = auto()
    HEMIFIELD_RIGHT = auto()
    SPLIT_HEMIFIELD = auto()
    QUADRANT_TL = auto()
    QUADRANT_TR = auto()
    QUADRANT_BL = auto()
    QUADRANT_BR = auto()


@dataclass(frozen=True)
class FrequencyBand:
    name: str
    min_hz: float
    max_hz: float


# Canonical brainwave band presets (Hz), including previously missing Theta
PRESETS: Dict[str, float] = {
    "Delta": 2.0,
    "Theta": 6.0,
    "Alpha": 10.0,
    "Beta": 20.0,
    "Gamma": 40.0,
    "High Gamma": 80.0,
}


@dataclass(frozen=True)
class EntrainmentProtocol:
    """Immutable, validated protocol definition for visual entrainment sessions."""

    target_freq: float = 40.0
    waveform: WaveformType = WaveformType.SINE
    mode: StimulationMode = StimulationMode.FULL_SCREEN
    duration: float = 0.0
    ramp: float = 0.0
    sham: ShamType = ShamType.NONE
    sham_seed: Optional[int] = None
    gamma: float = 1.0
    brightness: float = 1.0
    phase: float = 0.0
    right_freq: Optional[float] = None
    right_phase: float = 0.0
    calibration_file: Optional[str] = None
    compat_mode: str = "standard"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize protocol parameters to a JSON-compatible dictionary."""
        return {
            "target_freq": self.target_freq,
            "waveform": self.waveform.name.lower(),
            "mode": self.mode.name.lower(),
            "duration": self.duration,
            "ramp": self.ramp,
            "sham": self.sham.name.lower(),
            "sham_seed": self.sham_seed,
            "gamma": self.gamma,
            "brightness": self.brightness,
            "phase": self.phase,
            "right_freq": self.right_freq,
            "right_phase": self.right_phase,
            "calibration_file": self.calibration_file,
            "compat_mode": self.compat_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntrainmentProtocol":
        """Reconstruct an EntrainmentProtocol from a dictionary with case-insensitive enums."""
        wf_name = str(data.get("waveform", "sine")).upper()
        if wf_name == "AM":
            wf_name = "AM_CARRIER"
        mode_name = str(data.get("mode", "full_screen")).upper()
        if mode_name == "FULL":
            mode_name = "FULL_SCREEN"
        elif mode_name == "RING":
            mode_name = "PERIPHERAL_RING"
        elif mode_name == "LEFT":
            mode_name = "HEMIFIELD_LEFT"
        elif mode_name == "RIGHT":
            mode_name = "HEMIFIELD_RIGHT"
        elif mode_name == "SPLIT":
            mode_name = "SPLIT_HEMIFIELD"

        sham_name = str(data.get("sham", "none")).upper()
        if sham_name == "JITTER":
            sham_name = "PHASE_JITTER"

        return cls(
            target_freq=float(data.get("target_freq", 40.0)),
            waveform=WaveformType[wf_name],
            mode=StimulationMode[mode_name],
            duration=float(data.get("duration", 0.0)),
            ramp=float(data.get("ramp", 0.0)),
            sham=ShamType[sham_name],
            sham_seed=data.get("sham_seed"),
            gamma=float(data.get("gamma", 1.0)),
            brightness=float(data.get("brightness", 1.0)),
            phase=float(data.get("phase", 0.0)),
            right_freq=float(data["right_freq"]) if data.get("right_freq") is not None else None,
            right_phase=float(data.get("right_phase", 0.0)),
            calibration_file=data.get("calibration_file"),
            compat_mode=str(data.get("compat_mode", "standard")),
        )

    def to_cli_args(self) -> List[str]:
        """Convert protocol parameters into CLI argument tokens for entrainment_engine.py."""
        mode_map = {
            StimulationMode.FULL_SCREEN: "full",
            StimulationMode.PERIPHERAL_RING: "ring",
            StimulationMode.HEMIFIELD_LEFT: "left",
            StimulationMode.HEMIFIELD_RIGHT: "right",
            StimulationMode.SPLIT_HEMIFIELD: "split",
            StimulationMode.QUADRANT_TL: "quad_tl",
            StimulationMode.QUADRANT_TR: "quad_tr",
            StimulationMode.QUADRANT_BL: "quad_bl",
            StimulationMode.QUADRANT_BR: "quad_br",
        }
        cmd = [
            "--freq", str(self.target_freq),
            "--waveform", self.waveform.name.lower(),
            "--mode", mode_map.get(self.mode, "full"),
            "--duration", str(self.duration),
            "--ramp", str(self.ramp),
            "--sham", self.sham.name.lower(),
            "--gamma", str(self.gamma),
            "--brightness", str(self.brightness),
            "--phase", str(self.phase),
            "--phase-right", str(self.right_phase),
            "--compat", self.compat_mode,
        ]
        if self.right_freq is not None and self.right_freq > 0:
            cmd.extend(["--freq-right", str(self.right_freq)])
        if self.sham_seed is not None:
            cmd.extend(["--sham-seed", str(self.sham_seed)])
        if self.calibration_file:
            cmd.extend(["--calib-file", self.calibration_file])
        return cmd
