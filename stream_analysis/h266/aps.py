"""H.266 Adaptation Parameter Set (APS) parser.

Follows ITU-T H.266 Section 7.3.2.5.
APS is new in H.266 and carries ALF, LMCS, and Scaling List parameters.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.h266.definitions import APS_PARAMS_TYPE_NAMES


def parse_aps(reader: BitReader) -> dict:
    """Parse an H.266 APS from RBSP data (after 2-byte NAL header)."""
    aps = {}

    aps["aps_params_type"] = reader.read_bits(3)
    aps["aps_params_type_name"] = APS_PARAMS_TYPE_NAMES.get(
        aps["aps_params_type"], f"unknown({aps['aps_params_type']})")
    aps["aps_adaptation_parameter_set_id"] = reader.read_bits(5)
    aps["aps_chroma_present_flag"] = reader.read_bits(1)

    if aps["aps_params_type"] == 0:  # ALF
        aps["alf_data"] = _parse_alf_data(reader, aps)
    elif aps["aps_params_type"] == 1:  # LMCS
        aps["lmcs_data"] = _parse_lmcs_data(reader, aps)
    elif aps["aps_params_type"] == 2:  # Scaling List
        aps["scaling_list_data"] = _parse_scaling_list_data(reader, aps)

    aps["aps_extension_flag"] = reader.read_bits(1)

    return aps


def _parse_alf_data(reader: BitReader, aps: dict) -> dict:
    """Parse ALF (Adaptive Loop Filter) data."""
    alf = {}

    alf["alf_luma_filter_signal_flag"] = reader.read_bits(1)

    if aps["aps_chroma_present_flag"]:
        alf["alf_chroma_filter_signal_flag"] = reader.read_bits(1)
    else:
        alf["alf_chroma_filter_signal_flag"] = 0

    alf["alf_cc_cb_filter_signal_flag"] = 0
    alf["alf_cc_cr_filter_signal_flag"] = 0
    if aps["aps_chroma_present_flag"]:
        alf["alf_cc_cb_filter_signal_flag"] = reader.read_bits(1)
        alf["alf_cc_cr_filter_signal_flag"] = reader.read_bits(1)

    if alf["alf_luma_filter_signal_flag"]:
        alf["alf_luma_clip_flag"] = reader.read_bits(1)
        alf["alf_luma_num_filters_signalled_minus1"] = reader.read_unsigned_exp_golomb()
        num_filters = alf["alf_luma_num_filters_signalled_minus1"] + 1

        if num_filters > 1:
            alf["alf_luma_coeff_delta_idx"] = []
            bits_needed = max(1, (num_filters - 1).bit_length())
            for _ in range(25):  # NumAlfFilters = 25
                alf["alf_luma_coeff_delta_idx"].append(reader.read_bits(bits_needed))

        # Luma filter coefficients
        alf["alf_luma_filters"] = []
        for i in range(num_filters):
            filt = {}
            filt["coefficients"] = []
            for j in range(12):  # 12 coefficients per filter
                filt["coefficients"].append(reader.read_unsigned_exp_golomb())
            if alf["alf_luma_clip_flag"]:
                filt["clip_indices"] = []
                for j in range(12):
                    filt["clip_indices"].append(reader.read_bits(2))
            alf["alf_luma_filters"].append(filt)

    if alf.get("alf_chroma_filter_signal_flag"):
        alf["alf_chroma_clip_flag"] = reader.read_bits(1)
        alf["alf_chroma_num_alt_filters_minus1"] = reader.read_unsigned_exp_golomb()
        alf["alf_chroma_filters"] = []
        for i in range(alf["alf_chroma_num_alt_filters_minus1"] + 1):
            filt = {"coefficients": []}
            for j in range(6):  # 6 chroma coefficients
                filt["coefficients"].append(reader.read_unsigned_exp_golomb())
            if alf["alf_chroma_clip_flag"]:
                filt["clip_indices"] = []
                for j in range(6):
                    filt["clip_indices"].append(reader.read_bits(2))
            alf["alf_chroma_filters"].append(filt)

    if alf.get("alf_cc_cb_filter_signal_flag"):
        alf["alf_cc_cb_filters_signalled_minus1"] = reader.read_unsigned_exp_golomb()
        alf["alf_cc_cb_filters"] = []
        for _ in range(alf["alf_cc_cb_filters_signalled_minus1"] + 1):
            coeffs = []
            for j in range(7):
                coeffs.append(reader.read_bits(3))  # mapped code
            alf["alf_cc_cb_filters"].append(coeffs)

    if alf.get("alf_cc_cr_filter_signal_flag"):
        alf["alf_cc_cr_filters_signalled_minus1"] = reader.read_unsigned_exp_golomb()
        alf["alf_cc_cr_filters"] = []
        for _ in range(alf["alf_cc_cr_filters_signalled_minus1"] + 1):
            coeffs = []
            for j in range(7):
                coeffs.append(reader.read_bits(3))
            alf["alf_cc_cr_filters"].append(coeffs)

    return alf


def _parse_lmcs_data(reader: BitReader, aps: dict) -> dict:
    """Parse LMCS (Luma Mapping with Chroma Scaling) data."""
    lmcs = {}

    lmcs["lmcs_min_bin_idx"] = reader.read_unsigned_exp_golomb()
    lmcs["lmcs_delta_max_bin_idx"] = reader.read_unsigned_exp_golomb()
    lmcs["lmcs_delta_cw_prec_minus1"] = reader.read_unsigned_exp_golomb()

    prec = lmcs["lmcs_delta_cw_prec_minus1"] + 1
    max_bin_idx = 15 - lmcs["lmcs_delta_max_bin_idx"]

    lmcs["lmcs_delta_abs_cw"] = []
    lmcs["lmcs_delta_sign_cw_flag"] = []
    for i in range(lmcs["lmcs_min_bin_idx"], max_bin_idx + 1):
        abs_cw = reader.read_bits(prec)
        lmcs["lmcs_delta_abs_cw"].append(abs_cw)
        if abs_cw > 0:
            lmcs["lmcs_delta_sign_cw_flag"].append(reader.read_bits(1))
        else:
            lmcs["lmcs_delta_sign_cw_flag"].append(0)

    if aps["aps_chroma_present_flag"]:
        lmcs["lmcs_delta_abs_crs"] = reader.read_bits(3)
        if lmcs["lmcs_delta_abs_crs"] > 0:
            lmcs["lmcs_delta_sign_crs_flag"] = reader.read_bits(1)

    return lmcs


def _parse_scaling_list_data(reader: BitReader, aps: dict) -> dict:
    """Parse Scaling List data."""
    sl = {}
    sl["scaling_lists"] = []

    # 28 scaling lists in H.266
    for sl_id in range(28):
        entry = {"id": sl_id}
        entry["scaling_list_copy_mode_flag"] = reader.read_bits(1)

        if not entry["scaling_list_copy_mode_flag"]:
            entry["scaling_list_pred_mode_flag"] = reader.read_bits(1)

        if (not entry["scaling_list_copy_mode_flag"] and
            entry.get("scaling_list_pred_mode_flag")) or entry["scaling_list_copy_mode_flag"]:
            entry["scaling_list_pred_id_delta"] = reader.read_unsigned_exp_golomb()

        if not entry["scaling_list_copy_mode_flag"]:
            # Determine matrix size from sl_id
            if sl_id < 2:
                mat_size = 2  # 2x2
            elif sl_id < 8:
                mat_size = 4  # 4x4
            elif sl_id < 14:
                mat_size = 8  # 8x8
            else:
                mat_size = 8  # 8x8 (with DC)

            coeff_num = min(64, mat_size * mat_size)

            if sl_id >= 14:  # DC coeff for large matrices
                entry["scaling_list_dc_coef"] = reader.read_signed_exp_golomb()

            if not entry.get("scaling_list_pred_mode_flag", 0):
                entry["coefficients"] = []
                for _ in range(coeff_num):
                    entry["coefficients"].append(reader.read_signed_exp_golomb())

        sl["scaling_lists"].append(entry)

    return sl
