"""CSV output writer for bitstream analysis results."""

import csv
import io
import sys


def write_csv_summary(nal_results: list[dict], output_path: str) -> None:
    """Write NAL unit summary as CSV.

    Fixed columns: index, offset, size, nal_type, type_name, key_info
    """
    fieldnames = ["index", "offset", "size", "nal_unit_type", "nal_unit_type_name", "key_info"]

    rows = []
    for r in nal_results:
        row = {
            "index": r["index"],
            "offset": r["offset"],
            "size": r["size"],
            "nal_unit_type": r["nal_unit_type"],
            "nal_unit_type_name": r["nal_unit_type_name"],
            "key_info": _build_key_info(r),
        }
        rows.append(row)

    _write_csv(fieldnames, rows, output_path)


def write_csv_full(nal_results: list[dict], output_path: str) -> None:
    """Write all NAL unit fields as CSV.

    All syntax element keys are flattened into columns.
    """
    # Collect all possible keys
    base_keys = ["index", "offset", "size", "nal_unit_type", "nal_unit_type_name"]
    syntax_keys = set()

    for r in nal_results:
        se = r.get("syntax_elements", {})
        for k, v in se.items():
            if not isinstance(v, (dict, list)):
                syntax_keys.add(k)

    fieldnames = base_keys + sorted(syntax_keys)

    rows = []
    for r in nal_results:
        row = {k: r.get(k, "") for k in base_keys}
        se = r.get("syntax_elements", {})
        for k in syntax_keys:
            v = se.get(k, "")
            if isinstance(v, (dict, list)):
                v = ""
            row[k] = v
        rows.append(row)

    _write_csv(fieldnames, rows, output_path)


def write_csv_frames(frames: list[dict], output_path: str) -> None:
    """Write frame-level decode/display order as CSV."""
    if not frames:
        return

    fieldnames = [
        "decode_order", "display_order",
        "pict_type", "key_frame",
        "pts", "pts_time",
        "dts", "dts_time",
        "coded_picture_number", "display_picture_number",
    ]

    rows = []
    for f in frames:
        row = {k: f.get(k, "") for k in fieldnames}
        rows.append(row)

    _write_csv(fieldnames, rows, output_path)


def _write_csv(fieldnames: list[str], rows: list[dict], output_path: str) -> None:
    """Write rows to CSV file or stdout."""
    if output_path == "-":
        writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    else:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)


def _build_key_info(nal_result: dict) -> str:
    """Build a compact human-readable summary string for a NAL unit."""
    codec = nal_result.get("codec", "")
    se = nal_result.get("syntax_elements", {})
    nal_type = nal_result.get("nal_unit_type")

    if codec == "h264":
        return _build_key_info_h264(nal_type, se, nal_result)
    elif codec == "h265":
        return _build_key_info_h265(nal_type, se, nal_result)
    elif codec == "h266":
        return _build_key_info_h266(nal_type, se, nal_result)

    # Fallback for legacy results without codec field (treat as before)
    return _build_key_info_legacy(nal_type, se, nal_result)


def _build_key_info_h264(nal_type: int, se: dict, nal_result: dict) -> str:
    if nal_type == 7:  # SPS
        parts = []
        if "profile_idc" in se:
            parts.append(f"profile={se['profile_idc']}({se.get('profile_name', '')})")
        if "level" in se:
            parts.append(f"level={se['level']}")
        if "derived_width" in se:
            parts.append(f"{se['derived_width']}x{se['derived_height']}")
        if "chroma_format_idc" in se:
            chroma_names = {0: "4:0:0", 1: "4:2:0", 2: "4:2:2", 3: "4:4:4"}
            parts.append(f"chroma={chroma_names.get(se['chroma_format_idc'], '?')}")
        bit_depth = 8 + se.get("bit_depth_luma_minus8", 0)
        if bit_depth != 8:
            parts.append(f"{bit_depth}bit")
        return " ".join(parts)

    if nal_type == 8:  # PPS
        parts = [f"pps_id={se.get('pic_parameter_set_id', '?')}"]
        if "entropy_coding_mode" in se:
            parts.append(se["entropy_coding_mode"])
        return " ".join(parts)

    if nal_type in (1, 2, 3, 4, 5):  # Slice
        parts = [f"type={se.get('slice_type_name', '?')}"]
        if "frame_num" in se:
            parts.append(f"frame_num={se['frame_num']}")
        if "derived_slice_qp" in se:
            parts.append(f"QP={se['derived_slice_qp']}")
        return " ".join(parts)

    if nal_type == 6:  # SEI
        msgs = se.get("sei_messages", [])
        return ", ".join(m.get("payload_type_name", "?") for m in msgs)

    if nal_type == 9:  # AUD
        return se.get("primary_pic_type_name", "")

    if "_error" in nal_result:
        return f"ERROR: {nal_result['_error']}"
    return ""


def _build_key_info_h265(nal_type: int, se: dict, nal_result: dict) -> str:
    if nal_type == 32:  # VPS
        ptl = se.get("profile_tier_level", {})
        parts = []
        if "general_profile_idc" in ptl:
            parts.append(f"profile={ptl['general_profile_idc']}({ptl.get('general_profile_name', '')})")
        if "general_level" in ptl:
            parts.append(f"level={ptl['general_level']}")
        return " ".join(parts)

    if nal_type == 33:  # SPS
        parts = []
        if "derived_width" in se:
            parts.append(f"{se['derived_width']}x{se['derived_height']}")
        if "chroma_format_idc" in se:
            chroma_names = {0: "4:0:0", 1: "4:2:0", 2: "4:2:2", 3: "4:4:4"}
            parts.append(f"chroma={chroma_names.get(se['chroma_format_idc'], '?')}")
        bit_depth = 8 + se.get("bit_depth_luma_minus8", 0)
        if bit_depth != 8:
            parts.append(f"{bit_depth}bit")
        return " ".join(parts)

    if nal_type == 34:  # PPS
        parts = [f"pps_id={se.get('pps_pic_parameter_set_id', '?')}"]
        if se.get("tiles_enabled_flag"):
            cols = se.get("num_tile_columns_minus1", 0) + 1
            rows_ = se.get("num_tile_rows_minus1", 0) + 1
            parts.append(f"tiles={cols}x{rows_}")
        return " ".join(parts)

    if nal_type in (39, 40):  # SEI
        msgs = se.get("sei_messages", [])
        return ", ".join(m.get("payload_type_name", "?") for m in msgs)

    if nal_type == 35:  # AUD
        return se.get("pic_type_name", "")

    # VCL (slice)
    if nal_type <= 31:
        parts = [f"type={se.get('slice_type_name', '?')}"]
        if "derived_slice_qp" in se:
            parts.append(f"QP={se['derived_slice_qp']}")
        if "slice_pic_order_cnt_lsb" in se:
            parts.append(f"poc_lsb={se['slice_pic_order_cnt_lsb']}")
        return " ".join(parts)

    if "_error" in nal_result:
        return f"ERROR: {nal_result['_error']}"
    return ""


def _build_key_info_h266(nal_type: int, se: dict, nal_result: dict) -> str:
    if nal_type == 14:  # VPS
        ptls = se.get("profile_tier_levels", [])
        if ptls:
            ptl = ptls[0]
            parts = []
            if "general_profile_idc" in ptl:
                parts.append(f"profile={ptl['general_profile_idc']}({ptl.get('general_profile_name', '')})")
            if "general_level" in ptl:
                parts.append(f"level={ptl['general_level']}")
            return " ".join(parts)
        return ""

    if nal_type == 15:  # SPS
        parts = []
        if "derived_width" in se:
            parts.append(f"{se['derived_width']}x{se['derived_height']}")
        if "sps_chroma_format_idc" in se:
            chroma_names = {0: "4:0:0", 1: "4:2:0", 2: "4:2:2", 3: "4:4:4"}
            parts.append(f"chroma={chroma_names.get(se['sps_chroma_format_idc'], '?')}")
        if "derived_bit_depth" in se and se["derived_bit_depth"] != 8:
            parts.append(f"{se['derived_bit_depth']}bit")
        return " ".join(parts)

    if nal_type == 16:  # PPS
        parts = [f"pps_id={se.get('pps_pic_parameter_set_id', '?')}"]
        w = se.get("pps_pic_width_in_luma_samples")
        h = se.get("pps_pic_height_in_luma_samples")
        if w and h:
            parts.append(f"{w}x{h}")
        num_tiles = se.get("derived_num_tiles_in_pic", 1)
        if num_tiles > 1:
            parts.append(f"tiles={se.get('derived_num_tile_columns', '?')}x{se.get('derived_num_tile_rows', '?')}")
        return " ".join(parts)

    if nal_type in (17, 18):  # APS
        parts = [se.get("aps_params_type_name", "?")]
        parts.append(f"id={se.get('aps_adaptation_parameter_set_id', '?')}")
        return " ".join(parts)

    if nal_type == 19:  # PH
        parts = []
        if "ph_pic_order_cnt_lsb" in se:
            parts.append(f"poc_lsb={se['ph_pic_order_cnt_lsb']}")
        if se.get("ph_gdr_pic_flag"):
            parts.append("GDR")
        if se.get("ph_gdr_or_irap_pic_flag") and not se.get("ph_gdr_pic_flag"):
            parts.append("IRAP")
        return " ".join(parts)

    if nal_type in (23, 24):  # SEI
        msgs = se.get("sei_messages", [])
        return ", ".join(m.get("payload_type_name", "?") for m in msgs)

    if nal_type == 20:  # AUD
        return se.get("pic_type_name", "")

    if nal_type == 13:  # DCI
        return f"num_ptls={se.get('dci_num_ptls_minus1', 0) + 1}"

    if nal_type == 12:  # OPI
        return ""

    # VCL (slice, types 0-11)
    if nal_type <= 11:
        parts = [f"type={se.get('slice_type_name', '?')}"]
        if "derived_slice_qp" in se:
            parts.append(f"QP={se['derived_slice_qp']}")
        ph = se.get("picture_header", {})
        if "ph_pic_order_cnt_lsb" in ph:
            parts.append(f"poc_lsb={ph['ph_pic_order_cnt_lsb']}")
        return " ".join(parts)

    if "_error" in nal_result:
        return f"ERROR: {nal_result['_error']}"
    return ""


def _build_key_info_legacy(nal_type: int, se: dict, nal_result: dict) -> str:
    """Fallback for results without a codec field (backwards compatibility)."""
    # Try H.264 first based on type number patterns
    if nal_type == 7:
        return _build_key_info_h264(nal_type, se, nal_result)
    if nal_type == 8:
        return _build_key_info_h264(nal_type, se, nal_result)
    if nal_type in (1, 2, 3, 4, 5):
        return _build_key_info_h264(nal_type, se, nal_result)
    if nal_type == 6:
        return _build_key_info_h264(nal_type, se, nal_result)
    if nal_type == 9:
        return _build_key_info_h264(nal_type, se, nal_result)
    # H.265
    if nal_type >= 32:
        return _build_key_info_h265(nal_type, se, nal_result)
    if nal_type <= 31:
        return _build_key_info_h265(nal_type, se, nal_result)
    if "_error" in nal_result:
        return f"ERROR: {nal_result['_error']}"
    return ""
