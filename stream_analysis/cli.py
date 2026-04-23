"""Command-line interface for the stream analysis tool."""

import argparse
import os
import sys

from stream_analysis.detect import detect_file_info
from stream_analysis.demux import extract_raw_bitstream
from stream_analysis.frame_info import get_frame_info
from stream_analysis.h264.parser import H264Parser
from stream_analysis.h265.parser import H265Parser
from stream_analysis.output.json_writer import write_json
from stream_analysis.output.csv_writer import write_csv_summary, write_csv_full, write_csv_frames


def main():
    parser = argparse.ArgumentParser(
        prog="stream-analysis",
        description="H.264/H.265 bitstream syntax element analysis tool",
    )
    parser.add_argument("input", help="Input file (raw bitstream or container)")
    parser.add_argument("-o", "--output", default="-",
                        help="Output file path (default: stdout). "
                             "Format determined by extension: .json or .csv")
    parser.add_argument("--format", choices=["json", "csv", "csv-full", "csv-frames"],
                        default=None,
                        help="Output format (overrides extension detection)")
    parser.add_argument("--stream", type=int, default=0,
                        help="Video stream index for container files (default: 0)")
    parser.add_argument("--codec", choices=["h264", "h265"],
                        default=None,
                        help="Force codec type (auto-detected by default)")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Determine output format
    out_format = args.format
    if out_format is None:
        if args.output == "-":
            out_format = "json"
        elif args.output.endswith(".json"):
            out_format = "json"
        elif args.output.endswith(".csv"):
            out_format = "csv"
        else:
            out_format = "json"

    # Detect file info
    print(f"Analyzing: {args.input}", file=sys.stderr)
    file_info = detect_file_info(args.input)

    codec = args.codec or file_info["codec"]
    if codec is None:
        print("Error: could not detect codec type. Use --codec to specify.", file=sys.stderr)
        sys.exit(1)

    print(f"Codec: {codec.upper()}, File type: {file_info['file_type']}", file=sys.stderr)

    # Get raw bitstream
    if file_info["file_type"] == "container":
        stream_idx = file_info.get("stream_index", args.stream)
        print(f"Extracting bitstream from stream {stream_idx}...", file=sys.stderr)
        data = extract_raw_bitstream(args.input, codec, stream_idx)
    else:
        with open(args.input, "rb") as f:
            data = f.read()

    print(f"Bitstream size: {len(data)} bytes", file=sys.stderr)

    # Parse NAL units
    if codec == "h264":
        stream_parser = H264Parser()
    else:
        stream_parser = H265Parser()

    nal_results = stream_parser.parse_stream(data)
    print(f"Parsed {len(nal_results)} NAL units", file=sys.stderr)

    # Get frame info
    frames = None
    try:
        frames = get_frame_info(args.input, args.stream)
        print(f"Extracted info for {len(frames)} frames", file=sys.stderr)
    except Exception as e:
        print(f"Warning: could not extract frame info: {e}", file=sys.stderr)

    # Build stream info
    stream_info = {
        "file": os.path.basename(args.input),
        "codec": codec.upper(),
        "file_type": file_info["file_type"],
        "total_nal_units": len(nal_results),
        "total_bytes": len(data),
    }
    # Add resolution from SPS
    for r in nal_results:
        se = r.get("syntax_elements", {})
        if "derived_width" in se:
            stream_info["width"] = se["derived_width"]
            stream_info["height"] = se["derived_height"]
            break

    # Write output
    if out_format == "json":
        write_json(stream_info, nal_results, frames, args.output)
    elif out_format == "csv":
        write_csv_summary(nal_results, args.output)
    elif out_format == "csv-full":
        write_csv_full(nal_results, args.output)
    elif out_format == "csv-frames":
        if frames:
            write_csv_frames(frames, args.output)
        else:
            print("Error: no frame info available for csv-frames output", file=sys.stderr)
            sys.exit(1)

    if args.output != "-":
        print(f"Output written to: {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
