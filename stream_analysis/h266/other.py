"""H.266 parsers for DCI, OPI, AUD, Filler Data, EOS, EOB, etc."""

from stream_analysis.bitreader import BitReader
from stream_analysis.h266.definitions import PRIMARY_PIC_TYPE_NAMES
from stream_analysis.h266.profile_tier_level import parse_profile_tier_level


def parse_dci(reader: BitReader) -> dict:
    """Parse Decoding Capability Information (DCI, NAL type 13).

    New in H.266. Provides PTL information for the decoder.
    """
    dci = {}
    reader.skip_bits(4)  # dci_reserved_zero_4bits
    dci["dci_num_ptls_minus1"] = reader.read_bits(4)

    dci["profile_tier_levels"] = []
    for _ in range(dci["dci_num_ptls_minus1"] + 1):
        ptl = parse_profile_tier_level(reader, True, 0)
        dci["profile_tier_levels"].append(ptl)

    dci["dci_extension_flag"] = reader.read_bits(1)

    return dci


def parse_opi(reader: BitReader) -> dict:
    """Parse Operating Point Information (OPI, NAL type 12).

    New in H.266.
    """
    opi = {}

    opi["opi_ols_info_present_flag"] = reader.read_bits(1)
    opi["opi_htid_info_present_flag"] = reader.read_bits(1)

    if opi["opi_ols_info_present_flag"]:
        opi["opi_ols_idx"] = reader.read_bits(9)

    if opi["opi_htid_info_present_flag"]:
        opi["opi_htid_plus1"] = reader.read_bits(3)

    opi["opi_extension_flag"] = reader.read_bits(1)

    return opi


def parse_aud(reader: BitReader) -> dict:
    """Parse Access Unit Delimiter (AUD, NAL type 20).

    H.266 AUD adds aud_irap_or_gdr_flag compared to H.265.
    """
    aud = {}
    aud["aud_irap_or_gdr_flag"] = reader.read_bits(1)
    aud["aud_pic_type"] = reader.read_bits(3)
    aud["pic_type_name"] = PRIMARY_PIC_TYPE_NAMES.get(aud["aud_pic_type"], "unknown")

    return aud


def parse_filler_data(raw_data: bytes) -> dict:
    """Parse Filler Data (NAL type 25). Just record size."""
    return {
        "filler_size": len(raw_data) - 2,  # minus 2-byte NAL header
    }


def parse_eos() -> dict:
    """Parse End of Sequence (NAL type 21). No payload."""
    return {}


def parse_eob() -> dict:
    """Parse End of Bitstream (NAL type 22). No payload."""
    return {}
