import pytest

from xtouch_compact import ControlChange, NoteOff, NoteOn, ProgramChange


@pytest.mark.parametrize(
    ("message_type", "arguments"),
    [
        (NoteOn, (1, 0, 0)),
        (NoteOn, (16, 127, 127)),
        (NoteOff, (1, 0, 0)),
        (NoteOff, (16, 127, 127)),
        (ControlChange, (1, 0, 0)),
        (ControlChange, (16, 127, 127)),
        (ProgramChange, (1, 0)),
        (ProgramChange, (16, 127)),
    ],
)
def test_raw_midi_messages_accept_boundary_values(
    message_type: type, arguments: tuple[int, ...]
) -> None:
    assert message_type(*arguments) is not None


@pytest.mark.parametrize(
    ("message_type", "arguments", "field"),
    [
        (NoteOn, (0, 1, 1), "midi_channel"),
        (NoteOn, (17, 1, 1), "midi_channel"),
        (NoteOn, (1, -1, 1), "note_number"),
        (NoteOff, (1, 128, 1), "note_number"),
        (NoteOn, (1, 1, -1), "velocity"),
        (NoteOff, (1, 1, 128), "velocity"),
        (ControlChange, (1, -1, 1), "control_number"),
        (ControlChange, (1, 128, 1), "control_number"),
        (ControlChange, (1, 1, -1), "value"),
        (ControlChange, (1, 1, 128), "value"),
        (ProgramChange, (0, 1), "midi_channel"),
        (ProgramChange, (1, -1), "program_number"),
        (ProgramChange, (1, 128), "program_number"),
    ],
)
def test_raw_midi_messages_reject_out_of_range_values(
    message_type: type, arguments: tuple[int, ...], field: str
) -> None:
    with pytest.raises(ValueError, match=field):
        message_type(*arguments)


def test_raw_midi_messages_reject_non_integer_values() -> None:
    with pytest.raises(TypeError, match="midi_channel"):
        NoteOn(True, 1, 1)
