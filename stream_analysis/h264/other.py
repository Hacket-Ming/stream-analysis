"""H.264 parsers for AUD, Filler Data, End of Sequence/Stream, etc."""

from stream_analysis.bitreader import BitReader
from stream_analysis.h264.definitions import PRIMARY_PIC_TYPE_NAMES


def parse_aud(reader: BitReader) -> dict:
    """Parse Access Unit Delimiter (NAL type 9)."""
    primary_pic_type = reader.read_bits(3)
    return {
        "primary_pic_type": primary_pic_type,
        "primary_pic_type_name": PRIMARY_PIC_TYPE_NAMES.get(primary_pic_type, "unknown"),
    }


def parse_filler_data(raw_data: bytes) -> dict:
    """Parse Filler Data (NAL type 12). Just record size."""
    return {
        "filler_size": len(raw_data) - 1,  # minus NAL header byte
    }


def parse_end_of_sequence() -> dict:
    """Parse End of Sequence (NAL type 10). No payload."""
    return {}


def parse_end_of_stream() -> dict:
    """Parse End of Stream (NAL type 11). No payload."""
    return {}
