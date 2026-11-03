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

## Licensing migration (agpl-final)

- New versions use the Aegean License 1.1 (AL-1.1); versions up to and including `agpl-final` remain under GNU AGPL-3.0.
- Rights holder: AegeanWorks; commercial use under ACL-1.0.
- Counsel review of the 1.1 texts remains pending.

## License notice cleanup (2026-10-26)

- The license-history notes were removed from README.md and COMMERCIAL.md: the project is offered only under the Aegean License 1.1 (AL-1.1), with commercial use under ACL-1.0.
