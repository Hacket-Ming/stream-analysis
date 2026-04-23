"""H.265 Sequence Parameter Set (SPS) parser.

Follows ITU-T H.265 Section 7.3.2.2.
"""

import math
from stream_analysis.bitreader import BitReader
from stream_analysis.h265.profile_tier_level import parse_profile_tier_level


def parse_sps(reader: BitReader) -> dict:
    """Parse an H.265 SPS from RBSP data (after 2-byte NAL header)."""
    sps = {}

    sps["sps_video_parameter_set_id"] = reader.read_bits(4)
    sps["sps_max_sub_layers_minus1"] = reader.read_bits(3)
    sps["sps_temporal_id_nesting_flag"] = reader.read_bits(1)

    sps["profile_tier_level"] = parse_profile_tier_level(
        reader, True, sps["sps_max_sub_layers_minus1"]
    )

    sps["sps_seq_parameter_set_id"] = reader.read_unsigned_exp_golomb()
    sps["chroma_format_idc"] = reader.read_unsigned_exp_golomb()

    if sps["chroma_format_idc"] == 3:
        sps["separate_colour_plane_flag"] = reader.read_bits(1)
    else:
        sps["separate_colour_plane_flag"] = 0

    sps["pic_width_in_luma_samples"] = reader.read_unsigned_exp_golomb()
    sps["pic_height_in_luma_samples"] = reader.read_unsigned_exp_golomb()

    sps["conformance_window_flag"] = reader.read_bits(1)
    if sps["conformance_window_flag"]:
        sps["conf_win_left_offset"] = reader.read_unsigned_exp_golomb()
        sps["conf_win_right_offset"] = reader.read_unsigned_exp_golomb()
        sps["conf_win_top_offset"] = reader.read_unsigned_exp_golomb()
        sps["conf_win_bottom_offset"] = reader.read_unsigned_exp_golomb()

    sps["bit_depth_luma_minus8"] = reader.read_unsigned_exp_golomb()
    sps["bit_depth_chroma_minus8"] = reader.read_unsigned_exp_golomb()
    sps["log2_max_pic_order_cnt_lsb_minus4"] = reader.read_unsigned_exp_golomb()

    sps["sps_sub_layer_ordering_info_present_flag"] = reader.read_bits(1)
    start = 0 if sps["sps_sub_layer_ordering_info_present_flag"] else sps["sps_max_sub_layers_minus1"]
    sps["sub_layer_ordering"] = []
    for _ in range(start, sps["sps_max_sub_layers_minus1"] + 1):
        sps["sub_layer_ordering"].append({
            "sps_max_dec_pic_buffering_minus1": reader.read_unsigned_exp_golomb(),
            "sps_max_num_reorder_pics": reader.read_unsigned_exp_golomb(),
            "sps_max_latency_increase_plus1": reader.read_unsigned_exp_golomb(),
        })

    sps["log2_min_luma_coding_block_size_minus3"] = reader.read_unsigned_exp_golomb()
    sps["log2_diff_max_min_luma_coding_block_size"] = reader.read_unsigned_exp_golomb()
    sps["log2_min_luma_transform_block_size_minus2"] = reader.read_unsigned_exp_golomb()
    sps["log2_diff_max_min_luma_transform_block_size"] = reader.read_unsigned_exp_golomb()
    sps["max_transform_hierarchy_depth_inter"] = reader.read_unsigned_exp_golomb()
    sps["max_transform_hierarchy_depth_intra"] = reader.read_unsigned_exp_golomb()

    sps["scaling_list_enabled_flag"] = reader.read_bits(1)
    if sps["scaling_list_enabled_flag"]:
        sps["sps_scaling_list_data_present_flag"] = reader.read_bits(1)
        if sps["sps_scaling_list_data_present_flag"]:
            sps["scaling_list_data"] = _parse_scaling_list_data(reader)

    sps["amp_enabled_flag"] = reader.read_bits(1)
    sps["sample_adaptive_offset_enabled_flag"] = reader.read_bits(1)

    sps["pcm_enabled_flag"] = reader.read_bits(1)
    if sps["pcm_enabled_flag"]:
        sps["pcm_sample_bit_depth_luma_minus1"] = reader.read_bits(4)
        sps["pcm_sample_bit_depth_chroma_minus1"] = reader.read_bits(4)
        sps["log2_min_pcm_luma_coding_block_size_minus3"] = reader.read_unsigned_exp_golomb()
        sps["log2_diff_max_min_pcm_luma_coding_block_size"] = reader.read_unsigned_exp_golomb()
        sps["pcm_loop_filter_disabled_flag"] = reader.read_bits(1)

    sps["num_short_term_ref_pic_sets"] = reader.read_unsigned_exp_golomb()
    sps["short_term_ref_pic_sets"] = []
    for i in range(sps["num_short_term_ref_pic_sets"]):
        st_rps = parse_short_term_ref_pic_set(reader, i, sps["num_short_term_ref_pic_sets"],
                                               sps["short_term_ref_pic_sets"])
        sps["short_term_ref_pic_sets"].append(st_rps)

    sps["long_term_ref_pics_present_flag"] = reader.read_bits(1)
    if sps["long_term_ref_pics_present_flag"]:
        sps["num_long_term_ref_pics_sps"] = reader.read_unsigned_exp_golomb()
        sps["lt_ref_pic_poc_lsb_sps"] = []
        sps["used_by_curr_pic_lt_sps_flag"] = []
        lt_bits = sps["log2_max_pic_order_cnt_lsb_minus4"] + 4
        for _ in range(sps["num_long_term_ref_pics_sps"]):
            sps["lt_ref_pic_poc_lsb_sps"].append(reader.read_bits(lt_bits))
            sps["used_by_curr_pic_lt_sps_flag"].append(reader.read_bits(1))

    sps["sps_temporal_mvp_enabled_flag"] = reader.read_bits(1)
    sps["strong_intra_smoothing_enabled_flag"] = reader.read_bits(1)

    sps["vui_parameters_present_flag"] = reader.read_bits(1)
    if sps["vui_parameters_present_flag"]:
        sps["vui"] = _parse_vui_parameters(reader, sps["sps_max_sub_layers_minus1"])

    # Derive resolution
    _derive_resolution(sps)

    return sps


def parse_short_term_ref_pic_set(reader: BitReader, st_rps_idx: int,
                                  num_short_term_ref_pic_sets: int,
                                  ref_pic_sets: list) -> dict:
    """Parse short_term_ref_pic_set().

    This is the most complex sub-routine in H.265 SPS parsing.
    """
    rps = {}

    inter_ref_pic_set_prediction_flag = 0
    if st_rps_idx != 0:
        inter_ref_pic_set_prediction_flag = reader.read_bits(1)
    rps["inter_ref_pic_set_prediction_flag"] = inter_ref_pic_set_prediction_flag

    if inter_ref_pic_set_prediction_flag:
        delta_idx_minus1 = 0
        if st_rps_idx == num_short_term_ref_pic_sets:
            delta_idx_minus1 = reader.read_unsigned_exp_golomb()
        rps["delta_idx_minus1"] = delta_idx_minus1

        delta_rps_sign = reader.read_bits(1)
        abs_delta_rps_minus1 = reader.read_unsigned_exp_golomb()
        delta_rps = (1 - 2 * delta_rps_sign) * (abs_delta_rps_minus1 + 1)
        rps["delta_rps"] = delta_rps

        ref_idx = st_rps_idx - 1 - delta_idx_minus1
        ref_rps = ref_pic_sets[ref_idx]

        num_delta_pocs = ref_rps.get("num_delta_pocs", 0)

        used_by_curr_pic_flag = []
        use_delta_flag = []
        for _ in range(num_delta_pocs + 1):
            used = reader.read_bits(1)
            used_by_curr_pic_flag.append(used)
            if not used:
                use_delta = reader.read_bits(1)
                use_delta_flag.append(use_delta)
            else:
                use_delta_flag.append(1)

        # Derive the new ref pic set from the reference
        delta_poc_s0 = []
        used_s0 = []
        delta_poc_s1 = []
        used_s1 = []

        ref_delta_poc_s0 = ref_rps.get("delta_poc_s0", [])
        ref_delta_poc_s1 = ref_rps.get("delta_poc_s1", [])
        ref_used_s0 = ref_rps.get("used_by_curr_pic_s0", [])
        ref_used_s1 = ref_rps.get("used_by_curr_pic_s1", [])

        # Build list of all delta_poc values from reference set
        d_pocs = []
        for j in range(len(ref_delta_poc_s0)):
            d_pocs.append(ref_delta_poc_s0[j])
        for j in range(len(ref_delta_poc_s1)):
            d_pocs.append(ref_delta_poc_s1[j])

        for j in range(len(d_pocs) + 1):
            if use_delta_flag[j]:
                if j < len(d_pocs):
                    d_poc = delta_rps + d_pocs[j]
                else:
                    d_poc = delta_rps

                if d_poc < 0:
                    delta_poc_s0.append(d_poc)
                    used_s0.append(used_by_curr_pic_flag[j])
                elif d_poc > 0:
                    delta_poc_s1.append(d_poc)
                    used_s1.append(used_by_curr_pic_flag[j])

        # Sort: s0 should be negative (descending), s1 should be positive (ascending)
        pairs_s0 = sorted(zip(delta_poc_s0, used_s0), key=lambda x: x[0])
        pairs_s1 = sorted(zip(delta_poc_s1, used_s1), key=lambda x: x[0])

        rps["delta_poc_s0"] = [p[0] for p in pairs_s0]
        rps["used_by_curr_pic_s0"] = [p[1] for p in pairs_s0]
        rps["delta_poc_s1"] = [p[0] for p in pairs_s1]
        rps["used_by_curr_pic_s1"] = [p[1] for p in pairs_s1]
        rps["num_negative_pics"] = len(rps["delta_poc_s0"])
        rps["num_positive_pics"] = len(rps["delta_poc_s1"])
    else:
        rps["num_negative_pics"] = reader.read_unsigned_exp_golomb()
        rps["num_positive_pics"] = reader.read_unsigned_exp_golomb()

        rps["delta_poc_s0"] = []
        rps["used_by_curr_pic_s0"] = []
        delta_poc = 0
        for _ in range(rps["num_negative_pics"]):
            delta_poc_s0_minus1 = reader.read_unsigned_exp_golomb()
            used = reader.read_bits(1)
            delta_poc -= (delta_poc_s0_minus1 + 1)
            rps["delta_poc_s0"].append(delta_poc)
            rps["used_by_curr_pic_s0"].append(used)

        rps["delta_poc_s1"] = []
        rps["used_by_curr_pic_s1"] = []
        delta_poc = 0
        for _ in range(rps["num_positive_pics"]):
            delta_poc_s1_minus1 = reader.read_unsigned_exp_golomb()
            used = reader.read_bits(1)
            delta_poc += (delta_poc_s1_minus1 + 1)
            rps["delta_poc_s1"].append(delta_poc)
            rps["used_by_curr_pic_s1"].append(used)

    rps["num_delta_pocs"] = rps["num_negative_pics"] + rps["num_positive_pics"]

    return rps


def _parse_scaling_list_data(reader: BitReader) -> dict:
    """Parse scaling_list_data()."""
    data = {"lists": []}
    for size_id in range(4):
        step = 1 if size_id == 3 else 3 if size_id == 0 else 1
        for matrix_id in range(0, 6, step if size_id == 3 else 1):
            pred_mode_flag = reader.read_bits(1)
            entry = {"size_id": size_id, "matrix_id": matrix_id}
            if not pred_mode_flag:
                entry["pred_matrix_id_delta"] = reader.read_unsigned_exp_golomb()
            else:
                if size_id > 1:
                    entry["dc_coef_minus8"] = reader.read_signed_exp_golomb()
                coeff_num = min(64, 1 << (4 + (size_id << 1)))
                entry["coefficients"] = []
                for _ in range(coeff_num):
                    entry["coefficients"].append(reader.read_signed_exp_golomb())
            data["lists"].append(entry)
    return data


def _parse_vui_parameters(reader: BitReader, max_sub_layers_minus1: int) -> dict:
    """Parse VUI parameters for H.265."""
    vui = {}

    vui["aspect_ratio_info_present_flag"] = reader.read_bits(1)
    if vui["aspect_ratio_info_present_flag"]:
        vui["aspect_ratio_idc"] = reader.read_bits(8)
        if vui["aspect_ratio_idc"] == 255:
            vui["sar_width"] = reader.read_bits(16)
            vui["sar_height"] = reader.read_bits(16)

    vui["overscan_info_present_flag"] = reader.read_bits(1)
    if vui["overscan_info_present_flag"]:
        vui["overscan_appropriate_flag"] = reader.read_bits(1)

    vui["video_signal_type_present_flag"] = reader.read_bits(1)
    if vui["video_signal_type_present_flag"]:
        vui["video_format"] = reader.read_bits(3)
        vui["video_full_range_flag"] = reader.read_bits(1)
        vui["colour_description_present_flag"] = reader.read_bits(1)
        if vui["colour_description_present_flag"]:
            vui["colour_primaries"] = reader.read_bits(8)
            vui["transfer_characteristics"] = reader.read_bits(8)
            vui["matrix_coefficients"] = reader.read_bits(8)

    vui["chroma_loc_info_present_flag"] = reader.read_bits(1)
    if vui["chroma_loc_info_present_flag"]:
        vui["chroma_sample_loc_type_top_field"] = reader.read_unsigned_exp_golomb()
        vui["chroma_sample_loc_type_bottom_field"] = reader.read_unsigned_exp_golomb()

    vui["neutral_chroma_indication_flag"] = reader.read_bits(1)
    vui["field_seq_flag"] = reader.read_bits(1)
    vui["frame_field_info_present_flag"] = reader.read_bits(1)

    vui["default_display_window_flag"] = reader.read_bits(1)
    if vui["default_display_window_flag"]:
        vui["def_disp_win_left_offset"] = reader.read_unsigned_exp_golomb()
        vui["def_disp_win_right_offset"] = reader.read_unsigned_exp_golomb()
        vui["def_disp_win_top_offset"] = reader.read_unsigned_exp_golomb()
        vui["def_disp_win_bottom_offset"] = reader.read_unsigned_exp_golomb()

    vui["vui_timing_info_present_flag"] = reader.read_bits(1)
    if vui["vui_timing_info_present_flag"]:
        vui["vui_num_units_in_tick"] = reader.read_bits(32)
        vui["vui_time_scale"] = reader.read_bits(32)
        if vui["vui_num_units_in_tick"] > 0:
            vui["derived_fps"] = vui["vui_time_scale"] / vui["vui_num_units_in_tick"]

        vui["vui_poc_proportional_to_timing_flag"] = reader.read_bits(1)
        if vui["vui_poc_proportional_to_timing_flag"]:
            vui["vui_num_ticks_poc_diff_one_minus1"] = reader.read_unsigned_exp_golomb()

        vui["vui_hrd_parameters_present_flag"] = reader.read_bits(1)
        if vui["vui_hrd_parameters_present_flag"]:
            vui["hrd"] = _parse_hrd_parameters(reader, True, max_sub_layers_minus1)

    vui["bitstream_restriction_flag"] = reader.read_bits(1)
    if vui["bitstream_restriction_flag"]:
        vui["tiles_fixed_structure_flag"] = reader.read_bits(1)
        vui["motion_vectors_over_pic_boundaries_flag"] = reader.read_bits(1)
        vui["restricted_ref_pic_lists_flag"] = reader.read_bits(1)
        vui["min_spatial_segmentation_idc"] = reader.read_unsigned_exp_golomb()
        vui["max_bytes_per_pic_denom"] = reader.read_unsigned_exp_golomb()
        vui["max_bits_per_min_cu_denom"] = reader.read_unsigned_exp_golomb()
        vui["log2_max_mv_length_horizontal"] = reader.read_unsigned_exp_golomb()
        vui["log2_max_mv_length_vertical"] = reader.read_unsigned_exp_golomb()

    return vui


def _parse_hrd_parameters(reader: BitReader, common_inf_present_flag: bool,
                           max_sub_layers_minus1: int) -> dict:
    """Parse HRD parameters for H.265."""
    hrd = {}

    nal_hrd_present = False
    vcl_hrd_present = False
    sub_pic_hrd_params_present = False

    if common_inf_present_flag:
        hrd["nal_hrd_parameters_present_flag"] = reader.read_bits(1)
        hrd["vcl_hrd_parameters_present_flag"] = reader.read_bits(1)
        nal_hrd_present = hrd["nal_hrd_parameters_present_flag"]
        vcl_hrd_present = hrd["vcl_hrd_parameters_present_flag"]

        if nal_hrd_present or vcl_hrd_present:
            hrd["sub_pic_hrd_params_present_flag"] = reader.read_bits(1)
            sub_pic_hrd_params_present = hrd["sub_pic_hrd_params_present_flag"]
            if sub_pic_hrd_params_present:
                hrd["tick_divisor_minus2"] = reader.read_bits(8)
                hrd["du_cpb_removal_delay_increment_length_minus1"] = reader.read_bits(5)
                hrd["sub_pic_cpb_params_in_pic_timing_sei_flag"] = reader.read_bits(1)
                hrd["dpb_output_delay_du_length_minus1"] = reader.read_bits(5)

            hrd["bit_rate_scale"] = reader.read_bits(4)
            hrd["cpb_size_scale"] = reader.read_bits(4)
            if sub_pic_hrd_params_present:
                hrd["cpb_size_du_scale"] = reader.read_bits(4)

            hrd["initial_cpb_removal_delay_length_minus1"] = reader.read_bits(5)
            hrd["au_cpb_removal_delay_length_minus1"] = reader.read_bits(5)
            hrd["dpb_output_delay_length_minus1"] = reader.read_bits(5)

    hrd["sub_layers"] = []
    for i in range(max_sub_layers_minus1 + 1):
        sub = {}
        sub["fixed_pic_rate_general_flag"] = reader.read_bits(1)
        fixed_pic_rate_within_cvs = sub["fixed_pic_rate_general_flag"]
        if not sub["fixed_pic_rate_general_flag"]:
            sub["fixed_pic_rate_within_cvs_flag"] = reader.read_bits(1)
            fixed_pic_rate_within_cvs = sub["fixed_pic_rate_within_cvs_flag"]
        low_delay_hrd = False
        if fixed_pic_rate_within_cvs:
            sub["elemental_duration_in_tc_minus1"] = reader.read_unsigned_exp_golomb()
        else:
            sub["low_delay_hrd_flag"] = reader.read_bits(1)
            low_delay_hrd = sub["low_delay_hrd_flag"]

        cpb_cnt = 1
        if not low_delay_hrd:
            sub["cpb_cnt_minus1"] = reader.read_unsigned_exp_golomb()
            cpb_cnt = sub["cpb_cnt_minus1"] + 1

        if nal_hrd_present:
            sub["nal_sub_layer_hrd"] = _parse_sub_layer_hrd(
                reader, cpb_cnt, sub_pic_hrd_params_present)
        if vcl_hrd_present:
            sub["vcl_sub_layer_hrd"] = _parse_sub_layer_hrd(
                reader, cpb_cnt, sub_pic_hrd_params_present)
        hrd["sub_layers"].append(sub)

    return hrd


def _parse_sub_layer_hrd(reader: BitReader, cpb_cnt: int,
                          sub_pic_hrd_params_present: bool) -> list:
    """Parse sub_layer_hrd_parameters()."""
    entries = []
    for _ in range(cpb_cnt):
        entry = {
            "bit_rate_value_minus1": reader.read_unsigned_exp_golomb(),
            "cpb_size_value_minus1": reader.read_unsigned_exp_golomb(),
        }
        if sub_pic_hrd_params_present:
            entry["cpb_size_du_value_minus1"] = reader.read_unsigned_exp_golomb()
            entry["bit_rate_du_value_minus1"] = reader.read_unsigned_exp_golomb()
        entry["cbr_flag"] = reader.read_bits(1)
        entries.append(entry)
    return entries


def _derive_resolution(sps: dict) -> None:
    """Compute actual width/height from SPS fields."""
    width = sps["pic_width_in_luma_samples"]
    height = sps["pic_height_in_luma_samples"]

    if sps.get("conformance_window_flag"):
        chroma_format_idc = sps.get("chroma_format_idc", 1)
        sub_width_c = 2 if chroma_format_idc in (1, 2) else 1
        sub_height_c = 2 if chroma_format_idc == 1 else 1

        width -= (sps["conf_win_left_offset"] + sps["conf_win_right_offset"]) * sub_width_c
        height -= (sps["conf_win_top_offset"] + sps["conf_win_bottom_offset"]) * sub_height_c

    sps["derived_width"] = width
    sps["derived_height"] = height
