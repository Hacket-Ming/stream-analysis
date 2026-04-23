"""H.265 parsers for AUD, Filler Data, EOS, EOB, etc."""

from stream_analysis.bitreader import BitReader
from stream_analysis.h265.definitions import PRIMARY_PIC_TYPE_NAMES


def parse_aud(reader: BitReader) -> dict:
    """Parse Access Unit Delimiter (NAL type 35)."""
    pic_type = reader.read_bits(3)
    return {
        "pic_type": pic_type,
        "pic_type_name": PRIMARY_PIC_TYPE_NAMES.get(pic_type, "unknown"),
    }


def parse_filler_data(raw_data: bytes) -> dict:
    """Parse Filler Data (NAL type 38). Just record size."""
    return {
        "filler_size": len(raw_data) - 2,  # minus 2-byte NAL header
    }


def parse_eos() -> dict:
    """Parse End of Sequence (NAL type 36). No payload."""
    return {}


def parse_eob() -> dict:
    """Parse End of Bitstream (NAL type 37). No payload."""
    return {}
