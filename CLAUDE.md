# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`stream-analysis` parses every NAL unit's **syntax elements** (not slice
data) from H.264, H.265, and H.266/VVC bitstreams and emits JSON or CSV
plus frame-level decode/display order info via ffprobe.

Python 3.10+, **stdlib only** for the parser. FFmpeg/ffprobe is required
externally (used to demux containers and to get frame timing) — it is not
a Python dependency.

User-facing docs: `README.md`, `FFmpeg-Build-Guide.md`. This file is for
**changing the code**.

## Commands

```bash
# install (macOS Homebrew Python needs --break-system-packages)
pip3 install --break-system-packages -e .
pip install -e .                  # everywhere else

# run without installing
python3 -m stream_analysis input.mp4 -o out.json

# installed entry point
stream-analysis input.264 -o summary.csv
stream-analysis input.mkv --format csv-full --stream 1 -o full.csv
stream-analysis input.bin --codec h266 -o out.json   # force codec

# tests
python3 -m pytest tests/ -q
python3 -m pytest tests/test_bitreader.py::test_name -q
```

The CLI auto-detects codec from container/extension; pass `--codec` to
force when detection fails (e.g. raw bitstream in an unfamiliar extension).

## Architecture

Each pipeline stage is a single small module — there's no class hierarchy
or registry to wire into.

```
stream_analysis/
├── cli.py             argparse + the orchestration in main(): detect → demux → parse → write
├── __main__.py        delegates to cli.main()
├── detect.py          codec + container detection from header bytes + extension
├── demux.py           ffmpeg-cli subprocess: container → raw Annex-B bitstream
├── frame_info.py      ffprobe -show_frames → decode/display order, PTS/DTS, pict_type
├── nal.py             Annex-B start-code scanner; EPB (0x000003) removal
├── bitreader.py       bit-level reader + Exp-Golomb (ue/se) — the foundation everything builds on
├── h264/ h265/ h266/  per-codec parsers (see below)
└── output/  json_writer.py · csv_writer.py    final serialization
```

Each codec subpackage has the same shape:

```
h26x/
├── parser.py            top-level parse_stream(data) → list of NAL dicts
├── definitions.py       NAL type enums + name tables
├── sps.py · pps.py      sequence/picture parameter sets
├── vps.py               (h265, h266) video parameter set
├── slice_header.py      slice header parsing (no slice data)
├── sei.py               SEI message dispatching
├── other.py             AUD, EOS/EOB, filler, etc.
├── profile_tier_level.py (h265, h266)
├── aps.py               (h266 only) ALF / LMCS / Scaling List APS
└── picture_header.py    (h266 only) picture header NAL
```

`cli.py:main()` is the orchestrator — it's the only file that knows about
all four codecs and three output formats. Adding a NAL type or a syntax
element is a localized edit inside one `h26x/*.py` file.

## Non-obvious gotchas

**EPB removal happens in `nal.py`, before parsing.** Don't re-remove
emulation prevention bytes inside the per-codec parsers. The bitstream
handed to `bitreader.BitReader` is already EPB-stripped.

**`bitreader.py` is the contract.** All three codecs build on it.
`read_ue()` / `read_se()` are Exp-Golomb (unsigned/signed). If you spot a
field decoding off-by-one, check whether the spec says "ue(v)" vs "u(v)"
first — they're easy to swap.

**Containers go through `demux.extract_raw_bitstream()`.** This shells out
to `ffmpeg -bsf h264_mp4toannexb` (or h265/h266 equivalent). If `ffmpeg`
is missing or too old for VVC, the demux silently fails — the CLI prints
the codec but parsing 0 NALs is the symptom.

**H.266/VVC support is FFmpeg-version-sensitive.** Decoding (ffprobe)
needs FFmpeg n7.0+ (native VVC decoder). Encoding test fixtures need
FFmpeg master + libvvenc. See `FFmpeg-Build-Guide.md` before touching VVC
fixtures.

**Frame info is best-effort.** `frame_info.get_frame_info()` is wrapped in
a try/except in `cli.py` because some odd containers or raw streams have
no probe output. When that branch fails, `--format csv-frames` exits with
an error; JSON output simply omits the `frames` key.

**SPS-derived resolution is opportunistic.** `cli.py` walks NAL results
looking for the first `derived_width` key. If the SPS parser doesn't
populate it (e.g. unusual `frame_crop_*_offset` math), `stream_info` will
lack width/height. Fix the SPS parser, not the CLI.

## Conventions for changes

- **No Python deps.** Stdlib only is a hard rule; do not add `bitstring`,
  `construct`, `pydantic`, etc. The whole point is "drop in and run."
- A new NAL type: add the enum/name in `h26x/definitions.py`, create or
  extend the relevant `h26x/<thing>.py`, then dispatch from
  `h26x/parser.py`. Mirror the conventions of the existing files
  (return a dict of `{field_name: value}`, no classes).
- New output format: extend `--format` choices in `cli.py` and add a
  writer under `output/`. Keep writers free of parsing logic — they
  receive already-parsed dicts.
- Field names in syntax-element dicts should mirror the spec (`pic_width_in_luma_samples`,
  not `width`). Derived/convenience fields use a `derived_` prefix.
- Tests live in `tests/` and cover the foundation (`bitreader`, `nal`).
  When adding parsers, prefer adding fixture-based round-trip tests over
  unit-testing every helper.

## See also

- `README.md` — full feature matrix per codec, output examples.
- `Setup-macOS.md` — Homebrew install path on this machine (ffmpeg + python@3.13), plus snags hit.
- `FFmpeg-Build-Guide.md` — building FFmpeg with libvvenc for H.266 *encoding* (analysis doesn't need this).
