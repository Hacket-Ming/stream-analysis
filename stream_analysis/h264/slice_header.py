"""H.264 Slice Header parser.

Follows ITU-T H.264 Section 7.3.3.
Parses all fields up to but NOT including slice_data().
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h264.definitions import SLICE_TYPE_NAMES


def parse_slice_header(reader: BitReader, nal_unit_type: int, nal_ref_idc: int,
                       sps_map: dict, pps_map: dict) -> dict:
    """Parse a slice header from RBSP data (after NAL header byte)."""
    sh = {}

    sh["first_mb_in_slice"] = reader.read_unsigned_exp_golomb()
    sh["slice_type"] = reader.read_unsigned_exp_golomb()
    sh["slice_type_name"] = SLICE_TYPE_NAMES.get(sh["slice_type"], f"unknown({sh['slice_type']})")
    sh["pic_parameter_set_id"] = reader.read_unsigned_exp_golomb()

    # Look up PPS and SPS
    pps = pps_map.get(sh["pic_parameter_set_id"])
    if pps is None:
        sh["_error"] = f"PPS {sh['pic_parameter_set_id']} not found"
        return sh

    sps_id = pps["seq_parameter_set_id"]
    sps = sps_map.get(sps_id)
    if sps is None:
        sh["_error"] = f"SPS {sps_id} not found"
        return sh

    if sps.get("separate_colour_plane_flag") == 1:
        sh["colour_plane_id"] = reader.read_bits(2)

    frame_num_bits = sps["log2_max_frame_num_minus4"] + 4
    sh["frame_num"] = reader.read_bits(frame_num_bits)

    if not sps["frame_mbs_only_flag"]:
        sh["field_pic_flag"] = reader.read_bits(1)
        if sh["field_pic_flag"]:
            sh["bottom_field_flag"] = reader.read_bits(1)

    if nal_unit_type == 5:  # IDR
        sh["idr_pic_id"] = reader.read_unsigned_exp_golomb()

    if sps["pic_order_cnt_type"] == 0:
        poc_lsb_bits = sps["log2_max_pic_order_cnt_lsb_minus4"] + 4
        sh["pic_order_cnt_lsb"] = reader.read_bits(poc_lsb_bits)
        if pps.get("bottom_field_pic_order_in_frame_present_flag") and not sh.get("field_pic_flag", 0):
            sh["delta_pic_order_cnt_bottom"] = reader.read_signed_exp_golomb()

    elif sps["pic_order_cnt_type"] == 1:
        if not sps.get("delta_pic_order_always_zero_flag"):
            sh["delta_pic_order_cnt_0"] = reader.read_signed_exp_golomb()
            if pps.get("bottom_field_pic_order_in_frame_present_flag") and not sh.get("field_pic_flag", 0):
                sh["delta_pic_order_cnt_1"] = reader.read_signed_exp_golomb()

    if pps.get("redundant_pic_cnt_present_flag"):
        sh["redundant_pic_cnt"] = reader.read_unsigned_exp_golomb()

    slice_type = sh["slice_type"] % 5  # Normalize (0-4)

    if slice_type == 1:  # B slice
        sh["direct_spatial_mv_pred_flag"] = reader.read_bits(1)

    if slice_type in (0, 1, 3):  # P, B, SP
        sh["num_ref_idx_active_override_flag"] = reader.read_bits(1)
        if sh["num_ref_idx_active_override_flag"]:
            sh["num_ref_idx_l0_active_minus1"] = reader.read_unsigned_exp_golomb()
            if slice_type == 1:  # B
                sh["num_ref_idx_l1_active_minus1"] = reader.read_unsigned_exp_golomb()

    # ref_pic_list_modification
    _parse_ref_pic_list_modification(reader, sh, slice_type)

    # pred_weight_table
    if (pps.get("weighted_pred_flag") and slice_type in (0, 3)) or \
       (pps.get("weighted_bipred_idc") == 1 and slice_type == 1):
        _parse_pred_weight_table(reader, sh, sps, pps, slice_type)

    # dec_ref_pic_marking
    if nal_ref_idc != 0:
        _parse_dec_ref_pic_marking(reader, sh, nal_unit_type)

    if pps.get("entropy_coding_mode_flag") and slice_type not in (2, 4):  # Not I/SI
        sh["cabac_init_idc"] = reader.read_unsigned_exp_golomb()

    sh["slice_qp_delta"] = reader.read_signed_exp_golomb()
    sh["derived_slice_qp"] = 26 + pps.get("pic_init_qp_minus26", 0) + sh["slice_qp_delta"]

    if slice_type in (3, 4):  # SP, SI
        if slice_type == 3:  # SP
            sh["sp_for_switch_flag"] = reader.read_bits(1)
        sh["slice_qs_delta"] = reader.read_signed_exp_golomb()

    if pps.get("deblocking_filter_control_present_flag"):
        sh["disable_deblocking_filter_idc"] = reader.read_unsigned_exp_golomb()
        if sh["disable_deblocking_filter_idc"] != 1:
            sh["slice_alpha_c0_offset_div2"] = reader.read_signed_exp_golomb()
            sh["slice_beta_offset_div2"] = reader.read_signed_exp_golomb()

    # Stop here - slice_data() follows

    return sh


def _parse_ref_pic_list_modification(reader: BitReader, sh: dict, slice_type: int) -> None:
    """Parse ref_pic_list_modification()."""
    if slice_type != 2 and slice_type != 4:  # Not I, SI
        sh["ref_pic_list_modification_flag_l0"] = reader.read_bits(1)
        if sh["ref_pic_list_modification_flag_l0"]:
            sh["ref_pic_list_modification_l0"] = []
            while True:
                op = reader.read_unsigned_exp_golomb()
                if op == 3:
                    break
                val = reader.read_unsigned_exp_golomb()
                sh["ref_pic_list_modification_l0"].append({"op": op, "val": val})

    if slice_type == 1:  # B
        sh["ref_pic_list_modification_flag_l1"] = reader.read_bits(1)
        if sh["ref_pic_list_modification_flag_l1"]:
            sh["ref_pic_list_modification_l1"] = []
            while True:
                op = reader.read_unsigned_exp_golomb()
                if op == 3:
                    break
                val = reader.read_unsigned_exp_golomb()
                sh["ref_pic_list_modification_l1"].append({"op": op, "val": val})


def _parse_pred_weight_table(reader: BitReader, sh: dict, sps: dict, pps: dict,
                             slice_type: int) -> None:
    """Parse pred_weight_table()."""
    sh["luma_log2_weight_denom"] = reader.read_unsigned_exp_golomb()

    chroma_format_idc = sps.get("chroma_format_idc", 1)
    if chroma_format_idc != 0:
        sh["chroma_log2_weight_denom"] = reader.read_unsigned_exp_golomb()

    num_l0 = sh.get("num_ref_idx_l0_active_minus1",
                     pps.get("num_ref_idx_l0_default_active_minus1", 0)) + 1
    sh["weight_table_l0"] = []
    for _ in range(num_l0):
        entry = {}
        luma_flag = reader.read_bits(1)
        if luma_flag:
            entry["luma_weight"] = reader.read_signed_exp_golomb()
            entry["luma_offset"] = reader.read_signed_exp_golomb()
        if chroma_format_idc != 0:
            chroma_flag = reader.read_bits(1)
            if chroma_flag:
                entry["chroma_weight"] = [reader.read_signed_exp_golomb() for _ in range(2)]
                entry["chroma_offset"] = [reader.read_signed_exp_golomb() for _ in range(2)]
        sh["weight_table_l0"].append(entry)

    if slice_type == 1:  # B
        num_l1 = sh.get("num_ref_idx_l1_active_minus1",
                         pps.get("num_ref_idx_l1_default_active_minus1", 0)) + 1
        sh["weight_table_l1"] = []
        for _ in range(num_l1):
            entry = {}
            luma_flag = reader.read_bits(1)
            if luma_flag:
                entry["luma_weight"] = reader.read_signed_exp_golomb()
                entry["luma_offset"] = reader.read_signed_exp_golomb()
            if chroma_format_idc != 0:
                chroma_flag = reader.read_bits(1)
                if chroma_flag:
                    entry["chroma_weight"] = [reader.read_signed_exp_golomb() for _ in range(2)]
                    entry["chroma_offset"] = [reader.read_signed_exp_golomb() for _ in range(2)]
            sh["weight_table_l1"].append(entry)


def _parse_dec_ref_pic_marking(reader: BitReader, sh: dict, nal_unit_type: int) -> None:
    """Parse dec_ref_pic_marking()."""
    if nal_unit_type == 5:  # IDR
        sh["no_output_of_prior_pics_flag"] = reader.read_bits(1)
        sh["long_term_reference_flag"] = reader.read_bits(1)
    else:
        sh["adaptive_ref_pic_marking_mode_flag"] = reader.read_bits(1)
        if sh["adaptive_ref_pic_marking_mode_flag"]:
            sh["mmco_operations"] = []
            while True:
                op = reader.read_unsigned_exp_golomb()
                if op == 0:
                    break
                entry = {"operation": op}
                if op in (1, 3):
                    entry["difference_of_pic_nums_minus1"] = reader.read_unsigned_exp_golomb()
                if op == 2:
                    entry["long_term_pic_num"] = reader.read_unsigned_exp_golomb()
                if op in (3, 6):
                    entry["long_term_frame_idx"] = reader.read_unsigned_exp_golomb()
                if op == 4:
                    entry["max_long_term_frame_idx_plus1"] = reader.read_unsigned_exp_golomb()
                sh["mmco_operations"].append(entry)
