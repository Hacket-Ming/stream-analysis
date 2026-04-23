"""H.265 SEI (Supplemental Enhancement Information) message parser.

Follows ITU-T H.265 Section 7.3.5.
Same framing as H.264 SEI (payload_type/size accumulated from 0xFF bytes).
"""

from stream_analysis.bitreader import BitReader


SEI_PAYLOAD_TYPE_NAMES = {
    0: "buffering_period",
    1: "pic_timing",
    5: "user_data_unregistered",
    6: "recovery_point",
    19: "scene_info",
    45: "frame_packing_arrangement",
    47: "display_orientation",
    128: "structure_of_pictures_info",
    129: "active_parameter_sets",
    130: "decoding_unit_info",
    131: "temporal_sub_layer_zero_index",
    132: "decoded_picture_hash",
    133: "scalable_nesting",
    134: "region_refresh_info",
    137: "mastering_display_colour_volume",
    144: "content_light_level_info",
    147: "alternative_transfer_characteristics",
}


def parse_sei(reader: BitReader) -> list[dict]:
    """Parse SEI messages from RBSP data (after 2-byte NAL header)."""
    messages = []
    while reader.bits_remaining() > 8:
        msg = _parse_sei_message(reader)
        if msg:
            messages.append(msg)
    return messages


def _parse_sei_message(reader: BitReader) -> dict:
    """Parse a single SEI message."""
    payload_type = 0
    while True:
        byte = reader.read_bits(8)
        payload_type += byte
        if byte != 0xFF:
            break

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

    start_pos = reader.bit_position()
    try:
        if payload_type == 5:
            _parse_user_data_unregistered(reader, msg, payload_size)
        elif payload_type == 6:
            _parse_recovery_point(reader, msg)
        elif payload_type == 132:
            _parse_decoded_picture_hash(reader, msg, payload_size)
        elif payload_type == 137:
            _parse_mastering_display(reader, msg)
        elif payload_type == 144:
            _parse_content_light_level(reader, msg)
        else:
            reader.skip_bits(payload_size * 8)
    except (EOFError, ValueError):
        consumed = reader.bit_position() - start_pos
        remaining = payload_size * 8 - consumed
        if remaining > 0:
            reader.skip_bits(remaining)
        msg["_parse_error"] = True

    return msg


def _parse_user_data_unregistered(reader: BitReader, msg: dict, payload_size: int) -> None:
    """Parse user_data_unregistered SEI."""
    if payload_size < 16:
        reader.skip_bits(payload_size * 8)
        return

    uuid_bytes = []
    for _ in range(16):
        uuid_bytes.append(reader.read_bits(8))
    msg["uuid"] = "-".join(
        "".join(f"{b:02x}" for b in uuid_bytes[s:e])
        for s, e in [(0, 4), (4, 6), (6, 8), (8, 10), (10, 16)]
    )

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
    """Parse recovery_point SEI."""
    msg["recovery_poc_cnt"] = reader.read_signed_exp_golomb()
    msg["exact_match_flag"] = reader.read_bits(1)
    msg["broken_link_flag"] = reader.read_bits(1)


def _parse_decoded_picture_hash(reader: BitReader, msg: dict, payload_size: int) -> None:
    """Parse decoded_picture_hash SEI."""
    msg["hash_type"] = reader.read_bits(8)
    hash_type_names = {0: "MD5", 1: "CRC", 2: "Checksum"}
    msg["hash_type_name"] = hash_type_names.get(msg["hash_type"], "unknown")
    reader.skip_bits((payload_size - 1) * 8)


def _parse_mastering_display(reader: BitReader, msg: dict) -> None:
    """Parse mastering_display_colour_volume SEI."""
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
    """Parse content_light_level_info SEI."""
    msg["max_content_light_level"] = reader.read_bits(16)
    msg["max_pic_average_light_level"] = reader.read_bits(16)
