"""H.264 bitstream parser - top-level dispatcher.

Maintains SPS/PPS state and dispatches NAL units to sub-parsers.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.nal import NalUnit, parse_h264_nal_header, find_nal_units
from stream_analysis.h264.definitions import NalUnitType, NAL_TYPE_NAMES
from stream_analysis.h264.sps import parse_sps
from stream_analysis.h264.pps import parse_pps
from stream_analysis.h264.sei import parse_sei
from stream_analysis.h264.slice_header import parse_slice_header
from stream_analysis.h264.other import parse_aud, parse_filler_data, parse_end_of_sequence, parse_end_of_stream


class H264Parser:
    """Parses H.264 Annex B bitstreams."""

    def __init__(self):
        self._sps_map: dict[int, dict] = {}
        self._pps_map: dict[int, dict] = {}

    def parse_stream(self, data: bytes) -> list[dict]:
        """Parse all NAL units in an Annex B byte stream."""
        nal_units = find_nal_units(data)
        results = []
        for i, nal in enumerate(nal_units):
            result = self.parse_nal_unit(nal, index=i)
            results.append(result)
        return results

    def parse_nal_unit(self, nal: NalUnit, index: int = 0) -> dict:
        """Parse a single NAL unit and return its syntax elements."""
        header = parse_h264_nal_header(nal.raw_data)

        result = {
            "index": index,
            "offset": nal.offset,
            "size": nal.size,
            "start_code_length": nal.start_code_len,
            "forbidden_zero_bit": header.forbidden_zero_bit,
            "nal_ref_idc": header.nal_ref_idc,
            "nal_unit_type": header.nal_unit_type,
            "nal_unit_type_name": NAL_TYPE_NAMES.get(header.nal_unit_type, f"unknown({header.nal_unit_type})"),
        }

        # Create a BitReader for the RBSP data, skipping the 1-byte NAL header
        rbsp = nal.rbsp_data[1:]
        reader = BitReader(rbsp)

        try:
            syntax = self._dispatch_parse(reader, header, nal)
            if syntax is not None:
                result["syntax_elements"] = syntax
        except (EOFError, ValueError, IndexError) as e:
            result["_error"] = f"Parse error: {e}"

        return result

    def _dispatch_parse(self, reader: BitReader, header, nal: NalUnit) -> dict | None:
        """Dispatch to the appropriate sub-parser based on NAL unit type."""
        nal_type = header.nal_unit_type

        if nal_type == NalUnitType.SPS:
            sps = parse_sps(reader)
            sps_id = sps.get("seq_parameter_set_id", 0)
            self._sps_map[sps_id] = sps
            return sps

        elif nal_type == NalUnitType.PPS:
            pps = parse_pps(reader, self._sps_map)
            pps_id = pps.get("pic_parameter_set_id", 0)
            self._pps_map[pps_id] = pps
            return pps

        elif nal_type == NalUnitType.SEI:
            messages = parse_sei(reader)
            return {"sei_messages": messages}

        elif nal_type in (NalUnitType.SLICE_NON_IDR, NalUnitType.SLICE_IDR,
                          NalUnitType.SLICE_PART_A):
            return parse_slice_header(
                reader, nal_type, header.nal_ref_idc,
                self._sps_map, self._pps_map
            )

        elif nal_type == NalUnitType.AUD:
            return parse_aud(reader)

        elif nal_type == NalUnitType.FILLER_DATA:
            return parse_filler_data(nal.raw_data)

        elif nal_type == NalUnitType.END_OF_SEQUENCE:
            return parse_end_of_sequence()

        elif nal_type == NalUnitType.END_OF_STREAM:
            return parse_end_of_stream()

        elif nal_type == NalUnitType.SPS_EXTENSION:
            return {"note": "SPS extension present"}

        else:
            return None
