"""H.265 bitstream parser - top-level dispatcher.

Maintains VPS/SPS/PPS state and dispatches NAL units to sub-parsers.
"""

from stream_analysis.bitreader import BitReader
from stream_analysis.nal import NalUnit, parse_h265_nal_header, find_nal_units
from stream_analysis.h265.definitions import NalUnitType, NAL_TYPE_NAMES, is_vcl
from stream_analysis.h265.vps import parse_vps
from stream_analysis.h265.sps import parse_sps
from stream_analysis.h265.pps import parse_pps
from stream_analysis.h265.sei import parse_sei
from stream_analysis.h265.slice_header import parse_slice_header
from stream_analysis.h265.other import parse_aud, parse_filler_data, parse_eos, parse_eob


class H265Parser:
    """Parses H.265 (HEVC) Annex B bitstreams."""

    def __init__(self):
        self._vps_map: dict[int, dict] = {}
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
        header = parse_h265_nal_header(nal.raw_data)

        result = {
            "index": index,
            "offset": nal.offset,
            "size": nal.size,
            "start_code_length": nal.start_code_len,
            "forbidden_zero_bit": header.forbidden_zero_bit,
            "nal_unit_type": header.nal_unit_type,
            "nal_unit_type_name": NAL_TYPE_NAMES.get(header.nal_unit_type, f"unknown({header.nal_unit_type})"),
            "nuh_layer_id": header.nuh_layer_id,
            "nuh_temporal_id_plus1": header.nuh_temporal_id_plus1,
        }

        # Create a BitReader for the RBSP data, skipping the 2-byte NAL header
        rbsp = nal.rbsp_data[2:]
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

        if nal_type == NalUnitType.VPS:
            vps = parse_vps(reader)
            vps_id = vps.get("vps_video_parameter_set_id", 0)
            self._vps_map[vps_id] = vps
            return vps

        elif nal_type == NalUnitType.SPS:
            sps = parse_sps(reader)
            sps_id = sps.get("sps_seq_parameter_set_id", 0)
            self._sps_map[sps_id] = sps
            return sps

        elif nal_type == NalUnitType.PPS:
            pps = parse_pps(reader, self._sps_map)
            pps_id = pps.get("pps_pic_parameter_set_id", 0)
            self._pps_map[pps_id] = pps
            return pps

        elif nal_type in (NalUnitType.SEI_PREFIX, NalUnitType.SEI_SUFFIX):
            messages = parse_sei(reader)
            return {"sei_messages": messages}

        elif is_vcl(nal_type):
            return parse_slice_header(
                reader, nal_type,
                self._vps_map, self._sps_map, self._pps_map
            )

        elif nal_type == NalUnitType.AUD:
            return parse_aud(reader)

        elif nal_type == NalUnitType.FILLER_DATA:
            return parse_filler_data(nal.raw_data)

        elif nal_type == NalUnitType.EOS:
            return parse_eos()

        elif nal_type == NalUnitType.EOB:
            return parse_eob()

        else:
            return None
