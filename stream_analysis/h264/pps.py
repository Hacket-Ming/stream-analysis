"""H.264 Picture Parameter Set (PPS) parser.

Follows ITU-T H.264 Section 7.3.2.2.
"""

from stream_analysis.bitreader import BitReader


def parse_pps(reader: BitReader, sps_map: dict) -> dict:
    """Parse an H.264 PPS from RBSP data (after NAL header byte)."""
    pps = {}

    pps["pic_parameter_set_id"] = reader.read_unsigned_exp_golomb()
    pps["seq_parameter_set_id"] = reader.read_unsigned_exp_golomb()
    pps["entropy_coding_mode_flag"] = reader.read_bits(1)
    pps["entropy_coding_mode"] = "CABAC" if pps["entropy_coding_mode_flag"] else "CAVLC"
    pps["bottom_field_pic_order_in_frame_present_flag"] = reader.read_bits(1)

    pps["num_slice_groups_minus1"] = reader.read_unsigned_exp_golomb()
    if pps["num_slice_groups_minus1"] > 0:
        pps["slice_group_map_type"] = reader.read_unsigned_exp_golomb()
        if pps["slice_group_map_type"] == 0:
            pps["run_length_minus1"] = []
            for _ in range(pps["num_slice_groups_minus1"] + 1):
                pps["run_length_minus1"].append(reader.read_unsigned_exp_golomb())
        elif pps["slice_group_map_type"] == 2:
            pps["top_left"] = []
            pps["bottom_right"] = []
            for _ in range(pps["num_slice_groups_minus1"]):
                pps["top_left"].append(reader.read_unsigned_exp_golomb())
                pps["bottom_right"].append(reader.read_unsigned_exp_golomb())
        elif pps["slice_group_map_type"] in (3, 4, 5):
            pps["slice_group_change_direction_flag"] = reader.read_bits(1)
            pps["slice_group_change_rate_minus1"] = reader.read_unsigned_exp_golomb()
        elif pps["slice_group_map_type"] == 6:
            pic_size_in_map_units_minus1 = reader.read_unsigned_exp_golomb()
            pps["pic_size_in_map_units_minus1"] = pic_size_in_map_units_minus1
            pps["slice_group_id"] = []
            import math
            bits = max(1, math.ceil(math.log2(pps["num_slice_groups_minus1"] + 1)))
            for _ in range(pic_size_in_map_units_minus1 + 1):
                pps["slice_group_id"].append(reader.read_bits(bits))

    pps["num_ref_idx_l0_default_active_minus1"] = reader.read_unsigned_exp_golomb()
    pps["num_ref_idx_l1_default_active_minus1"] = reader.read_unsigned_exp_golomb()
    pps["weighted_pred_flag"] = reader.read_bits(1)
    pps["weighted_bipred_idc"] = reader.read_bits(2)
    pps["pic_init_qp_minus26"] = reader.read_signed_exp_golomb()
    pps["pic_init_qs_minus26"] = reader.read_signed_exp_golomb()
    pps["chroma_qp_index_offset"] = reader.read_signed_exp_golomb()
    pps["deblocking_filter_control_present_flag"] = reader.read_bits(1)
    pps["constrained_intra_pred_flag"] = reader.read_bits(1)
    pps["redundant_pic_cnt_present_flag"] = reader.read_bits(1)

    # Extended fields present in some profiles
    if reader.more_rbsp_data():
        pps["transform_8x8_mode_flag"] = reader.read_bits(1)
        pps["pic_scaling_matrix_present_flag"] = reader.read_bits(1)
        if pps["pic_scaling_matrix_present_flag"]:
            num_lists = 6 + 2 * pps.get("transform_8x8_mode_flag", 0)
            sps = sps_map.get(pps["seq_parameter_set_id"])
            if sps and sps.get("chroma_format_idc") == 3:
                num_lists = 6 + 6 * pps.get("transform_8x8_mode_flag", 0)
            pps["scaling_lists"] = []
            for i in range(num_lists):
                present = reader.read_bits(1)
                if present:
                    size = 16 if i < 6 else 64
                    pps["scaling_lists"].append(_parse_scaling_list(reader, size))
                else:
                    pps["scaling_lists"].append(None)
        pps["second_chroma_qp_index_offset"] = reader.read_signed_exp_golomb()

    return pps


def _parse_scaling_list(reader: BitReader, size: int) -> list[int]:
    """Parse a scaling list (same algorithm as SPS)."""
    scaling_list = [0] * size
    last_scale = 8
    next_scale = 8
    for j in range(size):
        if next_scale != 0:
            delta_scale = reader.read_signed_exp_golomb()
            next_scale = (last_scale + delta_scale + 256) % 256
        scaling_list[j] = last_scale if next_scale == 0 else next_scale
        last_scale = scaling_list[j]
    return scaling_list
