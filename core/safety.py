"""Bio-safety calculations, photic risk scoring, and hardware Nyquist validation."""

from dataclasses import dataclass
from enum import Enum, auto
import math
from typing import Tuple

from core.protocol import StimulationMode, WaveformType


class RiskTier(Enum):
    SAFE = auto()
    CAUTION = auto()
    HIGH_RISK_PSE = auto()


@dataclass(frozen=True)
class PhoticRiskAssessment:
    """Evaluation result of photic driving and seizure risk."""

    tier: RiskTier
    score: float
    warning_message: str
    requires_human_confirmation: bool


def calculate_photic_risk(freq: float, waveform: WaveformType,
                           mode: StimulationMode = StimulationMode.FULL_SCREEN) -> PhoticRiskAssessment:
    """
    Evaluates photosensitive epilepsy (PSE) risk for given stimulation parameters.

    The 10-30 Hz frequency range represents the peak human photic driving band where
    visual flicker can trigger photoparoxysmal electroencephalographic responses.
    Square waveforms generate steep luminance transitions with high harmonic content,
    maximizing epileptogenic risk.
    """
    if freq <= 0.0:
        return PhoticRiskAssessment(
            tier=RiskTier.SAFE,
            score=0.0,
            warning_message="Static / Zero-frequency hold poses zero photic oscillation risk.",
            requires_human_confirmation=False,
        )

    # High-Risk Window: 10 to 30 Hz with Square Wave
    if 10.0 <= freq <= 30.0 and waveform == WaveformType.SQUARE:
        return PhoticRiskAssessment(
            tier=RiskTier.HIGH_RISK_PSE,
            score=0.95,
            warning_message=(
                f"CRITICAL SAFETY WARNING: {freq:.1f} Hz Square Wave is in the primary "
                "photosensitive epilepsy window (10-30 Hz) with steep harmonic transitions."
            ),
            requires_human_confirmation=True,
        )

    # Caution Window: 10 to 30 Hz with Sine / AM / Triangle
    if 10.0 <= freq <= 30.0:
        return PhoticRiskAssessment(
            tier=RiskTier.CAUTION,
            score=0.55,
            warning_message=(
                f"Elevated Caution: {freq:.1f} Hz is within the human photic driving range. "
                "Smooth waveform reduces harmonic risk."
            ),
            requires_human_confirmation=False,
        )

    # Frequencies near alpha lower boundary or beta upper boundary
    if 8.0 <= freq < 10.0 or 30.0 < freq <= 45.0:
        return PhoticRiskAssessment(
            tier=RiskTier.SAFE,
            score=0.25,
            warning_message="Standard research entrainment band.",
            requires_human_confirmation=False,
        )

    return PhoticRiskAssessment(
        tier=RiskTier.SAFE,
        score=0.10,
        warning_message="Low-risk stimulation band.",
        requires_human_confirmation=False,
    )


def validate_hardware_limits(target_freq: float, refresh_rate: int,
                             waveform: WaveformType,
                             allow_zero: bool = False) -> Tuple[float, WaveformType]:
    """
    Validates stimulation frequency against display Nyquist limit and duty-cycle symmetry.

    Raises ValueError if target frequency exceeds refresh_rate / 2.0 or is non-positive
    when allow_zero is False.
    """
    if target_freq == 0.0 and allow_zero:
        return 0.0, waveform

    safe_ceiling = refresh_rate / 2.0
    if target_freq > safe_ceiling:
        raise ValueError(
            f"Target frequency {target_freq} Hz exceeds safe representable limit "
            f"({safe_ceiling} Hz) for current monitor refresh rate ({refresh_rate} Hz)."
        )

    if target_freq <= 0.0:
        raise ValueError("Frequency must be positive.")

    # Duty-cycle distortion check for Square waves
    if waveform == WaveformType.SQUARE:
        frames_per_half_cycle = refresh_rate / (2.0 * target_freq)
        if abs(frames_per_half_cycle - round(frames_per_half_cycle)) > 0.01:
            # Degrade to SINE to maintain 50% duty cycle
            return target_freq, WaveformType.SINE

    return target_freq, waveform
