# Decisions

Why this project is built the way it is, oldest first. One entry per decision that changes a
contract, a dependency, a data format or the architecture; IDs are consecutive and never reused.

<!-- Entry format:
### ADR-001: <decision in one line>
- **Date**: YYYY-MM-DD
- **Status**: Accepted
- **Context**: <what forced the decision>
- **Decision**: <what was decided>
- **Consequences**: <what follows, including what it costs>
-->

### ADR-001: Controller keeper via PrintWindow; engine window stays unpressed
- **Date**: 2026-11-03
- **Status**: Accepted
- **Context**: No screenshots existed; the controller is one window and the fullscreen engine opens only on START (flashing visuals must not run unattended).
- **Decision**: Register `2026-11-03-launcher.png` (`python launcher.py`, PrintWindow on `NeuroOptic Controller`, 516x939, commit `36f9038`) in `.aikit/media.json` and the README `aegean:screenshots` block. The controller is the whole pre-stimulation UI, so one keeper is full coverage.
- **Consequences**: README proves the current controller. Reproduce with the launch plus PrintWindow helper above.

### ADR-002: STATIC sham holds 0 Hz via explicit opt-in; both hemifields zeroed
- **Date**: 2026-11-03
- **Status**: Accepted
- **Context**: Since wave 0 (`bf0f1ff`) STATIC set only `target_freq = 0.0` while `validate_frequency` rejects `<= 0`, so `initialize_hardware` raised `ValueError` and exited instead of showing static light; `right_freq` kept flickering in SPLIT mode. Reproduced: `validate_frequency(0.0, 60, SINE)` raises `ValueError: Frequency must be positive`.
- **Decision**: `validate_frequency(..., allow_zero=False)` returns `(0.0, waveform)` early only when `allow_zero` is true; `EntrainmentEngine` sets both `target_freq` and `right_freq` to `0.0` for STATIC and passes `allow_zero=(sham == STATIC)` through both hardware-validation calls; band label logs `Static` for the hold.
- **Consequences**: `--sham static` initializes; default Nyquist/positivity guards unchanged (existing `0.0 rejected` test still green); 2 new tests cover the opt-in and both-zero hold.

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.
