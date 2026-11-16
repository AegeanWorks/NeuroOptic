"""Headless session controller managing entrainment execution lifecycle and process supervision."""

from enum import Enum, auto
import os
import subprocess
import sys
from typing import Any, Callable, List, Optional, Tuple

from core.protocol import EntrainmentProtocol, ShamType, WaveformType
from core.safety import PhoticRiskAssessment, calculate_photic_risk, validate_hardware_limits


class SessionState(Enum):
    IDLE = auto()
    VALIDATED = auto()
    RUNNING = auto()
    TERMINATED = auto()
    FAILED = auto()


class SessionController:
    """Manages protocol validation, subprocess execution, and session lifecycle."""

    def __init__(self, protocol: EntrainmentProtocol, engine_path: Optional[str] = None):
        self.protocol = protocol
        if engine_path is None:
            engine_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "entrainment_engine.py")
        self.engine_path = engine_path
        self.state = SessionState.IDLE
        self.process: Optional[subprocess.Popen] = None
        self.last_assessment: Optional[PhoticRiskAssessment] = None

    def validate(self, refresh_rate: int = 60) -> PhoticRiskAssessment:
        """Validates protocol against display refresh limits and calculates bio-safety risk."""
        allow_zero = (self.protocol.sham == ShamType.STATIC)
        validate_hardware_limits(
            self.protocol.target_freq,
            refresh_rate,
            self.protocol.waveform,
            allow_zero=allow_zero
        )
        if self.protocol.right_freq is not None and self.protocol.right_freq > 0:
            validate_hardware_limits(
                self.protocol.right_freq,
                refresh_rate,
                self.protocol.waveform,
                allow_zero=allow_zero
            )
        assessment = calculate_photic_risk(
            self.protocol.target_freq,
            self.protocol.waveform,
            self.protocol.mode
        )
        self.last_assessment = assessment
        self.state = SessionState.VALIDATED
        return assessment

    def build_command(self, python_exe: str = sys.executable) -> List[str]:
        """Constructs subprocess command line tokens for the entrainment engine."""
        return [python_exe, self.engine_path] + self.protocol.to_cli_args()

    def start_session(self, popen_fn: Callable[..., Any] = subprocess.Popen) -> Any:
        """Launches the entrainment engine subprocess under process tracking."""
        if not os.path.exists(self.engine_path):
            self.state = SessionState.FAILED
            raise FileNotFoundError(f"Entrainment engine not found at: {self.engine_path}")

        cmd = self.build_command()
        try:
            self.process = popen_fn(cmd)
            self.state = SessionState.RUNNING
            return self.process
        except Exception:
            self.state = SessionState.FAILED
            raise

    def stop_session(self) -> bool:
        """Terminates the running engine subprocess safely."""
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.state = SessionState.TERMINATED
            return True
        self.state = SessionState.IDLE
        return False
