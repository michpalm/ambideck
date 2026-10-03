import struct

from ambideck.pods import SPA_VIDEO_FORMAT_BGRx, enum_format, parse_format, pod, pod_id, pod_rect, prop

# Bytes the spike sent to gamescope on the device (negotiated fine, renegotiated to 128x72).
GOLDEN_128x72 = bytes.fromhex(
    "a00000000f000000" "0300040003000000" "0100000000000000" "0400000003000000" "0200000000000000"
    "0200000000000000" "0400000003000000" "0100000000000000" "0100020000000000" "0400000003000000"
    "0800000000000000" "0300020000000000" "2800000013000000" "0100000000000000" "080000000a000000"
    "8000000048000000" "0100000001000000" "0040000000400000" "0000070000000000" "080000000a000000"
    "8000000048000000"
)


def fixated_format(size_pod):
    props = prop(0x20001, pod_id(SPA_VIDEO_FORMAT_BGRx)) + prop(0x20003, size_pod)
    return pod(15, struct.pack("<II", 0x40003, 4) + props)


def test_enum_format_matches_the_offer_proven_on_device():
    assert enum_format(128, 72) == GOLDEN_128x72


def test_parses_plain_values():
    assert parse_format(fixated_format(pod_rect(128, 72))) == {"format": 8, "size": (128, 72)}


def test_unwraps_choice_wrapped_values():
    choice = pod(19, struct.pack("<IIII", 0, 0, 8, 10) + struct.pack("<II", 64, 36))
    assert parse_format(fixated_format(choice)) == {"format": 8, "size": (64, 36)}


def test_non_object_or_truncated_input_gives_empty_result():
    assert parse_format(pod_id(3)) == {}
    assert parse_format(b"") == {}
    assert parse_format(fixated_format(pod_rect(1, 1))[:30]) in ({}, {"format": 8})
