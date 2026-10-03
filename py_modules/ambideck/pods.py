"""Minimal SPA pod builder/parser for negotiating a small frame with gamescope's PipeWire stream."""
from __future__ import annotations

import struct

SPA_TYPE_Id, SPA_TYPE_Rectangle, SPA_TYPE_Object, SPA_TYPE_Choice = 3, 10, 15, 19
SPA_TYPE_OBJECT_Format = 0x40003
SPA_PARAM_EnumFormat, SPA_PARAM_Format = 3, 4
SPA_FORMAT_mediaType, SPA_FORMAT_mediaSubtype = 1, 2
SPA_FORMAT_VIDEO_format, SPA_FORMAT_VIDEO_size = 0x20001, 0x20003
SPA_FORMAT_VIDEO_requested_size = 0x70000  # gamescope extension (pipewire_gamescope.hpp)
SPA_MEDIA_TYPE_video, SPA_MEDIA_SUBTYPE_raw = 2, 1
SPA_VIDEO_FORMAT_BGRx = 8
SPA_CHOICE_Range = 1


def pod(type_: int, body: bytes) -> bytes:
    return struct.pack("<II", len(body), type_) + body + b"\0" * (-len(body) % 8)


def pod_id(value: int) -> bytes:
    return pod(SPA_TYPE_Id, struct.pack("<I", value))


def pod_rect(width: int, height: int) -> bytes:
    return pod(SPA_TYPE_Rectangle, struct.pack("<II", width, height))


def pod_rect_range(default, low, high) -> bytes:
    body = struct.pack("<II", SPA_CHOICE_Range, 0) + struct.pack("<II", 8, SPA_TYPE_Rectangle)
    body += b"".join(struct.pack("<II", *r) for r in (default, low, high))
    return pod(SPA_TYPE_Choice, body)


def prop(key: int, value_pod: bytes) -> bytes:
    return struct.pack("<II", key, 0) + value_pod


def enum_format(width: int, height: int) -> bytes:
    """Our format offer. Never narrower than gamescope's own BGRx offer (any size, any requested size):
    a failed negotiation makes gamescope tear its stream down until Game Mode restarts."""
    props = b"".join([
        prop(SPA_FORMAT_mediaType, pod_id(SPA_MEDIA_TYPE_video)),
        prop(SPA_FORMAT_mediaSubtype, pod_id(SPA_MEDIA_SUBTYPE_raw)),
        prop(SPA_FORMAT_VIDEO_format, pod_id(SPA_VIDEO_FORMAT_BGRx)),
        prop(SPA_FORMAT_VIDEO_size, pod_rect_range((width, height), (1, 1), (16384, 16384))),
        prop(SPA_FORMAT_VIDEO_requested_size, pod_rect(width, height)),
    ])
    return pod(SPA_TYPE_Object, struct.pack("<II", SPA_TYPE_OBJECT_Format, SPA_PARAM_EnumFormat) + props)


def parse_format(raw: bytes) -> dict:
    """Format and size from a fixated Format pod; fixated values may stay wrapped in a Choice."""
    if len(raw) < 16:
        return {}
    size, type_ = struct.unpack_from("<II", raw)
    if type_ != SPA_TYPE_Object:
        return {}
    raw = raw[: 8 + size]
    out: dict = {}
    off = 16  # pod header + object type/id
    while off + 16 <= len(raw):
        key, _flags, vsize, vtype = struct.unpack_from("<IIII", raw, off)
        body = raw[off + 16: off + 16 + vsize]
        if vtype == SPA_TYPE_Choice and len(body) >= 16:
            _ctype, _cflags, _csize, vtype = struct.unpack_from("<IIII", body)
            body = body[16:]
        if key == SPA_FORMAT_VIDEO_format and vtype == SPA_TYPE_Id and len(body) >= 4:
            out["format"] = struct.unpack_from("<I", body)[0]
        elif key == SPA_FORMAT_VIDEO_size and vtype == SPA_TYPE_Rectangle and len(body) >= 8:
            out["size"] = struct.unpack_from("<II", body)
        off += 16 + vsize + (-vsize % 8)
    return out
