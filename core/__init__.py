"""NeuroOptic Core: Headless mechanics, protocol schemas, and safety validation."""

from core.protocol import (
    EntrainmentProtocol,
    FrequencyBand,
    PRESETS,
    ShamType,
    StimulationMode,
    WaveformType,
)
from core.safety import (
    PhoticRiskAssessment,
    RiskTier,
    calculate_photic_risk,
    validate_hardware_limits,
)
from core.session_controller import (
    SessionController,
    SessionState,
)

__all__ = [
    "EntrainmentProtocol",
    "FrequencyBand",
    "PRESETS",
    "ShamType",
    "StimulationMode",
    "WaveformType",
    "PhoticRiskAssessment",
    "RiskTier",
    "calculate_photic_risk",
    "validate_hardware_limits",
    "SessionController",
    "SessionState",
]
