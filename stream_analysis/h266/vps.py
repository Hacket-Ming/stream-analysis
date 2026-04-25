"""H.266 Video Parameter Set (VPS) parser.

Follows ITU-T H.266 Section 7.3.2.2.
"""

import math
from stream_analysis.bitreader import BitReader
from stream_analysis.h266.profile_tier_level import parse_profile_tier_level


def parse_vps(reader: BitReader) -> dict:
    """Parse an H.266 VPS from RBSP data (after 2-byte NAL header)."""
    vps = {}

    vps["vps_video_parameter_set_id"] = reader.read_bits(4)
    vps["vps_max_layers_minus1"] = reader.read_bits(6)
    vps["vps_max_sublayers_minus1"] = reader.read_bits(3)

    # Default layer order and ptl when single layer or single sublayer
    if vps["vps_max_layers_minus1"] > 0 and vps["vps_max_sublayers_minus1"] > 0:
        vps["vps_default_ptl_dpb_hrd_max_tid_flag"] = reader.read_bits(1)
    else:
        vps["vps_default_ptl_dpb_hrd_max_tid_flag"] = 1

    if vps["vps_max_layers_minus1"] > 0:
        vps["vps_all_independent_layers_flag"] = reader.read_bits(1)
    else:
        vps["vps_all_independent_layers_flag"] = 1

    # Layer IDs and dependencies
    vps["vps_layer_id"] = []
    for i in range(vps["vps_max_layers_minus1"] + 1):
        vps["vps_layer_id"].append(reader.read_bits(6))

    if not vps["vps_all_independent_layers_flag"]:
        vps["layer_dependencies"] = []
        for i in range(1, vps["vps_max_layers_minus1"] + 1):
            vps_independent_layer_flag = reader.read_bits(1)
            dep = {"vps_independent_layer_flag": vps_independent_layer_flag}
            if not vps_independent_layer_flag:
                max_tid = vps["vps_max_sublayers_minus1"]
                dep["vps_max_tid_ref_present_flag"] = reader.read_bits(1)
                dep["direct_ref_layers"] = []
                for j in range(i):
                    direct_dep_flag = reader.read_bits(1)
                    if direct_dep_flag and dep["vps_max_tid_ref_present_flag"]:
                        reader.read_bits(3)  # vps_max_tid_il_ref_pics_plus1
                    dep["direct_ref_layers"].append(direct_dep_flag)
            vps["layer_dependencies"].append(dep)

    # OLS (Output Layer Set) configuration
    if vps["vps_max_layers_minus1"] > 0:
        num_multi_layer_olss = 0  # will be derived
        if vps["vps_max_layers_minus1"] > 1:
            ols_mode_idc_present = not vps["vps_all_independent_layers_flag"]
            if ols_mode_idc_present:
                vps["vps_each_layer_is_an_ols_flag"] = reader.read_bits(1)
            else:
                vps["vps_each_layer_is_an_ols_flag"] = 1 if vps["vps_all_independent_layers_flag"] else 0

            if not vps.get("vps_each_layer_is_an_ols_flag", 1):
                if not vps["vps_all_independent_layers_flag"]:
                    vps["vps_ols_mode_idc"] = reader.read_bits(2)
                else:
                    vps["vps_ols_mode_idc"] = 2

                if vps.get("vps_ols_mode_idc") == 2:
                    vps["vps_num_output_layer_sets_minus2"] = reader.read_bits(8)
                    vps["ols_output_layer_flags"] = []
                    for i in range(vps["vps_num_output_layer_sets_minus2"] + 2):
                        flags = []
                        for j in range(vps["vps_max_layers_minus1"] + 1):
                            flags.append(reader.read_bits(1))
                        vps["ols_output_layer_flags"].append(flags)

        vps["vps_num_ptls_minus1"] = reader.read_bits(8)
    else:
        vps["vps_num_ptls_minus1"] = 0

    # Profile/tier/level
    vps["profile_tier_levels"] = []
    ptl_max_tids = []
    for i in range(vps.get("vps_num_ptls_minus1", 0) + 1):
        if i > 0:
            pt_present_flag = reader.read_bits(1)
        else:
            pt_present_flag = 1

        if not vps.get("vps_default_ptl_dpb_hrd_max_tid_flag", 1):
            max_tid = reader.read_bits(3)
        else:
            max_tid = vps["vps_max_sublayers_minus1"]
        ptl_max_tids.append(max_tid)

        # Byte alignment before PTL
        if reader.bits_remaining() > 0 and not reader.byte_aligned():
            while not reader.byte_aligned():
                reader.read_bits(1)

        ptl = parse_profile_tier_level(reader, bool(pt_present_flag), max_tid)
        vps["profile_tier_levels"].append(ptl)

    # OLS-to-PTL mapping
    if vps["vps_max_layers_minus1"] > 0:
        total_ols = vps.get("vps_num_output_layer_sets_minus2", 0) + 2 if vps.get("vps_ols_mode_idc") == 2 else vps["vps_max_layers_minus1"] + 1
        if vps.get("vps_num_ptls_minus1", 0) > 0 and vps.get("vps_num_ptls_minus1", 0) + 1 != total_ols:
            vps["vps_ols_ptl_idx"] = []
            bits_for_idx = max(1, math.ceil(math.log2(vps["vps_num_ptls_minus1"] + 1))) if vps["vps_num_ptls_minus1"] > 0 else 1
            for _ in range(total_ols):
                vps["vps_ols_ptl_idx"].append(reader.read_bits(bits_for_idx))

    # Timing/HRD info - skip detailed parsing, just record presence
    if not vps.get("vps_each_layer_is_an_ols_flag", 1):
        vps["vps_num_dpb_params_minus1"] = reader.read_unsigned_exp_golomb()
        # Skip detailed DPB/HRD parsing as it's very complex for multi-layer

    return vps
