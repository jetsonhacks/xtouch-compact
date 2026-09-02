import pytest

from xtouch_compact import (
    Button,
    ButtonPressed,
    ButtonReleased,
    ControlChange,
    Encoder,
    EncoderPositionReported,
    EncoderPressed,
    EncoderReleased,
    Fader,
    FaderPositionReported,
    FaderReleased,
    FaderTouched,
    InboundDecoder,
    Layer,
    NoteOff,
    NoteOn,
    ProgramChange,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            ControlChange(1, 1, 63),
            FaderPositionReported(
                Fader.CHANNEL_1, Layer.A, 63, ControlChange(1, 1, 63)
            ),
        ),
        (
            ControlChange(1, 28, 64),
            FaderPositionReported(
                Fader.CHANNEL_1, Layer.B, 64, ControlChange(1, 28, 64)
            ),
        ),
        (
            ControlChange(1, 101, 127),
            FaderTouched(Fader.CHANNEL_1, Layer.A, ControlChange(1, 101, 127)),
        ),
        (
            ControlChange(1, 101, 0),
            FaderReleased(Fader.CHANNEL_1, Layer.A, ControlChange(1, 101, 0)),
        ),
        (
            ControlChange(1, 37, 42),
            EncoderPositionReported(
                Encoder.CHANNEL_1, Layer.B, 42, ControlChange(1, 37, 42)
            ),
        ),
        (
            NoteOn(1, 55, 127),
            EncoderPressed(Encoder.CHANNEL_1, Layer.B, NoteOn(1, 55, 127)),
        ),
        (
            NoteOff(1, 55, 0),
            EncoderReleased(Encoder.CHANNEL_1, Layer.B, NoteOff(1, 55, 0)),
        ),
        (
            NoteOn(1, 54, 127),
            ButtonPressed(Button.PLAY, Layer.A, NoteOn(1, 54, 127)),
        ),
        (
            NoteOff(1, 109, 0),
            ButtonReleased(Button.PLAY, Layer.B, NoteOff(1, 109, 0)),
        ),
    ],
)
def test_decoder_emits_typed_physical_events(
    decoder: InboundDecoder, raw: object, expected: object
) -> None:
    assert decoder.decode(raw) == expected


def test_same_control_uses_message_address_to_identify_layer(
    decoder: InboundDecoder,
) -> None:
    layer_a = decoder.decode(NoteOn(1, 54, 127))
    layer_b = decoder.decode(NoteOn(1, 109, 127))

    assert isinstance(layer_a, ButtonPressed)
    assert isinstance(layer_b, ButtonPressed)
    assert layer_a.button is layer_b.button is Button.PLAY
    assert layer_a.layer is Layer.A
    assert layer_b.layer is Layer.B


def test_repeated_encoder_values_remain_observable(decoder: InboundDecoder) -> None:
    raw = ControlChange(1, 10, 127)

    first = decoder.decode(raw)
    second = decoder.decode(raw)

    assert isinstance(first, EncoderPositionReported)
    assert isinstance(second, EncoderPositionReported)
    assert first is not second


@pytest.mark.parametrize(
    "raw",
    [
        ControlChange(2, 1, 64),
        ControlChange(1, 127, 64),
        ControlChange(1, 101, 64),
        NoteOn(1, 54, 1),
        NoteOff(1, 54, 1),
        ControlChange(1, 26, 64),
        ProgramChange(1, 0),
    ],
)
def test_decoder_returns_none_for_unknown_or_unsupported_traffic(
    decoder: InboundDecoder, raw: object
) -> None:
    assert decoder.decode(raw) is None
