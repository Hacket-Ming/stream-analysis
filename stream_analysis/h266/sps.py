"""H.266 Sequence Parameter Set (SPS) parser.

Follows ITU-T H.266 Section 7.3.2.3.
"""

import math
from stream_analysis.bitreader import BitReader
from stream_analysis.h266.profile_tier_level import parse_profile_tier_level


def parse_sps(reader: BitReader) -> dict:
    """Parse an H.266 SPS from RBSP data (after 2-byte NAL header)."""
    sps = {}

    sps["sps_seq_parameter_set_id"] = reader.read_bits(4)
    sps["sps_video_parameter_set_id"] = reader.read_bits(4)
    sps["sps_max_sublayers_minus1"] = reader.read_bits(3)
    sps["sps_chroma_format_idc"] = reader.read_bits(2)
    sps["sps_log2_ctu_size_minus5"] = reader.read_bits(2)

    ctb_log2_size_y = sps["sps_log2_ctu_size_minus5"] + 5
    ctb_size_y = 1 << ctb_log2_size_y
    sps["derived_ctb_size_y"] = ctb_size_y

    sps["sps_ptl_dpb_hrd_params_present_flag"] = reader.read_bits(1)
    if sps["sps_ptl_dpb_hrd_params_present_flag"]:
        sps["profile_tier_level"] = parse_profile_tier_level(
            reader, True, sps["sps_max_sublayers_minus1"]
        )

    sps["sps_gdr_enabled_flag"] = reader.read_bits(1)
    sps["sps_ref_pic_resampling_enabled_flag"] = reader.read_bits(1)

    if sps["sps_ref_pic_resampling_enabled_flag"]:
        sps["sps_res_change_in_clvs_allowed_flag"] = reader.read_bits(1)

    sps["sps_pic_width_max_in_luma_samples"] = reader.read_unsigned_exp_golomb()
    sps["sps_pic_height_max_in_luma_samples"] = reader.read_unsigned_exp_golomb()

    sps["sps_conformance_window_flag"] = reader.read_bits(1)
    if sps["sps_conformance_window_flag"]:
        sps["sps_conf_win_left_offset"] = reader.read_unsigned_exp_golomb()
        sps["sps_conf_win_right_offset"] = reader.read_unsigned_exp_golomb()
        sps["sps_conf_win_top_offset"] = reader.read_unsigned_exp_golomb()
        sps["sps_conf_win_bottom_offset"] = reader.read_unsigned_exp_golomb()

    # Subpicture info
    sps["sps_subpic_info_present_flag"] = reader.read_bits(1)
    if sps["sps_subpic_info_present_flag"]:
        _parse_subpic_info(reader, sps, ctb_size_y)

    # Bit depth (unified in H.266 - single value for both luma and chroma)
    sps["sps_bitdepth_minus8"] = reader.read_unsigned_exp_golomb()
    sps["derived_bit_depth"] = sps["sps_bitdepth_minus8"] + 8

    # Entropy coding
    sps["sps_entropy_coding_sync_enabled_flag"] = reader.read_bits(1)
    sps["sps_entry_point_offsets_present_flag"] = reader.read_bits(1)

    # POC
    sps["sps_log2_max_pic_order_cnt_lsb_minus4"] = reader.read_bits(4)
    sps["sps_poc_msb_cycle_flag"] = reader.read_bits(1)
    if sps["sps_poc_msb_cycle_flag"]:
        sps["sps_poc_msb_cycle_len_minus1"] = reader.read_unsigned_exp_golomb()

    # Extra PH bits
    sps["sps_num_extra_ph_bytes"] = reader.read_bits(2)
    if sps["sps_num_extra_ph_bytes"] > 0:
        sps["sps_extra_ph_bit_present_flag"] = []
        for _ in range(sps["sps_num_extra_ph_bytes"] * 8):
            sps["sps_extra_ph_bit_present_flag"].append(reader.read_bits(1))

    sps["sps_num_extra_sh_bytes"] = reader.read_bits(2)
    if sps["sps_num_extra_sh_bytes"] > 0:
        sps["sps_extra_sh_bit_present_flag"] = []
        for _ in range(sps["sps_num_extra_sh_bytes"] * 8):
            sps["sps_extra_sh_bit_present_flag"].append(reader.read_bits(1))

    # Sub-layer DPB parameters
    if sps["sps_ptl_dpb_hrd_params_present_flag"]:
        if sps["sps_max_sublayers_minus1"] > 0:
            sps["sps_sublayer_dpb_params_flag"] = reader.read_bits(1)
        else:
            sps["sps_sublayer_dpb_params_flag"] = 0

        start = 0 if sps.get("sps_sublayer_dpb_params_flag", 0) else sps["sps_max_sublayers_minus1"]
        sps["dpb_params"] = []
        for _ in range(start, sps["sps_max_sublayers_minus1"] + 1):
            sps["dpb_params"].append({
                "sps_max_dec_pic_buffering_minus1": reader.read_unsigned_exp_golomb(),
                "sps_max_num_reorder_pics": reader.read_unsigned_exp_golomb(),
                "sps_max_latency_increase_plus1": reader.read_unsigned_exp_golomb(),
            })

    # CTU size constraints
    sps["sps_log2_min_luma_coding_block_size_minus2"] = reader.read_unsigned_exp_golomb()
    sps["sps_partition_constraints_override_enabled_flag"] = reader.read_bits(1)
    sps["sps_log2_diff_min_qt_min_cb_intra_slice_luma"] = reader.read_unsigned_exp_golomb()
    sps["sps_max_mtt_hierarchy_depth_intra_slice_luma"] = reader.read_unsigned_exp_golomb()
    if sps["sps_max_mtt_hierarchy_depth_intra_slice_luma"] != 0:
        sps["sps_log2_diff_max_bt_min_qt_intra_slice_luma"] = reader.read_unsigned_exp_golomb()
        sps["sps_log2_diff_max_tt_min_qt_intra_slice_luma"] = reader.read_unsigned_exp_golomb()

    if sps["sps_chroma_format_idc"] != 0:
        sps["sps_qtbtt_dual_tree_intra_flag"] = reader.read_bits(1)
    else:
        sps["sps_qtbtt_dual_tree_intra_flag"] = 0

    if sps.get("sps_qtbtt_dual_tree_intra_flag"):
        sps["sps_log2_diff_min_qt_min_cb_intra_slice_chroma"] = reader.read_unsigned_exp_golomb()
        sps["sps_max_mtt_hierarchy_depth_intra_slice_chroma"] = reader.read_unsigned_exp_golomb()
        if sps["sps_max_mtt_hierarchy_depth_intra_slice_chroma"] != 0:
            sps["sps_log2_diff_max_bt_min_qt_intra_slice_chroma"] = reader.read_unsigned_exp_golomb()
            sps["sps_log2_diff_max_tt_min_qt_intra_slice_chroma"] = reader.read_unsigned_exp_golomb()

    sps["sps_log2_diff_min_qt_min_cb_inter_slice"] = reader.read_unsigned_exp_golomb()
    sps["sps_max_mtt_hierarchy_depth_inter_slice"] = reader.read_unsigned_exp_golomb()
    if sps["sps_max_mtt_hierarchy_depth_inter_slice"] != 0:
        sps["sps_log2_diff_max_bt_min_qt_inter_slice"] = reader.read_unsigned_exp_golomb()
        sps["sps_log2_diff_max_tt_min_qt_inter_slice"] = reader.read_unsigned_exp_golomb()

    # Max luma transform size
    if ctb_size_y > 32:
        sps["sps_max_luma_transform_size_64_flag"] = reader.read_bits(1)

    # Coding tool flags
    sps["sps_transform_skip_enabled_flag"] = reader.read_bits(1)
    if sps["sps_transform_skip_enabled_flag"]:
        sps["sps_log2_transform_skip_max_size_minus2"] = reader.read_unsigned_exp_golomb()
        sps["sps_bdpcm_enabled_flag"] = reader.read_bits(1)

    sps["sps_mts_enabled_flag"] = reader.read_bits(1)
    if sps["sps_mts_enabled_flag"]:
        sps["sps_explicit_mts_intra_enabled_flag"] = reader.read_bits(1)
        sps["sps_explicit_mts_inter_enabled_flag"] = reader.read_bits(1)

    sps["sps_lfnst_enabled_flag"] = reader.read_bits(1)

    if sps["sps_chroma_format_idc"] != 0:
        sps["sps_joint_cbcr_enabled_flag"] = reader.read_bits(1)
        sps["sps_same_qp_table_for_chroma_flag"] = reader.read_bits(1)

        num_qp_tables = 1 if sps.get("sps_same_qp_table_for_chroma_flag", 1) else (3 if sps.get("sps_joint_cbcr_enabled_flag") else 2)
        sps["chroma_qp_tables"] = []
        for i in range(num_qp_tables):
            table = {}
            table["sps_qp_table_start_minus26"] = reader.read_signed_exp_golomb()
            table["sps_num_points_in_qp_table_minus1"] = reader.read_unsigned_exp_golomb()
            table["points"] = []
            for j in range(table["sps_num_points_in_qp_table_minus1"] + 1):
                table["points"].append({
                    "sps_delta_qp_in_val_minus1": reader.read_unsigned_exp_golomb(),
                    "sps_delta_qp_diff_val": reader.read_unsigned_exp_golomb(),
                })
            sps["chroma_qp_tables"].append(table)

    sps["sps_sao_enabled_flag"] = reader.read_bits(1)
    sps["sps_alf_enabled_flag"] = reader.read_bits(1)
    if sps["sps_alf_enabled_flag"] and sps["sps_chroma_format_idc"] != 0:
        sps["sps_ccalf_enabled_flag"] = reader.read_bits(1)

    sps["sps_lmcs_enabled_flag"] = reader.read_bits(1)
    sps["sps_weighted_pred_flag"] = reader.read_bits(1)
    sps["sps_weighted_bipred_flag"] = reader.read_bits(1)
    sps["sps_long_term_ref_pics_flag"] = reader.read_bits(1)

    if sps["sps_video_parameter_set_id"] > 0:
        sps["sps_inter_layer_prediction_enabled_flag"] = reader.read_bits(1)

    sps["sps_idr_rpl_present_flag"] = reader.read_bits(1)

    # RPL (Reference Picture List) - replaces H.265's short_term_ref_pic_set
    sps["sps_rpl1_same_as_rpl0_flag"] = reader.read_bits(1)
    num_rpl_lists = 1 if sps["sps_rpl1_same_as_rpl0_flag"] else 2

    sps["ref_pic_lists"] = []
    for list_idx in range(num_rpl_lists):
        sps_num_ref_pic_lists = reader.read_unsigned_exp_golomb()
        rpl_list = {"sps_num_ref_pic_lists": sps_num_ref_pic_lists, "rpls": []}
        for rpl_idx in range(sps_num_ref_pic_lists):
            rpl = _parse_ref_pic_list_struct(reader, list_idx, rpl_idx, sps)
            rpl_list["rpls"].append(rpl)
        sps["ref_pic_lists"].append(rpl_list)

    if sps["sps_rpl1_same_as_rpl0_flag"]:
        sps["ref_pic_lists"].append(sps["ref_pic_lists"][0])

    # Wrap-around
    sps["sps_ref_wraparound_enabled_flag"] = reader.read_bits(1)

    # Temporal MVP
    sps["sps_temporal_mvp_enabled_flag"] = reader.read_bits(1)
    if sps["sps_temporal_mvp_enabled_flag"]:
        sps["sps_sbtmvp_enabled_flag"] = reader.read_bits(1)

    # AMVR
    sps["sps_amvr_enabled_flag"] = reader.read_bits(1)

    # BDOF
    sps["sps_bdof_enabled_flag"] = reader.read_bits(1)
    if sps["sps_bdof_enabled_flag"]:
        sps["sps_bdof_control_present_in_ph_flag"] = reader.read_bits(1)

    # SMVD
    sps["sps_smvd_enabled_flag"] = reader.read_bits(1)

    # DMVR
    sps["sps_dmvr_enabled_flag"] = reader.read_bits(1)
    if sps["sps_dmvr_enabled_flag"]:
        sps["sps_dmvr_control_present_in_ph_flag"] = reader.read_bits(1)

    # MMVD
    sps["sps_mmvd_enabled_flag"] = reader.read_bits(1)
    if sps["sps_mmvd_enabled_flag"]:
        sps["sps_mmvd_fullpel_only_enabled_flag"] = reader.read_bits(1)

    # Max number of merge candidates
    sps["sps_six_minus_max_num_merge_cand"] = reader.read_unsigned_exp_golomb()
    max_num_merge_cand = 6 - sps["sps_six_minus_max_num_merge_cand"]

    sps["sps_sbt_enabled_flag"] = reader.read_bits(1)

    # Affine
    sps["sps_affine_enabled_flag"] = reader.read_bits(1)
    if sps["sps_affine_enabled_flag"]:
        sps["sps_five_minus_max_num_subblock_merge_cand"] = reader.read_unsigned_exp_golomb()
        sps["sps_6param_affine_enabled_flag"] = reader.read_bits(1)
        if sps["sps_amvr_enabled_flag"]:
            sps["sps_affine_amvr_enabled_flag"] = reader.read_bits(1)
        sps["sps_affine_prof_enabled_flag"] = reader.read_bits(1)
        if sps["sps_affine_prof_enabled_flag"]:
            sps["sps_prof_control_present_in_ph_flag"] = reader.read_bits(1)

    # BCW
    sps["sps_bcw_enabled_flag"] = reader.read_bits(1)

    # CIIP
    sps["sps_ciip_enabled_flag"] = reader.read_bits(1)

    # GPM
    if max_num_merge_cand >= 2:
        sps["sps_gpm_enabled_flag"] = reader.read_bits(1)
        if sps["sps_gpm_enabled_flag"] and max_num_merge_cand >= 3:
            sps["sps_max_num_merge_cand_minus_max_num_gpm_cand"] = reader.read_unsigned_exp_golomb()

    # LTRP
    sps["sps_log2_parallel_merge_level_minus2"] = reader.read_unsigned_exp_golomb()

    sps["sps_isp_enabled_flag"] = reader.read_bits(1)
    sps["sps_mrl_enabled_flag"] = reader.read_bits(1)
    sps["sps_mip_enabled_flag"] = reader.read_bits(1)

    if sps["sps_chroma_format_idc"] != 0:
        sps["sps_cclm_enabled_flag"] = reader.read_bits(1)

    if sps["sps_chroma_format_idc"] == 1:
        sps["sps_chroma_horizontal_collocated_flag"] = reader.read_bits(1)
        sps["sps_chroma_vertical_collocated_flag"] = reader.read_bits(1)

    sps["sps_palette_enabled_flag"] = reader.read_bits(1)

    if sps["sps_chroma_format_idc"] == 3 and not sps.get("sps_max_luma_transform_size_64_flag", 0):
        sps["sps_act_enabled_flag"] = reader.read_bits(1)

    if sps["sps_transform_skip_enabled_flag"] or sps.get("sps_palette_enabled_flag"):
        sps["sps_min_qp_prime_ts_minus4"] = reader.read_unsigned_exp_golomb()

    sps["sps_ibc_enabled_flag"] = reader.read_bits(1)
    if sps["sps_ibc_enabled_flag"]:
        sps["sps_six_minus_max_num_ibc_merge_cand"] = reader.read_unsigned_exp_golomb()

    # LADF
    sps["sps_ladf_enabled_flag"] = reader.read_bits(1)
    if sps["sps_ladf_enabled_flag"]:
        sps["sps_num_ladf_intervals_minus2"] = reader.read_bits(2)
        sps["sps_ladf_lowest_interval_qp_offset"] = reader.read_signed_exp_golomb()
        sps["sps_ladf_intervals"] = []
        for _ in range(sps["sps_num_ladf_intervals_minus2"] + 1):
            sps["sps_ladf_intervals"].append({
                "sps_ladf_qp_offset": reader.read_signed_exp_golomb(),
                "sps_ladf_delta_threshold_minus1": reader.read_unsigned_exp_golomb(),
            })

    # Explicit scaling list
    sps["sps_explicit_scaling_list_enabled_flag"] = reader.read_bits(1)

    if sps["sps_alf_enabled_flag"] and sps.get("sps_explicit_scaling_list_enabled_flag"):
        sps["sps_scaling_matrix_for_lfnst_disabled_flag"] = reader.read_bits(1)

    sps["sps_scaling_matrix_for_alternative_colour_space_disabled_flag"] = reader.read_bits(1)
    if sps["sps_scaling_matrix_for_alternative_colour_space_disabled_flag"]:
        sps["sps_scaling_matrix_designated_colour_space_flag"] = reader.read_bits(1)

    sps["sps_dep_quant_enabled_flag"] = reader.read_bits(1)
    sps["sps_sign_data_hiding_enabled_flag"] = reader.read_bits(1)

    sps["sps_virtual_boundaries_enabled_flag"] = reader.read_bits(1)
    if sps["sps_virtual_boundaries_enabled_flag"]:
        sps["sps_virtual_boundaries_present_flag"] = reader.read_bits(1)
        if sps["sps_virtual_boundaries_present_flag"]:
            sps["sps_num_ver_virtual_boundaries"] = reader.read_unsigned_exp_golomb()
            sps["virtual_boundary_pos_x"] = []
            for _ in range(sps["sps_num_ver_virtual_boundaries"]):
                sps["virtual_boundary_pos_x"].append(reader.read_unsigned_exp_golomb())
            sps["sps_num_hor_virtual_boundaries"] = reader.read_unsigned_exp_golomb()
            sps["virtual_boundary_pos_y"] = []
            for _ in range(sps["sps_num_hor_virtual_boundaries"]):
                sps["virtual_boundary_pos_y"].append(reader.read_unsigned_exp_golomb())

    # VUI
    if sps["sps_ptl_dpb_hrd_params_present_flag"]:
        sps["sps_timing_hrd_params_present_flag"] = reader.read_bits(1)
        if sps["sps_timing_hrd_params_present_flag"]:
            sps["general_timing_hrd_parameters"] = _parse_general_timing_hrd(reader)
            if sps["sps_max_sublayers_minus1"] > 0:
                sps["sps_sublayer_cpb_params_present_flag"] = reader.read_bits(1)
            else:
                sps["sps_sublayer_cpb_params_present_flag"] = 0

    sps["sps_field_seq_flag"] = reader.read_bits(1)

    sps["sps_vui_parameters_present_flag"] = reader.read_bits(1)
    if sps["sps_vui_parameters_present_flag"]:
        sps["sps_vui_payload_size_minus1"] = reader.read_unsigned_exp_golomb()
        # Byte alignment
        if not reader.byte_aligned():
            while not reader.byte_aligned():
                reader.read_bits(1)
        sps["vui"] = _parse_vui_parameters(reader)

    # SPS extension
    sps["sps_extension_flag"] = reader.read_bits(1)

    # Derive resolution
    _derive_resolution(sps)

    return sps


def _parse_subpic_info(reader: BitReader, sps: dict, ctb_size_y: int) -> None:
    """Parse subpicture information in SPS."""
    sps["sps_num_subpics_minus1"] = reader.read_unsigned_exp_golomb()

    if sps["sps_num_subpics_minus1"] > 0:
        sps["sps_independent_subpics_flag"] = reader.read_bits(1)
        sps["sps_subpic_same_size_flag"] = reader.read_bits(1)

    pic_w_ctb = math.ceil(sps["sps_pic_width_max_in_luma_samples"] / ctb_size_y)
    pic_h_ctb = math.ceil(sps["sps_pic_height_max_in_luma_samples"] / ctb_size_y)

    sps["subpics"] = []
    for i in range(sps["sps_num_subpics_minus1"] + 1):
        subpic = {}
        if i > 0 and sps.get("sps_subpic_same_size_flag", 0) == 0:
            if pic_w_ctb > 1:
                bits_w = math.ceil(math.log2(pic_w_ctb))
                subpic["sps_subpic_ctu_top_left_x"] = reader.read_bits(bits_w)
            if pic_h_ctb > 1:
                bits_h = math.ceil(math.log2(pic_h_ctb))
                subpic["sps_subpic_ctu_top_left_y"] = reader.read_bits(bits_h)

        if i < sps["sps_num_subpics_minus1"] and sps.get("sps_subpic_same_size_flag", 0) == 0:
            if pic_w_ctb > 1:
                bits_w = math.ceil(math.log2(pic_w_ctb))
                subpic["sps_subpic_width_minus1"] = reader.read_bits(bits_w)
            if pic_h_ctb > 1:
                bits_h = math.ceil(math.log2(pic_h_ctb))
                subpic["sps_subpic_height_minus1"] = reader.read_bits(bits_h)

        if not sps.get("sps_independent_subpics_flag", 1):
            subpic["sps_subpic_treated_as_pic_flag"] = reader.read_bits(1)
            subpic["sps_loop_filter_across_subpic_enabled_flag"] = reader.read_bits(1)

        sps["subpics"].append(subpic)

    sps["sps_subpic_id_len_minus1"] = reader.read_unsigned_exp_golomb()
    sps["sps_subpic_id_mapping_explicitly_signalled_flag"] = reader.read_bits(1)
    if sps["sps_subpic_id_mapping_explicitly_signalled_flag"]:
        sps["sps_subpic_id_mapping_present_flag"] = reader.read_bits(1)
        if sps["sps_subpic_id_mapping_present_flag"]:
            sps["sps_subpic_id"] = []
            id_bits = sps["sps_subpic_id_len_minus1"] + 1
            for _ in range(sps["sps_num_subpics_minus1"] + 1):
                sps["sps_subpic_id"].append(reader.read_bits(id_bits))


def _parse_ref_pic_list_struct(reader: BitReader, list_idx: int, rpl_idx: int,
                                sps: dict) -> dict:
    """Parse ref_pic_list_struct() - H.266 RPL replaces H.265 short_term_ref_pic_set."""
    rpl = {}

    rpl["num_ref_entries"] = reader.read_unsigned_exp_golomb()

    if rpl["num_ref_entries"] > 0 and sps.get("sps_long_term_ref_pics_flag"):
        rpl["ltrp_in_header_flag"] = reader.read_bits(1)
    else:
        rpl["ltrp_in_header_flag"] = 0

    rpl["entries"] = []
    for i in range(rpl["num_ref_entries"]):
        entry = {}

        if sps.get("sps_inter_layer_prediction_enabled_flag"):
            entry["inter_layer_ref_pic_flag"] = reader.read_bits(1)
        else:
            entry["inter_layer_ref_pic_flag"] = 0

        if entry["inter_layer_ref_pic_flag"]:
            entry["ilrp_idx"] = reader.read_unsigned_exp_golomb()
        else:
            if sps.get("sps_long_term_ref_pics_flag"):
                entry["st_ref_pic_flag"] = reader.read_bits(1)
            else:
                entry["st_ref_pic_flag"] = 1

            if entry.get("st_ref_pic_flag", 1):
                entry["abs_delta_poc_st"] = reader.read_unsigned_exp_golomb()
                if entry["abs_delta_poc_st"] > 0:
                    entry["strp_entry_sign_flag"] = reader.read_bits(1)
            else:
                # Long-term reference
                if not rpl.get("ltrp_in_header_flag"):
                    lt_bits = sps.get("sps_log2_max_pic_order_cnt_lsb_minus4", 0) + 4
                    entry["rpls_poc_lsb_lt"] = reader.read_bits(lt_bits)

        rpl["entries"].append(entry)

    return rpl


def _parse_general_timing_hrd(reader: BitReader) -> dict:
    """Parse general_timing_hrd_parameters()."""
    hrd = {}
    hrd["num_units_in_tick"] = reader.read_bits(32)
    hrd["time_scale"] = reader.read_bits(32)
    if hrd["num_units_in_tick"] > 0:
        hrd["derived_fps"] = hrd["time_scale"] / hrd["num_units_in_tick"]

    hrd["general_nal_hrd_params_present_flag"] = reader.read_bits(1)
    hrd["general_vcl_hrd_params_present_flag"] = reader.read_bits(1)
    if hrd["general_nal_hrd_params_present_flag"] or hrd["general_vcl_hrd_params_present_flag"]:
        hrd["general_same_pic_timing_in_all_ols_flag"] = reader.read_bits(1)
        hrd["general_du_hrd_params_present_flag"] = reader.read_bits(1)
        if hrd["general_du_hrd_params_present_flag"]:
            hrd["tick_divisor_minus2"] = reader.read_bits(8)
        hrd["bit_rate_scale"] = reader.read_bits(4)
        hrd["cpb_size_scale"] = reader.read_bits(4)
        if hrd["general_du_hrd_params_present_flag"]:
            hrd["cpb_size_du_scale"] = reader.read_bits(4)
        hrd["hrd_cpb_cnt_minus1"] = reader.read_unsigned_exp_golomb()

    return hrd


def _parse_vui_parameters(reader: BitReader) -> dict:
    """Parse VUI parameters for H.266."""
    vui = {}

    vui["vui_progressive_source_flag"] = reader.read_bits(1)
    vui["vui_interlaced_source_flag"] = reader.read_bits(1)
    vui["vui_non_packed_constraint_flag"] = reader.read_bits(1)
    vui["vui_non_projected_flag"] = reader.read_bits(1)

    vui["vui_aspect_ratio_info_present_flag"] = reader.read_bits(1)
    if vui["vui_aspect_ratio_info_present_flag"]:
        vui["vui_aspect_ratio_constant_flag"] = reader.read_bits(1)
        vui["vui_aspect_ratio_idc"] = reader.read_bits(8)
        if vui["vui_aspect_ratio_idc"] == 255:
            vui["vui_sar_width"] = reader.read_bits(16)
            vui["vui_sar_height"] = reader.read_bits(16)

    vui["vui_overscan_info_present_flag"] = reader.read_bits(1)
    if vui["vui_overscan_info_present_flag"]:
        vui["vui_overscan_appropriate_flag"] = reader.read_bits(1)

    vui["vui_colour_description_present_flag"] = reader.read_bits(1)
    if vui["vui_colour_description_present_flag"]:
        vui["vui_colour_primaries"] = reader.read_bits(8)
        vui["vui_transfer_characteristics"] = reader.read_bits(8)
        vui["vui_matrix_coefficients"] = reader.read_bits(8)
        vui["vui_full_range_flag"] = reader.read_bits(1)

    vui["vui_chroma_loc_info_present_flag"] = reader.read_bits(1)
    if vui["vui_chroma_loc_info_present_flag"]:
        if vui.get("vui_progressive_source_flag") and not vui.get("vui_interlaced_source_flag"):
            vui["vui_chroma_sample_loc_type_frame"] = reader.read_unsigned_exp_golomb()
        else:
            vui["vui_chroma_sample_loc_type_top_field"] = reader.read_unsigned_exp_golomb()
            vui["vui_chroma_sample_loc_type_bottom_field"] = reader.read_unsigned_exp_golomb()

    return vui


def _derive_resolution(sps: dict) -> None:
    """Compute actual width/height from SPS fields."""
    width = sps["sps_pic_width_max_in_luma_samples"]
    height = sps["sps_pic_height_max_in_luma_samples"]

    if sps.get("sps_conformance_window_flag"):
        chroma_format_idc = sps.get("sps_chroma_format_idc", 1)
        sub_width_c = 2 if chroma_format_idc in (1, 2) else 1
        sub_height_c = 2 if chroma_format_idc == 1 else 1

        width -= (sps["sps_conf_win_left_offset"] + sps["sps_conf_win_right_offset"]) * sub_width_c
        height -= (sps["sps_conf_win_top_offset"] + sps["sps_conf_win_bottom_offset"]) * sub_height_c

    sps["derived_width"] = width
    sps["derived_height"] = height
