"""H.266 profile_tier_level() parsing.

Shared by VPS, SPS, and DCI. Follows ITU-T H.266 Section 7.3.3.1.
The H.266 PTL structure differs significantly from H.265.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h266.definitions import PROFILE_NAMES


def parse_profile_tier_level(reader: BitReader, profile_tier_present_flag: bool,
                             max_num_sub_layers_minus1: int) -> dict:
    """Parse profile_tier_level().

    Args:
        reader: BitReader positioned at the start of PTL data.
        profile_tier_present_flag: Whether profile/tier info is present.
        max_num_sub_layers_minus1: Maximum number of sub-layers minus 1.
    """
    ptl = {}

    if profile_tier_present_flag:
        ptl["general_profile_idc"] = reader.read_bits(7)
        ptl["general_profile_name"] = PROFILE_NAMES.get(ptl["general_profile_idc"], "Unknown")
        ptl["general_tier_flag"] = reader.read_bits(1)

    ptl["general_level_idc"] = reader.read_bits(8)
    ptl["general_level"] = f"{ptl['general_level_idc'] / 30:.1f}"

    ptl["ptl_frame_only_constraint_flag"] = reader.read_bits(1)
    ptl["ptl_multilayer_enabled_flag"] = reader.read_bits(1)

    if profile_tier_present_flag:
        ptl["general_constraints_info"] = _parse_general_constraints_info(reader)

    # Sub-layer level presence flags
    sub_layer_level_present = []
    for i in range(max_num_sub_layers_minus1):
        sub_layer_level_present.append(reader.read_bits(1))

    # Byte alignment
    remaining = (max_num_sub_layers_minus1 + 1) % 8
    if remaining > 0:
        for _ in range(8 - remaining):
            reader.read_bits(1)  # ptl_reserved_zero_bit

    # Sub-layer level_idc
    ptl["sub_layer_levels"] = []
    for i in range(max_num_sub_layers_minus1):
        if sub_layer_level_present[i]:
            level_idc = reader.read_bits(8)
            ptl["sub_layer_levels"].append({
                "sub_layer_level_idc": level_idc,
                "sub_layer_level": f"{level_idc / 30:.1f}",
            })
        else:
            ptl["sub_layer_levels"].append({})

    if profile_tier_present_flag:
        ptl["ptl_num_sub_profiles"] = reader.read_unsigned_exp_golomb()
        ptl["general_sub_profile_idcs"] = []
        for _ in range(ptl["ptl_num_sub_profiles"]):
            ptl["general_sub_profile_idcs"].append(reader.read_bits(32))

    return ptl


def _parse_general_constraints_info(reader: BitReader) -> dict:
    """Parse general_constraints_info().

    This contains a large number of constraint flags. We parse the
    gci_present_flag and if present, read all constraint flags.
    """
    gci = {}
    gci["gci_present_flag"] = reader.read_bits(1)

    if gci["gci_present_flag"]:
        # Intra-only constraint
        gci["gci_intra_only_constraint_flag"] = reader.read_bits(1)
        # All layers independent
        gci["gci_all_layers_independent_constraint_flag"] = reader.read_bits(1)
        gci["gci_one_au_only_constraint_flag"] = reader.read_bits(1)

        # Picture format constraints
        gci["gci_sixteen_minus_max_bitdepth_constraint_idc"] = reader.read_bits(4)
        gci["gci_three_minus_max_chroma_format_constraint_idc"] = reader.read_bits(2)

        # Max picture size constraints
        gci["gci_no_mixed_nalu_types_in_pic_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_trail_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_stsa_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_rasl_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_radl_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_idr_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_cra_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_gdr_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_aps_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_idr_rpl_constraint_flag"] = reader.read_bits(1)

        # Tile/slice constraints
        gci["gci_one_tile_per_pic_constraint_flag"] = reader.read_bits(1)
        gci["gci_pic_header_in_slice_header_constraint_flag"] = reader.read_bits(1)
        gci["gci_one_slice_per_pic_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_rectangular_slice_constraint_flag"] = reader.read_bits(1)
        gci["gci_one_slice_per_subpic_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_subpic_info_constraint_flag"] = reader.read_bits(1)

        # Coding tool constraints (many flags)
        gci["gci_three_minus_max_log2_ctu_size_constraint_idc"] = reader.read_bits(2)
        gci["gci_no_partition_constraints_override_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_mtt_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_qtbtt_dual_tree_intra_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_palette_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_ibc_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_isp_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_mrl_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_mip_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_cclm_constraint_flag"] = reader.read_bits(1)

        gci["gci_no_ref_pic_resampling_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_res_change_in_clvs_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_weighted_prediction_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_ref_wraparound_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_temporal_mvp_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_sbtmvp_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_amvr_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_bdof_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_smvd_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_dmvr_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_mmvd_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_affine_motion_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_prof_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_bcw_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_ciip_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_gpm_constraint_flag"] = reader.read_bits(1)

        gci["gci_no_luma_transform_size_64_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_transform_skip_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_bdpcm_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_mts_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_lfnst_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_joint_cbcr_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_sbt_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_act_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_explicit_scaling_list_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_dep_quant_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_sign_data_hiding_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_cu_qp_delta_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_chroma_qp_offset_constraint_flag"] = reader.read_bits(1)

        gci["gci_no_sao_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_alf_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_ccalf_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_lmcs_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_ladf_constraint_flag"] = reader.read_bits(1)
        gci["gci_no_virtual_boundaries_constraint_flag"] = reader.read_bits(1)

        # gci_num_reserved_bits + reserved bits
        gci_num_reserved_bits = reader.read_bits(8)
        if gci_num_reserved_bits > 0:
            reader.skip_bits(gci_num_reserved_bits)

    # Byte alignment
    if not reader.byte_aligned():
        reader.read_bits(1)  # gci_alignment_zero_bit (should be 0)
        while not reader.byte_aligned():
            reader.read_bits(1)  # gci_alignment_zero_bit

    return gci
