# Development

Run `uv sync` from the repository root to install the library in editable
mode and its development tools. Run these checks before submitting changes:

```bash
uv run pytest --cov=xtouch_compact --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

CI runs tests on Python 3.10–3.13, with coverage on 3.13, and runs lint,
formatting, and type checks. The configured coverage floor is 90%. Unit tests
need neither a controller nor `/dev/snd/seq`; examples remain manual hardware
checks. Passing software tests establishes emitted messages and state behavior,
not physical movement, display appearance, timing, or device presence.

## Test Responsibilities

| Tests | Responsibility |
|---|---|
| `test_midi.py`, `test_decoder.py`, `test_semantic_api.py` | Value boundaries, input decoding, and output encoding |
| `test_device_map.py` | Map completeness, ranges, collision guards, and independent protocol addresses |
| `test_fader_state.py`, `test_surface_state.py` | Ownership, observation validity, feedback invalidation, and reconciliation |
| `test_session.py` | Construction, lifecycle, context cleanup, and the receive interface |
| `test_runtime.py` | Session recovery and state preservation using an instrumented transport |
| `test_alsa_transport.py` | ALSA adaptation, actual discovery logic, subscriptions, and transport cleanup |
| `test_public_api.py` | Export compatibility and the public exception hierarchy |
| `test_project_foundation.py` | Availability and basic integrity of historical evidence |

Add a regression where the behavior belongs, rather than repeating it in a
second public-API suite. Keep distinct assertions when consolidating tests.
The simple `FakeTransport` supports ordinary session tests; the instrumented
transport in recovery tests records resource and failure sequences. Neither
fake establishes physical hardware behavior.

Protocol vectors use literal expectations justified by the manufacturer
reference or dated measurements. A test deriving its expected message from
the runtime table checks consistency, not the table's protocol correctness.
Keep both independent evidence and structural invariants. Test changes should
catch representative mistakes, such as swapped ring-mode values or shifted
address ranges, rather than merely preserve a coverage percentage.

The historical YAML remains readable development evidence. Its integrity
check does not require it to track every future runtime correction; see
[specs/README.md](../specs/README.md). Runtime protocol tests do not load it.

## Documentation Responsibilities

- **README:** purpose, requirements, installation, first use, and navigation.
- **Usage:** application workflows and behavioral rules, including ownership.
- **API:** supported signatures, fields, return values, and exceptions.
- **Hardware:** host setup, device prerequisites, and manual bring-up.
- **MIDI map and observations:** manufacturer claims and dated measurements,
  kept distinct. The observation-disposition register links policy to evidence.

When behavior changes, update its regression test, API docstring, and the
relevant usage/API section together. Check local links and runnable examples.
Preserve historical observations as dated evidence; annotate later decisions
instead of rewriting earlier measurements. Link to the responsible document
instead of repeating its detailed rules in the README.
