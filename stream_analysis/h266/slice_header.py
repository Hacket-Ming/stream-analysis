"""H.266 Slice Header parser.

Follows ITU-T H.266 Section 7.3.7.
Parses all fields up to but NOT including slice_data().
"""

import math
from stream_analysis.bitreader import BitReader
from stream_analysis.h266.definitions import SLICE_TYPE_NAMES, is_irap, is_idr, is_gdr
from stream_analysis.h266.picture_header import parse_picture_header, _parse_ref_pic_lists


def parse_slice_header(reader: BitReader, nal_unit_type: int,
                       vps_map: dict, sps_map: dict, pps_map: dict,
                       active_ph: dict | None) -> dict:
    """Parse a slice header from RBSP data (after 2-byte NAL header).

    Args:
        active_ph: The most recently parsed Picture Header, or None.
    """
    sh = {}

    sh["sh_picture_header_in_slice_header_flag"] = reader.read_bits(1)

    if sh["sh_picture_header_in_slice_header_flag"]:
        # Picture header is embedded in this slice header
        sh["picture_header"] = parse_picture_header(
            reader, nal_unit_type, vps_map, sps_map, pps_map)
        ph = sh["picture_header"]
    else:
        ph = active_ph or {}

    pps_id = ph.get("ph_pic_parameter_set_id", 0)
    pps = pps_map.get(pps_id)
    if pps is None:
        sh["_error"] = f"PPS {pps_id} not found"
        return sh

    sps_id = pps.get("pps_seq_parameter_set_id", 0)
    sps = sps_map.get(sps_id)
    if sps is None:
        sh["_error"] = f"SPS {sps_id} not found"
        return sh

    # Subpicture ID
    num_subpics = sps.get("sps_num_subpics_minus1", 0) + 1
    if sps.get("sps_subpic_info_present_flag") and num_subpics > 1:
        subpic_id_bits = sps.get("sps_subpic_id_len_minus1", 0) + 1
        sh["sh_subpic_id"] = reader.read_bits(subpic_id_bits)

    # Slice address
    num_slices = pps.get("derived_num_slices_in_pic", 1)
    if num_slices > 1:
        addr_bits = max(1, math.ceil(math.log2(num_slices)))
        sh["sh_slice_address"] = reader.read_bits(addr_bits)

    # Extra SH bits
    num_extra_sh_bytes = sps.get("sps_num_extra_sh_bytes", 0)
    extra_sh_bits = sps.get("sps_extra_sh_bit_present_flag", [])
    for i in range(num_extra_sh_bytes * 8):
        if i < len(extra_sh_bits) and extra_sh_bits[i]:
            reader.read_bits(1)  # sh_extra_bit

    # Number of tiles in slice
    if not pps.get("pps_rect_slice_flag", 1) and pps.get("derived_num_tiles_in_pic", 1) > 1:
        num_tiles = pps.get("derived_num_tiles_in_pic", 1)
        tiles_bits = max(1, math.ceil(math.log2(num_tiles)))
        sh["sh_num_tiles_in_slice_minus1"] = reader.read_bits(tiles_bits)

    # Slice type
    if ph.get("ph_inter_slice_allowed_flag"):
        sh["sh_slice_type"] = reader.read_unsigned_exp_golomb()
    else:
        sh["sh_slice_type"] = 2  # I slice
    sh["slice_type_name"] = SLICE_TYPE_NAMES.get(sh["sh_slice_type"], f"unknown({sh['sh_slice_type']})")

    if nal_unit_type == 10:  # GDR_NUT
        if not ph.get("ph_gdr_or_irap_pic_flag"):
            sh["sh_no_output_of_prior_pics_flag"] = reader.read_bits(1)

    # ALF
    if sps.get("sps_alf_enabled_flag") and not pps.get("pps_alf_info_in_ph_flag"):
        sh["sh_alf_enabled_flag"] = reader.read_bits(1)
        if sh["sh_alf_enabled_flag"]:
            sh["sh_num_alf_aps_ids_luma"] = reader.read_bits(3)
            sh["sh_alf_aps_id_luma"] = []
            for _ in range(sh["sh_num_alf_aps_ids_luma"]):
                sh["sh_alf_aps_id_luma"].append(reader.read_bits(3))
            if sps.get("sps_chroma_format_idc", 0) != 0:
                sh["sh_alf_cb_enabled_flag"] = reader.read_bits(1)
                sh["sh_alf_cr_enabled_flag"] = reader.read_bits(1)
            if sh.get("sh_alf_cb_enabled_flag") or sh.get("sh_alf_cr_enabled_flag"):
                sh["sh_alf_aps_id_chroma"] = reader.read_bits(3)
            if sps.get("sps_ccalf_enabled_flag"):
                sh["sh_alf_cc_cb_enabled_flag"] = reader.read_bits(1)
                if sh["sh_alf_cc_cb_enabled_flag"]:
                    sh["sh_alf_cc_cb_aps_id"] = reader.read_bits(3)
                sh["sh_alf_cc_cr_enabled_flag"] = reader.read_bits(1)
                if sh["sh_alf_cc_cr_enabled_flag"]:
                    sh["sh_alf_cc_cr_aps_id"] = reader.read_bits(3)

    # LMCS (if not already in PH)
    if sps.get("sps_lmcs_enabled_flag") and not sh["sh_picture_header_in_slice_header_flag"]:
        sh["sh_lmcs_used_flag"] = reader.read_bits(1)

    # Explicit scaling list (if not already in PH)
    if sps.get("sps_explicit_scaling_list_enabled_flag") and not sh["sh_picture_header_in_slice_header_flag"]:
        sh["sh_explicit_scaling_list_used_flag"] = reader.read_bits(1)

    # RPL
    if not pps.get("pps_rpl_info_in_ph_flag") and sh.get("sh_slice_type", 2) != 2:
        sh["ref_pic_lists"] = _parse_ref_pic_lists(reader, sps, pps)

    # Num ref idx override
    slice_type = sh.get("sh_slice_type", 2)
    if slice_type != 2:  # not I
        if pps.get("pps_cabac_init_present_flag"):
            sh["sh_cabac_init_flag"] = reader.read_bits(1)

        if ph.get("ph_temporal_mvp_enabled_flag") and not pps.get("pps_rpl_info_in_ph_flag"):
            if slice_type == 0:  # B
                sh["sh_collocated_from_l0_flag"] = reader.read_bits(1)

        sh["sh_num_ref_idx_active_override_flag"] = reader.read_bits(1)
        if sh["sh_num_ref_idx_active_override_flag"]:
            for i in range(2 if slice_type == 0 else 1):
                sh[f"sh_num_ref_idx_active_minus1_{i}"] = reader.read_unsigned_exp_golomb()

    # QP
    if not pps.get("pps_qp_delta_info_in_ph_flag"):
        sh["sh_qp_delta"] = reader.read_signed_exp_golomb()

    # Derive QP
    init_qp = 26 + pps.get("pps_init_qp_minus26", 0)
    if pps.get("pps_qp_delta_info_in_ph_flag"):
        sh["derived_slice_qp"] = init_qp + ph.get("ph_qp_delta", 0)
    else:
        sh["derived_slice_qp"] = init_qp + sh.get("sh_qp_delta", 0)

    # Chroma QP offsets
    if pps.get("pps_slice_chroma_qp_offsets_present_flag"):
        sh["sh_cb_qp_offset"] = reader.read_signed_exp_golomb()
        sh["sh_cr_qp_offset"] = reader.read_signed_exp_golomb()
        if pps.get("pps_joint_cbcr_qp_offset_present_flag"):
            sh["sh_joint_cbcr_qp_offset"] = reader.read_signed_exp_golomb()

    # CU QP delta
    if pps.get("pps_cu_chroma_qp_offset_list_enabled_flag"):
        sh["sh_cu_chroma_qp_offset_enabled_flag"] = reader.read_bits(1)

    # SAO
    if sps.get("sps_sao_enabled_flag") and not pps.get("pps_sao_info_in_ph_flag"):
        sh["sh_sao_luma_used_flag"] = reader.read_bits(1)
        if sps.get("sps_chroma_format_idc", 0) != 0:
            sh["sh_sao_chroma_used_flag"] = reader.read_bits(1)

    # Deblocking
    if pps.get("pps_deblocking_filter_override_enabled_flag") and not pps.get("pps_dbf_info_in_ph_flag", 0):
        sh["sh_deblocking_params_present_flag"] = reader.read_bits(1)
        if sh.get("sh_deblocking_params_present_flag"):
            if not pps.get("pps_deblocking_filter_disabled_flag"):
                sh["sh_deblocking_filter_disabled_flag"] = reader.read_bits(1)
            if not sh.get("sh_deblocking_filter_disabled_flag", pps.get("pps_deblocking_filter_disabled_flag", 0)):
                sh["sh_luma_beta_offset_div2"] = reader.read_signed_exp_golomb()
                sh["sh_luma_tc_offset_div2"] = reader.read_signed_exp_golomb()
                if pps.get("pps_chroma_tool_offsets_present_flag"):
                    sh["sh_cb_beta_offset_div2"] = reader.read_signed_exp_golomb()
                    sh["sh_cb_tc_offset_div2"] = reader.read_signed_exp_golomb()
                    sh["sh_cr_beta_offset_div2"] = reader.read_signed_exp_golomb()
                    sh["sh_cr_tc_offset_div2"] = reader.read_signed_exp_golomb()

    # dep_quant
    if sps.get("sps_dep_quant_enabled_flag"):
        sh["sh_dep_quant_used_flag"] = reader.read_bits(1)

    # sign_data_hiding
    if sps.get("sps_sign_data_hiding_enabled_flag") and not sh.get("sh_dep_quant_used_flag"):
        sh["sh_sign_data_hiding_used_flag"] = reader.read_bits(1)

    # ts_residual_coding_disabled
    if sps.get("sps_transform_skip_enabled_flag") and not sh.get("sh_dep_quant_used_flag") and not sh.get("sh_sign_data_hiding_used_flag"):
        sh["sh_ts_residual_coding_disabled_flag"] = reader.read_bits(1)

    # Stop here — slice_data() follows

    return sh
