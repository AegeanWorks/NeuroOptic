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

### ADR-003: STATIC normalizes to SINE 0.5 hold; launcher validates, calibration header explicit
- **Date**: 2026-11-06
- **Status**: Accepted
- **Context**: ADR-002 fixed STATIC init but preserved the requested waveform, so SQUARE/TRIANGLE held phase-dependent extremes and AM still advanced its carrier (30 Hz flicker on a sham that must not flicker); `-0.0` logged as `-0.0 Hz`; R-Freq was silently ignored outside SPLIT; launcher passed raw strings to the CLI with no range checks; calibration silently dropped a header-looking first row even when it was malformed data.
- **Decision**: STATIC forces SINE with zero phase offsets (reproducible 0.5 x brightness hold, no AM carrier); `validate_frequency` normalizes `-0.0` to `0.0`; `initialize_hardware` warns when R-Freq differs outside SPLIT and gates the AM carrier on either hemifield; launcher validates freq/duration/ramp/gamma/brightness/phase ranges before `Popen` and warns when R-Freq is ignored; calibration only skips row 1 silently when both columns are non-numeric.
- **Consequences**: Sham control is truly static and reproducible; invalid GUI input fails fast with a dialog instead of a dead subprocess; calibration errors stay visible; drift log uses EXCELLENT/GOOD/ACCEPTABLE/POOR tiers. 3 new tests (SINE hold, -0.0, first-row warn) bring the shield to 24 green.

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.
