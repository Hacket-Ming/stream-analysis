"""H.265 Video Parameter Set (VPS) parser.

Follows ITU-T H.265 Section 7.3.2.1.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h265.profile_tier_level import parse_profile_tier_level


def parse_vps(reader: BitReader) -> dict:
    """Parse an H.265 VPS from RBSP data (after 2-byte NAL header)."""
    vps = {}

    vps["vps_video_parameter_set_id"] = reader.read_bits(4)
    vps["vps_base_layer_internal_flag"] = reader.read_bits(1)
    vps["vps_base_layer_available_flag"] = reader.read_bits(1)
    vps["vps_max_layers_minus1"] = reader.read_bits(6)
    vps["vps_max_sub_layers_minus1"] = reader.read_bits(3)
    vps["vps_temporal_id_nesting_flag"] = reader.read_bits(1)
    reader.skip_bits(16)  # vps_reserved_0xffff_16bits

    vps["profile_tier_level"] = parse_profile_tier_level(
        reader, True, vps["vps_max_sub_layers_minus1"]
    )

    vps["vps_sub_layer_ordering_info_present_flag"] = reader.read_bits(1)
    start = 0 if vps["vps_sub_layer_ordering_info_present_flag"] else vps["vps_max_sub_layers_minus1"]
    vps["sub_layer_ordering"] = []
    for _ in range(start, vps["vps_max_sub_layers_minus1"] + 1):
        vps["sub_layer_ordering"].append({
            "vps_max_dec_pic_buffering_minus1": reader.read_unsigned_exp_golomb(),
            "vps_max_num_reorder_pics": reader.read_unsigned_exp_golomb(),
            "vps_max_latency_increase_plus1": reader.read_unsigned_exp_golomb(),
        })

    vps["vps_max_layer_id"] = reader.read_bits(6)
    vps["vps_num_layer_sets_minus1"] = reader.read_unsigned_exp_golomb()
    for _ in range(1, vps["vps_num_layer_sets_minus1"] + 1):
        for _ in range(vps["vps_max_layer_id"] + 1):
            reader.read_bits(1)  # layer_id_included_flag

    vps["vps_timing_info_present_flag"] = reader.read_bits(1)
    if vps["vps_timing_info_present_flag"]:
        vps["vps_num_units_in_tick"] = reader.read_bits(32)
        vps["vps_time_scale"] = reader.read_bits(32)
        vps["vps_poc_proportional_to_timing_flag"] = reader.read_bits(1)
        if vps["vps_poc_proportional_to_timing_flag"]:
            vps["vps_num_ticks_poc_diff_one_minus1"] = reader.read_unsigned_exp_golomb()

        if vps.get("vps_num_units_in_tick") and vps.get("vps_time_scale"):
            vps["derived_fps"] = vps["vps_time_scale"] / vps["vps_num_units_in_tick"]

    return vps
