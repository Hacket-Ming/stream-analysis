"""FFmpeg-based demuxer: extract raw Annex B bitstream from container formats.

Supports any container format that ffmpeg can demux (MP4, FLV, MKV, TS, etc.).
"""

import subprocess


def extract_raw_bitstream(filepath: str, codec: str, stream_index: int = 0) -> bytes:
    """Extract raw Annex B bitstream from a container file.

    Args:
        filepath: Path to the container file.
        codec: "h264" or "h265".
        stream_index: Video stream index.

    Returns:
        Raw Annex B byte stream.
    """
    if codec == "h264":
        bsf = "h264_mp4toannexb"
        output_format = "h264"
    elif codec == "h265":
        bsf = "hevc_mp4toannexb"
        output_format = "hevc"
    elif codec == "h266":
        bsf = "vvc_mp4toannexb"
        output_format = "vvc"
    else:
        raise ValueError(f"Unsupported codec: {codec}")

    cmd = [
        "ffmpeg",
        "-v", "quiet",
        "-i", filepath,
        "-map", f"0:{stream_index}",
        "-c:v", "copy",
        "-bsf:v", bsf,
        "-f", output_format,
        "pipe:1",
    ]

    result = subprocess.run(cmd, capture_output=True, timeout=120)

    if result.returncode != 0:
        # Try without bsf (some formats like TS already have Annex B start codes)
        cmd_no_bsf = [
            "ffmpeg",
            "-v", "quiet",
            "-i", filepath,
            "-map", f"0:{stream_index}",
            "-c:v", "copy",
            "-f", output_format,
            "pipe:1",
        ]
        result = subprocess.run(cmd_no_bsf, capture_output=True, timeout=120)

        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed to extract bitstream: {result.stderr.decode(errors='replace')}"
            )

    return result.stdout
