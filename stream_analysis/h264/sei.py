"""H.264 SEI (Supplemental Enhancement Information) message parser.

Follows ITU-T H.264 Section 7.3.2.3.
"""

from stream_analysis.bitreader import BitReader


SEI_PAYLOAD_TYPE_NAMES = {
    0: "buffering_period",
    1: "pic_timing",
    2: "pan_scan_rect",
    3: "filler_payload",
    4: "user_data_registered_itu_t_t35",
    5: "user_data_unregistered",
    6: "recovery_point",
    7: "dec_ref_pic_marking_repetition",
    8: "spare_pic",
    9: "scene_info",
    10: "sub_seq_info",
    11: "sub_seq_layer_characteristics",
    12: "sub_seq_characteristics",
    13: "full_frame_freeze",
    14: "full_frame_freeze_release",
    15: "full_frame_snapshot",
    16: "progressive_refinement_segment_start",
    17: "progressive_refinement_segment_end",
    18: "motion_constrained_slice_group_set",
    19: "film_grain_characteristics",
    20: "deblocking_filter_display_preference",
    21: "stereo_video_info",
    45: "frame_packing_arrangement",
    47: "display_orientation",
    128: "scalable_nesting",
    129: "scalability_info",
    137: "mastering_display_colour_volume",
    144: "content_light_level_info",
    147: "alternative_transfer_characteristics",
}


def parse_sei(reader: BitReader) -> list[dict]:
    """Parse SEI messages from RBSP data (after NAL header byte).

    An SEI NAL unit can contain multiple SEI messages.
    """
    messages = []
    while reader.bits_remaining() > 8:
        msg = _parse_sei_message(reader)
        if msg:
            messages.append(msg)
    return messages


def _parse_sei_message(reader: BitReader) -> dict:
    """Parse a single SEI message."""
    # Read payload type (accumulated from 0xFF bytes)
    payload_type = 0
    while True:
        byte = reader.read_bits(8)
        payload_type += byte
        if byte != 0xFF:
            break

    # Read payload size (accumulated from 0xFF bytes)
    payload_size = 0
    while True:
        byte = reader.read_bits(8)
        payload_size += byte
        if byte != 0xFF:
            break

    msg = {
        "payload_type": payload_type,
        "payload_type_name": SEI_PAYLOAD_TYPE_NAMES.get(payload_type, f"unknown({payload_type})"),
        "payload_size": payload_size,
    }

    # Parse known payload types
    start_pos = reader.bit_position()
    try:
        if payload_type == 0:
            _parse_buffering_period(reader, msg, payload_size)
        elif payload_type == 1:
            _parse_pic_timing(reader, msg, payload_size)
        elif payload_type == 5:
            _parse_user_data_unregistered(reader, msg, payload_size)
        elif payload_type == 6:
            _parse_recovery_point(reader, msg)
        elif payload_type == 137:
            _parse_mastering_display(reader, msg)
        elif payload_type == 144:
            _parse_content_light_level(reader, msg)
        else:
            # Skip unknown payload
            reader.skip_bits(payload_size * 8)
    except (EOFError, ValueError):
        # Skip remaining bits on error
        consumed = reader.bit_position() - start_pos
        remaining = payload_size * 8 - consumed
        if remaining > 0:
            reader.skip_bits(remaining)
        msg["_parse_error"] = True

    return msg


def _parse_buffering_period(reader: BitReader, msg: dict, payload_size: int) -> None:
    """Parse buffering_period SEI (type 0). Minimal: just record raw bytes."""
    # Full parsing requires HRD params from SPS, so just record the raw size
    reader.skip_bits(payload_size * 8)
    msg["note"] = "requires SPS HRD context for full decode"


def _parse_pic_timing(reader: BitReader, msg: dict, payload_size: int) -> None:
    """Parse pic_timing SEI (type 1). Minimal: just record raw bytes."""
    reader.skip_bits(payload_size * 8)
    msg["note"] = "requires SPS HRD/VUI context for full decode"


def _parse_user_data_unregistered(reader: BitReader, msg: dict, payload_size: int) -> None:
    """Parse user_data_unregistered SEI (type 5)."""
    if payload_size < 16:
        reader.skip_bits(payload_size * 8)
        return

    # Read UUID (16 bytes)
    uuid_bytes = []
    for _ in range(16):
        uuid_bytes.append(reader.read_bits(8))
    msg["uuid"] = "-".join(
        "".join(f"{b:02x}" for b in uuid_bytes[s:e])
        for s, e in [(0, 4), (4, 6), (6, 8), (8, 10), (10, 16)]
    )

    # Read remaining payload as text (often contains encoder info)
    remaining = payload_size - 16
    if remaining > 0:
        payload_bytes = bytearray()
        for _ in range(remaining):
            payload_bytes.append(reader.read_bits(8))
        try:
            msg["data"] = payload_bytes.rstrip(b"\x00").decode("utf-8", errors="replace")
        except Exception:
            msg["data_hex"] = payload_bytes.hex()


def _parse_recovery_point(reader: BitReader, msg: dict) -> None:
    """Parse recovery_point SEI (type 6)."""
    msg["recovery_frame_cnt"] = reader.read_unsigned_exp_golomb()
    msg["exact_match_flag"] = reader.read_bits(1)
    msg["broken_link_flag"] = reader.read_bits(1)
    msg["changing_slice_group_idc"] = reader.read_bits(2)


def _parse_mastering_display(reader: BitReader, msg: dict) -> None:
    """Parse mastering_display_colour_volume SEI (type 137)."""
    msg["display_primaries"] = []
    for _ in range(3):
        msg["display_primaries"].append({
            "x": reader.read_bits(16),
            "y": reader.read_bits(16),
        })
    msg["white_point_x"] = reader.read_bits(16)
    msg["white_point_y"] = reader.read_bits(16)
    msg["max_display_mastering_luminance"] = reader.read_bits(32)
    msg["min_display_mastering_luminance"] = reader.read_bits(32)


def _parse_content_light_level(reader: BitReader, msg: dict) -> None:
    """Parse content_light_level_info SEI (type 144)."""
    msg["max_content_light_level"] = reader.read_bits(16)
    msg["max_pic_average_light_level"] = reader.read_bits(16)
