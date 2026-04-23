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
    se = nal_result.get("syntax_elements", {})
    nal_type = nal_result.get("nal_unit_type")

    # H.264 types
    if nal_type == 7:  # H.264 SPS
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

    if nal_type == 8:  # H.264 PPS
        parts = [f"pps_id={se.get('pic_parameter_set_id', '?')}"]
        if "entropy_coding_mode" in se:
            parts.append(se["entropy_coding_mode"])
        return " ".join(parts)

    if nal_type in (1, 2, 3, 4, 5):  # H.264 Slice
        parts = [f"type={se.get('slice_type_name', '?')}"]
        if "frame_num" in se:
            parts.append(f"frame_num={se['frame_num']}")
        if "derived_slice_qp" in se:
            parts.append(f"QP={se['derived_slice_qp']}")
        return " ".join(parts)

    if nal_type == 6:  # H.264 SEI
        msgs = se.get("sei_messages", [])
        return ", ".join(m.get("payload_type_name", "?") for m in msgs)

    if nal_type == 9:  # H.264 AUD
        return se.get("primary_pic_type_name", "")

    # H.265 types
    if nal_type == 32:  # H.265 VPS
        ptl = se.get("profile_tier_level", {})
        parts = []
        if "general_profile_idc" in ptl:
            parts.append(f"profile={ptl['general_profile_idc']}({ptl.get('general_profile_name', '')})")
        if "general_level" in ptl:
            parts.append(f"level={ptl['general_level']}")
        return " ".join(parts)

    if nal_type == 33:  # H.265 SPS
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

    if nal_type == 34:  # H.265 PPS
        parts = [f"pps_id={se.get('pps_pic_parameter_set_id', '?')}"]
        if se.get("tiles_enabled_flag"):
            cols = se.get("num_tile_columns_minus1", 0) + 1
            rows_ = se.get("num_tile_rows_minus1", 0) + 1
            parts.append(f"tiles={cols}x{rows_}")
        return " ".join(parts)

    if nal_type in (39, 40):  # H.265 SEI
        msgs = se.get("sei_messages", [])
        return ", ".join(m.get("payload_type_name", "?") for m in msgs)

    if nal_type == 35:  # H.265 AUD
        return se.get("pic_type_name", "")

    # H.265 VCL (slice)
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
