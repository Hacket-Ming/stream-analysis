"""H.266 Picture Parameter Set (PPS) parser.

Follows ITU-T H.266 Section 7.3.2.4.
"""

import math
from stream_analysis.bitreader import BitReader


def parse_pps(reader: BitReader, sps_map: dict) -> dict:
    """Parse an H.266 PPS from RBSP data (after 2-byte NAL header)."""
    pps = {}

    pps["pps_pic_parameter_set_id"] = reader.read_bits(6)
    pps["pps_seq_parameter_set_id"] = reader.read_bits(4)
    pps["pps_mixed_nalu_types_in_pic_flag"] = reader.read_bits(1)

    # Per-picture resolution (RPR - Reference Picture Resampling)
    pps["pps_pic_width_in_luma_samples"] = reader.read_unsigned_exp_golomb()
    pps["pps_pic_height_in_luma_samples"] = reader.read_unsigned_exp_golomb()

    # Get SPS for context
    sps = sps_map.get(pps["pps_seq_parameter_set_id"], {})
    sps_width = sps.get("sps_pic_width_max_in_luma_samples", pps["pps_pic_width_in_luma_samples"])
    sps_height = sps.get("sps_pic_height_max_in_luma_samples", pps["pps_pic_height_in_luma_samples"])

    pps["pps_conformance_window_flag"] = reader.read_bits(1)
    if pps["pps_conformance_window_flag"]:
        pps["pps_conf_win_left_offset"] = reader.read_unsigned_exp_golomb()
        pps["pps_conf_win_right_offset"] = reader.read_unsigned_exp_golomb()
        pps["pps_conf_win_top_offset"] = reader.read_unsigned_exp_golomb()
        pps["pps_conf_win_bottom_offset"] = reader.read_unsigned_exp_golomb()

    pps["pps_scaling_window_explicit_signalling_flag"] = reader.read_bits(1)
    if pps["pps_scaling_window_explicit_signalling_flag"]:
        pps["pps_scaling_win_left_offset"] = reader.read_signed_exp_golomb()
        pps["pps_scaling_win_right_offset"] = reader.read_signed_exp_golomb()
        pps["pps_scaling_win_top_offset"] = reader.read_signed_exp_golomb()
        pps["pps_scaling_win_bottom_offset"] = reader.read_signed_exp_golomb()

    pps["pps_output_flag_present_flag"] = reader.read_bits(1)
    pps["pps_no_pic_partition_flag"] = reader.read_bits(1)
    pps["pps_subpic_id_mapping_present_flag"] = reader.read_bits(1)

    if pps["pps_subpic_id_mapping_present_flag"]:
        if not pps["pps_no_pic_partition_flag"]:
            pps["pps_num_subpics_minus1"] = reader.read_unsigned_exp_golomb()
        else:
            pps["pps_num_subpics_minus1"] = 0
        pps["pps_subpic_id_len_minus1"] = reader.read_unsigned_exp_golomb()
        id_bits = pps["pps_subpic_id_len_minus1"] + 1
        pps["pps_subpic_id"] = []
        for _ in range(pps.get("pps_num_subpics_minus1", 0) + 1):
            pps["pps_subpic_id"].append(reader.read_bits(id_bits))

    if not pps["pps_no_pic_partition_flag"]:
        _parse_pic_partition(reader, pps, sps)
    else:
        pps["derived_num_tiles_in_pic"] = 1
        pps["derived_num_slices_in_pic"] = 1

    pps["pps_cabac_init_present_flag"] = reader.read_bits(1)

    pps["pps_num_ref_idx_default_active_minus1"] = [0, 0]
    for i in range(2):
        pps["pps_num_ref_idx_default_active_minus1"][i] = reader.read_unsigned_exp_golomb()

    pps["pps_rpl1_idx_present_flag"] = reader.read_bits(1)
    pps["pps_weighted_pred_flag"] = reader.read_bits(1)
    pps["pps_weighted_bipred_flag"] = reader.read_bits(1)
    pps["pps_ref_wraparound_enabled_flag"] = reader.read_bits(1)

    if pps["pps_ref_wraparound_enabled_flag"]:
        pps["pps_pic_width_minus_wraparound_offset"] = reader.read_unsigned_exp_golomb()

    pps["pps_init_qp_minus26"] = reader.read_signed_exp_golomb()
    pps["pps_cu_qp_delta_enabled_flag"] = reader.read_bits(1)

    pps["pps_chroma_tool_offsets_present_flag"] = reader.read_bits(1)
    if pps["pps_chroma_tool_offsets_present_flag"]:
        pps["pps_cb_qp_offset"] = reader.read_signed_exp_golomb()
        pps["pps_cr_qp_offset"] = reader.read_signed_exp_golomb()
        pps["pps_joint_cbcr_qp_offset_present_flag"] = reader.read_bits(1)
        if pps["pps_joint_cbcr_qp_offset_present_flag"]:
            pps["pps_joint_cbcr_qp_offset_value"] = reader.read_signed_exp_golomb()
        pps["pps_slice_chroma_qp_offsets_present_flag"] = reader.read_bits(1)
        pps["pps_cu_chroma_qp_offset_list_enabled_flag"] = reader.read_bits(1)
        if pps["pps_cu_chroma_qp_offset_list_enabled_flag"]:
            pps["pps_chroma_qp_offset_list_len_minus1"] = reader.read_unsigned_exp_golomb()
            pps["chroma_qp_offset_list"] = []
            for _ in range(pps["pps_chroma_qp_offset_list_len_minus1"] + 1):
                pps["chroma_qp_offset_list"].append({
                    "pps_cb_qp_offset_list": reader.read_signed_exp_golomb(),
                    "pps_cr_qp_offset_list": reader.read_signed_exp_golomb(),
                    "pps_joint_cbcr_qp_offset_list": reader.read_signed_exp_golomb() if pps.get("pps_joint_cbcr_qp_offset_present_flag") else 0,
                })

    pps["pps_deblocking_filter_control_present_flag"] = reader.read_bits(1)
    if pps["pps_deblocking_filter_control_present_flag"]:
        pps["pps_deblocking_filter_override_enabled_flag"] = reader.read_bits(1)
        pps["pps_deblocking_filter_disabled_flag"] = reader.read_bits(1)
        if not pps["pps_deblocking_filter_disabled_flag"]:
            pps["pps_luma_beta_offset_div2"] = reader.read_signed_exp_golomb()
            pps["pps_luma_tc_offset_div2"] = reader.read_signed_exp_golomb()
            if pps.get("pps_chroma_tool_offsets_present_flag"):
                pps["pps_cb_beta_offset_div2"] = reader.read_signed_exp_golomb()
                pps["pps_cb_tc_offset_div2"] = reader.read_signed_exp_golomb()
                pps["pps_cr_beta_offset_div2"] = reader.read_signed_exp_golomb()
                pps["pps_cr_tc_offset_div2"] = reader.read_signed_exp_golomb()

    # PH/SH field allocation flags
    pps["pps_rpl_info_in_ph_flag"] = reader.read_bits(1)
    pps["pps_sao_info_in_ph_flag"] = reader.read_bits(1)
    pps["pps_alf_info_in_ph_flag"] = reader.read_bits(1)

    if pps.get("pps_weighted_pred_flag") or pps.get("pps_weighted_bipred_flag"):
        pps["pps_wp_info_in_ph_flag"] = reader.read_bits(1)

    pps["pps_qp_delta_info_in_ph_flag"] = reader.read_bits(1)

    pps["pps_picture_header_extension_present_flag"] = reader.read_bits(1)
    pps["pps_slice_header_extension_present_flag"] = reader.read_bits(1)

    pps["pps_extension_flag"] = reader.read_bits(1)

    return pps


def _parse_pic_partition(reader: BitReader, pps: dict, sps: dict) -> None:
    """Parse picture partitioning (tile and slice) configuration."""
    ctb_log2 = sps.get("sps_log2_ctu_size_minus5", 0) + 5
    ctb_size = 1 << ctb_log2

    pic_w = pps["pps_pic_width_in_luma_samples"]
    pic_h = pps["pps_pic_height_in_luma_samples"]
    pic_w_ctb = math.ceil(pic_w / ctb_size)
    pic_h_ctb = math.ceil(pic_h / ctb_size)

    pps["pps_log2_ctu_size_minus5"] = reader.read_bits(2)

    # Tile columns
    pps["pps_num_exp_tile_columns_minus1"] = reader.read_unsigned_exp_golomb()
    pps["pps_num_exp_tile_rows_minus1"] = reader.read_unsigned_exp_golomb()

    # Explicit tile column widths
    pps["pps_tile_column_width_minus1"] = []
    remaining_w = pic_w_ctb
    for _ in range(pps["pps_num_exp_tile_columns_minus1"] + 1):
        w = reader.read_unsigned_exp_golomb()
        pps["pps_tile_column_width_minus1"].append(w)
        remaining_w -= (w + 1)

    # Explicit tile row heights
    pps["pps_tile_row_height_minus1"] = []
    remaining_h = pic_h_ctb
    for _ in range(pps["pps_num_exp_tile_rows_minus1"] + 1):
        h = reader.read_unsigned_exp_golomb()
        pps["pps_tile_row_height_minus1"].append(h)
        remaining_h -= (h + 1)

    # Derive total number of tile columns and rows
    num_tile_cols = pps["pps_num_exp_tile_columns_minus1"] + 1
    if remaining_w > 0:
        last_w = pps["pps_tile_column_width_minus1"][-1] + 1 if pps["pps_tile_column_width_minus1"] else pic_w_ctb
        num_tile_cols += math.ceil(remaining_w / last_w) if last_w > 0 else 0

    num_tile_rows = pps["pps_num_exp_tile_rows_minus1"] + 1
    if remaining_h > 0:
        last_h = pps["pps_tile_row_height_minus1"][-1] + 1 if pps["pps_tile_row_height_minus1"] else pic_h_ctb
        num_tile_rows += math.ceil(remaining_h / last_h) if last_h > 0 else 0

    num_tiles = num_tile_cols * num_tile_rows
    pps["derived_num_tile_columns"] = num_tile_cols
    pps["derived_num_tile_rows"] = num_tile_rows
    pps["derived_num_tiles_in_pic"] = num_tiles

    if num_tiles > 1:
        pps["pps_loop_filter_across_tiles_enabled_flag"] = reader.read_bits(1)
        pps["pps_rect_slice_flag"] = reader.read_bits(1)
    else:
        pps["pps_rect_slice_flag"] = 1

    if pps.get("pps_rect_slice_flag"):
        if num_tiles > 1:
            pps["pps_single_slice_per_subpic_flag"] = reader.read_bits(1)
        else:
            pps["pps_single_slice_per_subpic_flag"] = 1

        if not pps.get("pps_single_slice_per_subpic_flag", 1):
            pps["pps_num_slices_in_pic_minus1"] = reader.read_unsigned_exp_golomb()
            num_slices = pps["pps_num_slices_in_pic_minus1"] + 1
            pps["derived_num_slices_in_pic"] = num_slices

            # Skip detailed slice-to-tile mapping for now (very complex)
            tile_idx_bits = max(1, math.ceil(math.log2(num_tiles))) if num_tiles > 1 else 0
            for i in range(num_slices - 1):
                if tile_idx_bits > 0:
                    if num_tile_cols > 1:
                        reader.read_bits(tile_idx_bits)  # pps_tile_idx_delta_val or width
                    if num_tile_rows > 1:
                        reader.read_bits(tile_idx_bits)  # pps_tile_idx_delta_val or height
        else:
            pps["derived_num_slices_in_pic"] = sps.get("sps_num_subpics_minus1", 0) + 1
    else:
        # Raster scan slices
        pps["derived_num_slices_in_pic"] = num_tiles

    pps["pps_loop_filter_across_slices_enabled_flag"] = reader.read_bits(1)
