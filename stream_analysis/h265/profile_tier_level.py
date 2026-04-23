"""H.265 profile_tier_level() parsing.

Shared by VPS and SPS. Follows ITU-T H.265 Section 7.3.3.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h265.definitions import PROFILE_NAMES


def parse_profile_tier_level(reader: BitReader, profile_present_flag: bool,
                             max_sub_layers_minus1: int) -> dict:
    """Parse profile_tier_level()."""
    ptl = {}

    if profile_present_flag:
        ptl["general_profile_space"] = reader.read_bits(2)
        ptl["general_tier_flag"] = reader.read_bits(1)
        ptl["general_profile_idc"] = reader.read_bits(5)
        ptl["general_profile_name"] = PROFILE_NAMES.get(ptl["general_profile_idc"], "Unknown")

        ptl["general_profile_compatibility_flags"] = reader.read_bits(32)

        ptl["general_progressive_source_flag"] = reader.read_bits(1)
        ptl["general_interlaced_source_flag"] = reader.read_bits(1)
        ptl["general_non_packed_constraint_flag"] = reader.read_bits(1)
        ptl["general_frame_only_constraint_flag"] = reader.read_bits(1)

        # 44 bits of constraint flags (reserved)
        reader.skip_bits(44)

    ptl["general_level_idc"] = reader.read_bits(8)
    ptl["general_level"] = f"{ptl['general_level_idc'] / 30:.1f}"

    # Sub-layer profile/level presence flags
    sub_layer_profile_present = []
    sub_layer_level_present = []
    for _ in range(max_sub_layers_minus1):
        sub_layer_profile_present.append(reader.read_bits(1))
        sub_layer_level_present.append(reader.read_bits(1))

    # Reserved bits if max_sub_layers_minus1 > 0
    if max_sub_layers_minus1 > 0:
        for _ in range(8 - max_sub_layers_minus1):
            reader.skip_bits(2)  # reserved_zero_2bits

    # Sub-layer profile/tier/level
    ptl["sub_layers"] = []
    for i in range(max_sub_layers_minus1):
        sub = {}
        if sub_layer_profile_present[i]:
            sub["sub_layer_profile_space"] = reader.read_bits(2)
            sub["sub_layer_tier_flag"] = reader.read_bits(1)
            sub["sub_layer_profile_idc"] = reader.read_bits(5)
            sub["sub_layer_profile_compatibility_flags"] = reader.read_bits(32)
            sub["sub_layer_progressive_source_flag"] = reader.read_bits(1)
            sub["sub_layer_interlaced_source_flag"] = reader.read_bits(1)
            sub["sub_layer_non_packed_constraint_flag"] = reader.read_bits(1)
            sub["sub_layer_frame_only_constraint_flag"] = reader.read_bits(1)
            reader.skip_bits(44)  # constraint flags
        if sub_layer_level_present[i]:
            sub["sub_layer_level_idc"] = reader.read_bits(8)
        ptl["sub_layers"].append(sub)

    return ptl
