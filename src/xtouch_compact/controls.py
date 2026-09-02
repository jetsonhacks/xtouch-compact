"""Stable identities for physical X-TOUCH COMPACT controls."""

from __future__ import annotations

from enum import Enum
from typing import TypeAlias


class Layer(Enum):
    A = "layer_a"
    B = "layer_b"


class Fader(Enum):
    CHANNEL_1 = "fader_1"
    CHANNEL_2 = "fader_2"
    CHANNEL_3 = "fader_3"
    CHANNEL_4 = "fader_4"
    CHANNEL_5 = "fader_5"
    CHANNEL_6 = "fader_6"
    CHANNEL_7 = "fader_7"
    CHANNEL_8 = "fader_8"
    MAIN = "master_fader"


class Encoder(Enum):
    CHANNEL_1 = "encoder_1"
    CHANNEL_2 = "encoder_2"
    CHANNEL_3 = "encoder_3"
    CHANNEL_4 = "encoder_4"
    CHANNEL_5 = "encoder_5"
    CHANNEL_6 = "encoder_6"
    CHANNEL_7 = "encoder_7"
    CHANNEL_8 = "encoder_8"
    POSITION_9 = "encoder_9"
    POSITION_10 = "encoder_10"
    POSITION_11 = "encoder_11"
    POSITION_12 = "encoder_12"
    POSITION_13 = "encoder_13"
    POSITION_14 = "encoder_14"
    POSITION_15 = "encoder_15"
    POSITION_16 = "encoder_16"


class Button(Enum):
    UPPER_TOP_1 = "upper_top_1"
    UPPER_TOP_2 = "upper_top_2"
    UPPER_TOP_3 = "upper_top_3"
    UPPER_TOP_4 = "upper_top_4"
    UPPER_TOP_5 = "upper_top_5"
    UPPER_TOP_6 = "upper_top_6"
    UPPER_TOP_7 = "upper_top_7"
    UPPER_TOP_8 = "upper_top_8"
    UPPER_MID_1 = "upper_mid_1"
    UPPER_MID_2 = "upper_mid_2"
    UPPER_MID_3 = "upper_mid_3"
    UPPER_MID_4 = "upper_mid_4"
    UPPER_MID_5 = "upper_mid_5"
    UPPER_MID_6 = "upper_mid_6"
    UPPER_MID_7 = "upper_mid_7"
    UPPER_MID_8 = "upper_mid_8"
    UPPER_BOTTOM_1 = "upper_bottom_1"
    UPPER_BOTTOM_2 = "upper_bottom_2"
    UPPER_BOTTOM_3 = "upper_bottom_3"
    UPPER_BOTTOM_4 = "upper_bottom_4"
    UPPER_BOTTOM_5 = "upper_bottom_5"
    UPPER_BOTTOM_6 = "upper_bottom_6"
    UPPER_BOTTOM_7 = "upper_bottom_7"
    UPPER_BOTTOM_8 = "upper_bottom_8"
    LOWER_1 = "lower_1"
    LOWER_2 = "lower_2"
    LOWER_3 = "lower_3"
    LOWER_4 = "lower_4"
    LOWER_5 = "lower_5"
    LOWER_6 = "lower_6"
    LOWER_7 = "lower_7"
    LOWER_8 = "lower_8"
    LOWER_9 = "lower_9"
    REWIND = "right_1"
    FAST_FORWARD = "right_2"
    LOOP = "right_3"
    RECORD = "right_4"
    STOP = "right_5"
    PLAY = "right_6"
    LAYER_A = "layer_a"
    LAYER_B = "layer_b"


class FootControl(Enum):
    EXPRESSION_PEDAL = "expression_pedal"
    FOOT_SWITCH = "foot_switch"


MappedControl: TypeAlias = Fader | Encoder | Button | FootControl
