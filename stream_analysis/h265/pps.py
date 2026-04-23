"""H.265 Picture Parameter Set (PPS) parser.

Follows ITU-T H.265 Section 7.3.2.3.
"""

import math
from stream_analysis.bitreader import BitReader


def parse_pps(reader: BitReader, sps_map: dict) -> dict:
    """Parse an H.265 PPS from RBSP data (after 2-byte NAL header)."""
    pps = {}

    pps["pps_pic_parameter_set_id"] = reader.read_unsigned_exp_golomb()
    pps["pps_seq_parameter_set_id"] = reader.read_unsigned_exp_golomb()
    pps["dependent_slice_segments_enabled_flag"] = reader.read_bits(1)
    pps["output_flag_present_flag"] = reader.read_bits(1)
    pps["num_extra_slice_header_bits"] = reader.read_bits(3)
    pps["sign_data_hiding_enabled_flag"] = reader.read_bits(1)
    pps["cabac_init_present_flag"] = reader.read_bits(1)

    pps["num_ref_idx_l0_default_active_minus1"] = reader.read_unsigned_exp_golomb()
    pps["num_ref_idx_l1_default_active_minus1"] = reader.read_unsigned_exp_golomb()
    pps["init_qp_minus26"] = reader.read_signed_exp_golomb()
    pps["constrained_intra_pred_flag"] = reader.read_bits(1)
    pps["transform_skip_enabled_flag"] = reader.read_bits(1)

    pps["cu_qp_delta_enabled_flag"] = reader.read_bits(1)
    if pps["cu_qp_delta_enabled_flag"]:
        pps["diff_cu_qp_delta_depth"] = reader.read_unsigned_exp_golomb()

    pps["pps_cb_qp_offset"] = reader.read_signed_exp_golomb()
    pps["pps_cr_qp_offset"] = reader.read_signed_exp_golomb()
    pps["pps_slice_chroma_qp_offsets_present_flag"] = reader.read_bits(1)
    pps["weighted_pred_flag"] = reader.read_bits(1)
    pps["weighted_bipred_flag"] = reader.read_bits(1)
    pps["transquant_bypass_enabled_flag"] = reader.read_bits(1)

    pps["tiles_enabled_flag"] = reader.read_bits(1)
    pps["entropy_coding_sync_enabled_flag"] = reader.read_bits(1)

    if pps["tiles_enabled_flag"]:
        pps["num_tile_columns_minus1"] = reader.read_unsigned_exp_golomb()
        pps["num_tile_rows_minus1"] = reader.read_unsigned_exp_golomb()
        pps["uniform_spacing_flag"] = reader.read_bits(1)
        if not pps["uniform_spacing_flag"]:
            pps["column_width_minus1"] = []
            for _ in range(pps["num_tile_columns_minus1"]):
                pps["column_width_minus1"].append(reader.read_unsigned_exp_golomb())
            pps["row_height_minus1"] = []
            for _ in range(pps["num_tile_rows_minus1"]):
                pps["row_height_minus1"].append(reader.read_unsigned_exp_golomb())
        pps["loop_filter_across_tiles_enabled_flag"] = reader.read_bits(1)

    pps["pps_loop_filter_across_slices_enabled_flag"] = reader.read_bits(1)

    pps["deblocking_filter_control_present_flag"] = reader.read_bits(1)
    if pps["deblocking_filter_control_present_flag"]:
        pps["deblocking_filter_override_enabled_flag"] = reader.read_bits(1)
        pps["pps_deblocking_filter_disabled_flag"] = reader.read_bits(1)
        if not pps["pps_deblocking_filter_disabled_flag"]:
            pps["pps_beta_offset_div2"] = reader.read_signed_exp_golomb()
            pps["pps_tc_offset_div2"] = reader.read_signed_exp_golomb()

    pps["pps_scaling_list_data_present_flag"] = reader.read_bits(1)
    if pps["pps_scaling_list_data_present_flag"]:
        # Skip scaling list data parsing for brevity
        from stream_analysis.h265.sps import _parse_scaling_list_data
        pps["scaling_list_data"] = _parse_scaling_list_data(reader)

    pps["lists_modification_present_flag"] = reader.read_bits(1)
    pps["log2_parallel_merge_level_minus2"] = reader.read_unsigned_exp_golomb()
    pps["slice_segment_header_extension_present_flag"] = reader.read_bits(1)

    return pps
