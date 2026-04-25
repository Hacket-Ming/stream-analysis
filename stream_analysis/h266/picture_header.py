"""H.266 Picture Header (PH) parser.

Follows ITU-T H.266 Section 7.3.2.7.
Picture Header is new in H.266 - it can be a standalone NAL (PH_NUT=19)
or embedded within a slice header.
"""

import math
from stream_analysis.bitreader import BitReader
from stream_analysis.h266.definitions import SLICE_TYPE_NAMES, is_irap, is_idr, is_gdr
from stream_analysis.h266.sps import _parse_ref_pic_list_struct


def parse_picture_header(reader: BitReader, nal_unit_type: int,
                         vps_map: dict, sps_map: dict, pps_map: dict) -> dict:
    """Parse a picture header from RBSP data.

    Can be called from a standalone PH NAL or from within a slice header.
    When called from a standalone PH NAL, nal_unit_type should be 19 (PH_NUT).
    """
    ph = {}

    ph["ph_gdr_or_irap_pic_flag"] = reader.read_bits(1)
    ph["ph_non_ref_pic_flag"] = reader.read_bits(1)

    if ph["ph_gdr_or_irap_pic_flag"]:
        ph["ph_gdr_pic_flag"] = reader.read_bits(1)

    ph["ph_inter_slice_allowed_flag"] = reader.read_bits(1)

    if ph["ph_inter_slice_allowed_flag"]:
        ph["ph_intra_slice_allowed_flag"] = reader.read_bits(1)
    else:
        ph["ph_intra_slice_allowed_flag"] = 1

    ph["ph_pic_parameter_set_id"] = reader.read_unsigned_exp_golomb()

    pps = pps_map.get(ph["ph_pic_parameter_set_id"])
    if pps is None:
        ph["_error"] = f"PPS {ph['ph_pic_parameter_set_id']} not found"
        return ph

    sps_id = pps.get("pps_seq_parameter_set_id", 0)
    sps = sps_map.get(sps_id)
    if sps is None:
        ph["_error"] = f"SPS {sps_id} not found"
        return ph

    # POC
    poc_lsb_bits = sps.get("sps_log2_max_pic_order_cnt_lsb_minus4", 0) + 4
    ph["ph_pic_order_cnt_lsb"] = reader.read_bits(poc_lsb_bits)

    if ph.get("ph_gdr_pic_flag"):
        ph["ph_recovery_poc_cnt"] = reader.read_unsigned_exp_golomb()

    # Extra PH bits
    num_extra_ph_bytes = sps.get("sps_num_extra_ph_bytes", 0)
    extra_ph_bits = sps.get("sps_extra_ph_bit_present_flag", [])
    for i in range(num_extra_ph_bytes * 8):
        if i < len(extra_ph_bits) and extra_ph_bits[i]:
            reader.read_bits(1)  # ph_extra_bit

    if sps.get("sps_poc_msb_cycle_flag"):
        ph["ph_poc_msb_cycle_present_flag"] = reader.read_bits(1)
        if ph["ph_poc_msb_cycle_present_flag"]:
            poc_msb_bits = sps.get("sps_poc_msb_cycle_len_minus1", 0) + 1
            ph["ph_poc_msb_cycle_val"] = reader.read_bits(poc_msb_bits)

    # ALF
    if sps.get("sps_alf_enabled_flag") and pps.get("pps_alf_info_in_ph_flag"):
        ph["ph_alf_enabled_flag"] = reader.read_bits(1)
        if ph["ph_alf_enabled_flag"]:
            ph["ph_num_alf_aps_ids_luma"] = reader.read_bits(3)
            ph["ph_alf_aps_id_luma"] = []
            for _ in range(ph["ph_num_alf_aps_ids_luma"]):
                ph["ph_alf_aps_id_luma"].append(reader.read_bits(3))
            if sps.get("sps_chroma_format_idc", 0) != 0:
                ph["ph_alf_cb_enabled_flag"] = reader.read_bits(1)
                ph["ph_alf_cr_enabled_flag"] = reader.read_bits(1)
            if ph.get("ph_alf_cb_enabled_flag") or ph.get("ph_alf_cr_enabled_flag"):
                ph["ph_alf_aps_id_chroma"] = reader.read_bits(3)
            if sps.get("sps_ccalf_enabled_flag"):
                ph["ph_alf_cc_cb_enabled_flag"] = reader.read_bits(1)
                if ph["ph_alf_cc_cb_enabled_flag"]:
                    ph["ph_alf_cc_cb_aps_id"] = reader.read_bits(3)
                ph["ph_alf_cc_cr_enabled_flag"] = reader.read_bits(1)
                if ph["ph_alf_cc_cr_enabled_flag"]:
                    ph["ph_alf_cc_cr_aps_id"] = reader.read_bits(3)

    # LMCS
    if sps.get("sps_lmcs_enabled_flag"):
        ph["ph_lmcs_enabled_flag"] = reader.read_bits(1)
        if ph["ph_lmcs_enabled_flag"]:
            ph["ph_lmcs_aps_id"] = reader.read_bits(2)
            if sps.get("sps_chroma_format_idc", 0) != 0:
                ph["ph_chroma_residual_scale_flag"] = reader.read_bits(1)

    # Explicit scaling list
    if sps.get("sps_explicit_scaling_list_enabled_flag"):
        ph["ph_explicit_scaling_list_enabled_flag"] = reader.read_bits(1)
        if ph["ph_explicit_scaling_list_enabled_flag"]:
            ph["ph_scaling_list_aps_id"] = reader.read_bits(3)

    # Virtual boundaries
    if sps.get("sps_virtual_boundaries_enabled_flag") and not sps.get("sps_virtual_boundaries_present_flag"):
        ph["ph_virtual_boundaries_present_flag"] = reader.read_bits(1)
        if ph["ph_virtual_boundaries_present_flag"]:
            ph["ph_num_ver_virtual_boundaries"] = reader.read_unsigned_exp_golomb()
            for _ in range(ph["ph_num_ver_virtual_boundaries"]):
                reader.read_unsigned_exp_golomb()  # ph_virtual_boundary_pos_x
            ph["ph_num_hor_virtual_boundaries"] = reader.read_unsigned_exp_golomb()
            for _ in range(ph["ph_num_hor_virtual_boundaries"]):
                reader.read_unsigned_exp_golomb()  # ph_virtual_boundary_pos_y

    # Output flag
    if pps.get("pps_output_flag_present_flag"):
        ph["ph_pic_output_flag"] = reader.read_bits(1)

    # RPL
    if pps.get("pps_rpl_info_in_ph_flag"):
        ph["ref_pic_lists"] = _parse_ref_pic_lists(reader, sps, pps)

    # SAO
    if sps.get("sps_sao_enabled_flag") and pps.get("pps_sao_info_in_ph_flag"):
        ph["ph_sao_luma_enabled_flag"] = reader.read_bits(1)
        if sps.get("sps_chroma_format_idc", 0) != 0:
            ph["ph_sao_chroma_enabled_flag"] = reader.read_bits(1)

    # Deblocking
    if pps.get("pps_deblocking_filter_control_present_flag"):
        if pps.get("pps_deblocking_filter_override_enabled_flag"):
            # Only in PH if pps_dbf_info_in_ph_flag (inferred from PPS context)
            pass

    if ph["ph_inter_slice_allowed_flag"]:
        # Temporal MVP
        if sps.get("sps_temporal_mvp_enabled_flag"):
            ph["ph_temporal_mvp_enabled_flag"] = reader.read_bits(1)
            if ph["ph_temporal_mvp_enabled_flag"] and pps.get("pps_rpl_info_in_ph_flag"):
                if ph.get("ref_pic_lists"):
                    # Check if both lists have entries
                    ph["ph_collocated_from_l0_flag"] = reader.read_bits(1)
                    # collocated_ref_idx if needed
        # Additional inter flags (MMVD, BDOF, DMVR, PROF)
        if sps.get("sps_mmvd_fullpel_only_enabled_flag"):
            ph["ph_mmvd_fullpel_only_flag"] = reader.read_bits(1)

        if sps.get("sps_bdof_control_present_in_ph_flag"):
            ph["ph_bdof_disabled_flag"] = reader.read_bits(1)
        if sps.get("sps_dmvr_control_present_in_ph_flag"):
            ph["ph_dmvr_disabled_flag"] = reader.read_bits(1)
        if sps.get("sps_prof_control_present_in_ph_flag"):
            ph["ph_prof_disabled_flag"] = reader.read_bits(1)

    # QP
    if pps.get("pps_qp_delta_info_in_ph_flag"):
        ph["ph_qp_delta"] = reader.read_signed_exp_golomb()

    return ph


def _parse_ref_pic_lists(reader: BitReader, sps: dict, pps: dict) -> dict:
    """Parse reference picture lists selection in PH or SH."""
    rpl_info = {}

    for i in range(2):
        rpl_list = sps.get("ref_pic_lists", [])
        if i >= len(rpl_list):
            break
        sps_rpls = rpl_list[i]
        num_rpl_in_sps = sps_rpls.get("sps_num_ref_pic_lists", 0)

        if num_rpl_in_sps > 0 and (i == 0 or (i == 1 and pps.get("pps_rpl1_idx_present_flag", 1))):
            rpl_sps_flag = reader.read_bits(1)
            rpl_info[f"rpl_sps_flag_{i}"] = rpl_sps_flag
        else:
            rpl_sps_flag = 0

        if rpl_sps_flag:
            if num_rpl_in_sps > 1 and (i == 0 or (i == 1 and pps.get("pps_rpl1_idx_present_flag", 1))):
                bits_needed = max(1, math.ceil(math.log2(num_rpl_in_sps)))
                rpl_info[f"rpl_idx_{i}"] = reader.read_bits(bits_needed)
        else:
            rpl_info[f"ref_pic_list_struct_{i}"] = _parse_ref_pic_list_struct(
                reader, i, num_rpl_in_sps, sps)

        # LTRP POC LSB values for entries with ltrp_in_header_flag
        poc_lsb_bits = sps.get("sps_log2_max_pic_order_cnt_lsb_minus4", 0) + 4
        rpl_struct = rpl_info.get(f"ref_pic_list_struct_{i}")
        if rpl_struct:
            for entry in rpl_struct.get("entries", []):
                if not entry.get("inter_layer_ref_pic_flag", 0) and not entry.get("st_ref_pic_flag", 1):
                    # Long-term ref with ltrp_in_header
                    if rpl_struct.get("ltrp_in_header_flag", 0):
                        entry["poc_lsb_lt"] = reader.read_bits(poc_lsb_bits)

    return rpl_info
