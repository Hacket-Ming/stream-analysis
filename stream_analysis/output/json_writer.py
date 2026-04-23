"""JSON output writer for bitstream analysis results."""

import json


def write_json(stream_info: dict, nal_results: list[dict],
               frames: list[dict] | None, output_path: str) -> None:
    """Write analysis results as JSON.

    Args:
        stream_info: Stream metadata (codec, file, etc.)
        nal_results: List of parsed NAL unit dicts.
        frames: Frame-level decode/display order info, or None.
        output_path: Output file path. Use "-" for stdout.
    """
    output = {
        "stream_info": stream_info,
        "nal_units": nal_results,
    }

    if frames:
        output["frames"] = frames

    json_str = json.dumps(output, indent=2, ensure_ascii=False, default=_json_default)

    if output_path == "-":
        print(json_str)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
            f.write("\n")


def _json_default(obj):
    """Handle non-serializable objects."""
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)
