"""H.264 Sequence Parameter Set (SPS) parser.

Follows ITU-T H.264 Section 7.3.2.1.1.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h264.definitions import HIGH_PROFILES, PROFILE_NAMES


def parse_sps(reader: BitReader) -> dict:
    """Parse an H.264 SPS from RBSP data (after NAL header byte)."""
    sps = {}

    sps["profile_idc"] = reader.read_bits(8)
    sps["constraint_set0_flag"] = reader.read_bits(1)
    sps["constraint_set1_flag"] = reader.read_bits(1)
    sps["constraint_set2_flag"] = reader.read_bits(1)
    sps["constraint_set3_flag"] = reader.read_bits(1)
    sps["constraint_set4_flag"] = reader.read_bits(1)
    sps["constraint_set5_flag"] = reader.read_bits(1)
    reader.skip_bits(2)  # reserved_zero_2bits
    sps["level_idc"] = reader.read_bits(8)
    sps["seq_parameter_set_id"] = reader.read_unsigned_exp_golomb()

    sps["profile_name"] = PROFILE_NAMES.get(sps["profile_idc"], "Unknown")
    sps["level"] = f"{sps['level_idc'] / 10:.1f}"

    if sps["profile_idc"] in HIGH_PROFILES:
        sps["chroma_format_idc"] = reader.read_unsigned_exp_golomb()
        if sps["chroma_format_idc"] == 3:
            sps["separate_colour_plane_flag"] = reader.read_bits(1)
        else:
            sps["separate_colour_plane_flag"] = 0
        sps["bit_depth_luma_minus8"] = reader.read_unsigned_exp_golomb()
        sps["bit_depth_chroma_minus8"] = reader.read_unsigned_exp_golomb()
        sps["qpprime_y_zero_transform_bypass_flag"] = reader.read_bits(1)
        sps["seq_scaling_matrix_present_flag"] = reader.read_bits(1)
        if sps["seq_scaling_matrix_present_flag"]:
            num_lists = 12 if sps["chroma_format_idc"] == 3 else 8
            sps["scaling_lists"] = []
            for i in range(num_lists):
                present = reader.read_bits(1)
                if present:
                    size = 16 if i < 6 else 64
                    sps["scaling_lists"].append(_parse_scaling_list(reader, size))
                else:
                    sps["scaling_lists"].append(None)
    else:
        sps["chroma_format_idc"] = 1
        sps["separate_colour_plane_flag"] = 0
        sps["bit_depth_luma_minus8"] = 0
        sps["bit_depth_chroma_minus8"] = 0

    sps["log2_max_frame_num_minus4"] = reader.read_unsigned_exp_golomb()
    sps["pic_order_cnt_type"] = reader.read_unsigned_exp_golomb()

    if sps["pic_order_cnt_type"] == 0:
        sps["log2_max_pic_order_cnt_lsb_minus4"] = reader.read_unsigned_exp_golomb()
    elif sps["pic_order_cnt_type"] == 1:
        sps["delta_pic_order_always_zero_flag"] = reader.read_bits(1)
        sps["offset_for_non_ref_pic"] = reader.read_signed_exp_golomb()
        sps["offset_for_top_to_bottom_field"] = reader.read_signed_exp_golomb()
        num_ref_frames_in_poc_cycle = reader.read_unsigned_exp_golomb()
        sps["num_ref_frames_in_pic_order_cnt_cycle"] = num_ref_frames_in_poc_cycle
        sps["offset_for_ref_frame"] = []
        for _ in range(num_ref_frames_in_poc_cycle):
            sps["offset_for_ref_frame"].append(reader.read_signed_exp_golomb())

    sps["max_num_ref_frames"] = reader.read_unsigned_exp_golomb()
    sps["gaps_in_frame_num_value_allowed_flag"] = reader.read_bits(1)
    sps["pic_width_in_mbs_minus1"] = reader.read_unsigned_exp_golomb()
    sps["pic_height_in_map_units_minus1"] = reader.read_unsigned_exp_golomb()
    sps["frame_mbs_only_flag"] = reader.read_bits(1)

    if not sps["frame_mbs_only_flag"]:
        sps["mb_adaptive_frame_field_flag"] = reader.read_bits(1)

    sps["direct_8x8_inference_flag"] = reader.read_bits(1)

    sps["frame_cropping_flag"] = reader.read_bits(1)
    if sps["frame_cropping_flag"]:
        sps["frame_crop_left_offset"] = reader.read_unsigned_exp_golomb()
        sps["frame_crop_right_offset"] = reader.read_unsigned_exp_golomb()
        sps["frame_crop_top_offset"] = reader.read_unsigned_exp_golomb()
        sps["frame_crop_bottom_offset"] = reader.read_unsigned_exp_golomb()

    sps["vui_parameters_present_flag"] = reader.read_bits(1)
    if sps["vui_parameters_present_flag"]:
        sps["vui"] = _parse_vui_parameters(reader)

    # Derive actual resolution
    _derive_resolution(sps)

    return sps


def _parse_scaling_list(reader: BitReader, size: int) -> list[int]:
    """Parse a scaling list of given size (16 or 64)."""
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


def _parse_vui_parameters(reader: BitReader) -> dict:
    """Parse VUI parameters (Annex E)."""
    vui = {}

    vui["aspect_ratio_info_present_flag"] = reader.read_bits(1)
    if vui["aspect_ratio_info_present_flag"]:
        vui["aspect_ratio_idc"] = reader.read_bits(8)
        if vui["aspect_ratio_idc"] == 255:  # Extended_SAR
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

    vui["timing_info_present_flag"] = reader.read_bits(1)
    if vui["timing_info_present_flag"]:
        vui["num_units_in_tick"] = reader.read_bits(32)
        vui["time_scale"] = reader.read_bits(32)
        vui["fixed_frame_rate_flag"] = reader.read_bits(1)
        if vui["num_units_in_tick"] > 0:
            vui["derived_fps"] = vui["time_scale"] / (2.0 * vui["num_units_in_tick"])

    vui["nal_hrd_parameters_present_flag"] = reader.read_bits(1)
    if vui["nal_hrd_parameters_present_flag"]:
        vui["nal_hrd"] = _parse_hrd_parameters(reader)

    vui["vcl_hrd_parameters_present_flag"] = reader.read_bits(1)
    if vui["vcl_hrd_parameters_present_flag"]:
        vui["vcl_hrd"] = _parse_hrd_parameters(reader)

    if vui.get("nal_hrd_parameters_present_flag") or vui.get("vcl_hrd_parameters_present_flag"):
        vui["low_delay_hrd_flag"] = reader.read_bits(1)

    vui["pic_struct_present_flag"] = reader.read_bits(1)

    vui["bitstream_restriction_flag"] = reader.read_bits(1)
    if vui["bitstream_restriction_flag"]:
        vui["motion_vectors_over_pic_boundaries_flag"] = reader.read_bits(1)
        vui["max_bytes_per_pic_denom"] = reader.read_unsigned_exp_golomb()
        vui["max_bits_per_mb_denom"] = reader.read_unsigned_exp_golomb()
        vui["log2_max_mv_length_horizontal"] = reader.read_unsigned_exp_golomb()
        vui["log2_max_mv_length_vertical"] = reader.read_unsigned_exp_golomb()
        vui["max_num_reorder_frames"] = reader.read_unsigned_exp_golomb()
        vui["max_dec_frame_buffering"] = reader.read_unsigned_exp_golomb()

    return vui


def _parse_hrd_parameters(reader: BitReader) -> dict:
    """Parse HRD parameters."""
    hrd = {}
    hrd["cpb_cnt_minus1"] = reader.read_unsigned_exp_golomb()
    hrd["bit_rate_scale"] = reader.read_bits(4)
    hrd["cpb_size_scale"] = reader.read_bits(4)
    hrd["schedules"] = []
    for _ in range(hrd["cpb_cnt_minus1"] + 1):
        hrd["schedules"].append({
            "bit_rate_value_minus1": reader.read_unsigned_exp_golomb(),
            "cpb_size_value_minus1": reader.read_unsigned_exp_golomb(),
            "cbr_flag": reader.read_bits(1),
        })
    hrd["initial_cpb_removal_delay_length_minus1"] = reader.read_bits(5)
    hrd["cpb_removal_delay_length_minus1"] = reader.read_bits(5)
    hrd["dpb_output_delay_length_minus1"] = reader.read_bits(5)
    hrd["time_offset_length"] = reader.read_bits(5)
    return hrd


def _derive_resolution(sps: dict) -> None:
    """Compute actual width/height from SPS fields."""
    width = (sps["pic_width_in_mbs_minus1"] + 1) * 16
    height = (sps["pic_height_in_map_units_minus1"] + 1) * 16
    if not sps["frame_mbs_only_flag"]:
        height *= 2

    if sps["frame_cropping_flag"]:
        chroma_format_idc = sps.get("chroma_format_idc", 1)
        if chroma_format_idc == 0:
            crop_unit_x, crop_unit_y = 1, 2 - sps["frame_mbs_only_flag"]
        elif chroma_format_idc == 1:
            crop_unit_x, crop_unit_y = 2, 2 * (2 - sps["frame_mbs_only_flag"])
        elif chroma_format_idc == 2:
            crop_unit_x, crop_unit_y = 2, 2 - sps["frame_mbs_only_flag"]
        else:  # 3
            crop_unit_x, crop_unit_y = 1, 2 - sps["frame_mbs_only_flag"]

        width -= (sps["frame_crop_left_offset"] + sps["frame_crop_right_offset"]) * crop_unit_x
        height -= (sps["frame_crop_top_offset"] + sps["frame_crop_bottom_offset"]) * crop_unit_y

    sps["derived_width"] = width
    sps["derived_height"] = height
