"""Auto-detect file type (container vs raw bitstream) and codec type.

Uses ffprobe for container detection. Falls back to bitstream header
analysis for raw streams.
"""

import json
import subprocess


def detect_file_info(filepath: str) -> dict:
    """Detect file type and codec.

    Returns dict with:
        - file_type: "container" or "raw"
        - codec: "h264" or "h265" or None
        - stream_index: video stream index (for containers)
        - ffprobe_streams: full stream info (for containers)
    """
    # Try ffprobe first
    probe = _probe_with_ffprobe(filepath)
    if probe is not None:
        streams = probe.get("streams", [])
        for stream in streams:
            codec = stream.get("codec_name", "")
            if codec in ("h264", "hevc", "vvc"):
                codec_map = {"h264": "h264", "hevc": "h265", "vvc": "h266"}
                return {
                    "file_type": "container",
                    "codec": codec_map[codec],
                    "stream_index": stream.get("index", 0),
                    "ffprobe_streams": streams,
                }

    # ffprobe couldn't identify it as a container — try as raw bitstream
    codec = _detect_raw_codec(filepath)
    if codec:
        return {
            "file_type": "raw",
            "codec": codec,
            "stream_index": None,
            "ffprobe_streams": None,
        }

    return {
        "file_type": "unknown",
        "codec": None,
        "stream_index": None,
        "ffprobe_streams": None,
    }


def _probe_with_ffprobe(filepath: str) -> dict | None:
    """Run ffprobe and return parsed JSON, or None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                filepath,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None


def _detect_raw_codec(filepath: str) -> str | None:
    """Detect codec type from raw bitstream by examining NAL headers.

    Returns "h264", "h265", "h266", or None.
    """
    try:
        with open(filepath, "rb") as f:
            header = f.read(64)
    except (IOError, OSError):
        return None

    # Find first start code
    start = _find_first_start_code(header)
    if start is None:
        return None

    nal_byte = header[start]

    # H.264: 1-byte NAL header, SPS type=7 → byte & 0x1F == 7
    # Common first NAL: 0x67 (SPS), 0x27 (SPS with different nal_ref_idc)
    h264_type = nal_byte & 0x1F
    if h264_type == 7:  # SPS
        return "h264"

    # H.265: 2-byte NAL header, VPS type=32 → (byte>>1) & 0x3F == 32
    # Common first NAL: 0x40 (VPS)
    h265_type = (nal_byte >> 1) & 0x3F
    if h265_type == 32:  # VPS
        return "h265"

    # H.266: 2-byte NAL header, nal_unit_type in byte1
    # byte0: forbidden(1)+reserved(1)+layer_id(6), byte1: nal_type(5)+tid(3)
    # VPS=14, SPS=15, AUD=20
    if start + 1 < len(header):
        h266_type = (header[start + 1] >> 3) & 0x1F
        # H.266 NAL: byte0 should have forbidden=0, reserved=0
        if (nal_byte & 0xC0) == 0:  # forbidden=0, reserved=0
            if h266_type in (14, 15, 20):  # VPS, SPS, AUD
                return "h266"

    # Also check for H.264 AUD (type=9) or H.265 AUD (type=35)
    if h264_type == 9:
        return "h264"
    if h265_type == 35:
        return "h265"

    # Try to use ffprobe on raw stream with explicit format
    for fmt, codec in [("h264", "h264"), ("hevc", "h265"), ("vvc", "h266")]:
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-f", fmt,
                    "-print_format", "json",
                    "-show_streams",
                    filepath,
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                if data.get("streams"):
                    return codec
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

    return None


def _find_first_start_code(data: bytes) -> int | None:
    """Find the byte position immediately after the first start code."""
    for i in range(len(data) - 3):
        if data[i] == 0 and data[i + 1] == 0:
            if data[i + 2] == 1:
                return i + 3
            if data[i + 2] == 0 and i + 3 < len(data) and data[i + 3] == 1:
                return i + 4
    return None
