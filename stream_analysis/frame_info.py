"""Frame-level information: decoding order, display order, timestamps.

Uses ffprobe -show_frames to extract per-frame timing and ordering info.
"""

import json
import subprocess


def get_frame_info(filepath: str, stream_index: int = 0) -> list[dict]:
    """Get per-frame decoding/display order info via ffprobe.

    Args:
        filepath: Path to the video file (container or raw).
        stream_index: Video stream index.

    Returns:
        List of frame info dicts, in decoding order.
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-select_streams", f"v:{stream_index}",
        "-show_frames",
        "-show_entries", "frame=coded_picture_number,display_picture_number,"
                         "pict_type,key_frame,pts,pts_time,pkt_dts,pkt_dts_time,"
                         "best_effort_timestamp,best_effort_timestamp_time,width,height",
        "-print_format", "json",
        filepath,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed: {result.stderr}"
        )

    data = json.loads(result.stdout)
    raw_frames = data.get("frames", [])

    frames = []
    for i, f in enumerate(raw_frames):
        frame = {
            "decode_order": i,
            "coded_picture_number": _int_or_none(f.get("coded_picture_number")),
            "display_picture_number": _int_or_none(f.get("display_picture_number")),
            "pict_type": f.get("pict_type", "?"),
            "key_frame": bool(int(f.get("key_frame", 0))),
            "pts": _int_or_none(f.get("pts")),
            "pts_time": f.get("pts_time"),
            "dts": _int_or_none(f.get("pkt_dts")),
            "dts_time": f.get("pkt_dts_time"),
        }

        # Compute display_order from pts (frames sorted by pts)
        frames.append(frame)

    # Compute display_order: sort by pts to get display order
    _compute_display_order(frames)

    return frames


def _compute_display_order(frames: list[dict]) -> None:
    """Compute display_order by sorting frames by PTS."""
    # Create (index, pts) pairs for sorting
    pts_pairs = []
    for i, f in enumerate(frames):
        pts = f.get("pts")
        if pts is None:
            pts = f.get("coded_picture_number")
        if pts is None:
            pts = i
        pts_pairs.append((i, pts))

    # Sort by pts to get display order
    pts_pairs.sort(key=lambda x: x[1])

    # Assign display_order
    for display_idx, (decode_idx, _) in enumerate(pts_pairs):
        frames[decode_idx]["display_order"] = display_idx


def _int_or_none(val) -> int | None:
    """Convert to int, return None if not possible."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
