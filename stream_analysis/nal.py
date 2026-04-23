"""NAL unit extraction from Annex B byte streams.

Handles start code detection, emulation prevention byte removal,
and NAL header parsing for both H.264 and H.265.
"""

from dataclasses import dataclass, field


@dataclass
class NalUnit:
    """A single NAL unit extracted from a byte stream."""
    offset: int  # byte position of start code in original stream
    start_code_len: int  # 3 or 4
    raw_data: bytes  # data after start code (including NAL header)
    rbsp_data: bytes = field(default=b"", repr=False)  # after EPB removal

    @property
    def size(self) -> int:
        return len(self.raw_data)


@dataclass
class H264NalHeader:
    """H.264 NAL unit header (1 byte)."""
    forbidden_zero_bit: int  # 1 bit, should be 0
    nal_ref_idc: int  # 2 bits
    nal_unit_type: int  # 5 bits


@dataclass
class H265NalHeader:
    """H.265 NAL unit header (2 bytes)."""
    forbidden_zero_bit: int  # 1 bit, should be 0
    nal_unit_type: int  # 6 bits
    nuh_layer_id: int  # 6 bits
    nuh_temporal_id_plus1: int  # 3 bits


def find_nal_units(data: bytes) -> list[NalUnit]:
    """Find all NAL units in an Annex B byte stream.

    Scans for start codes (0x000001 or 0x00000001), splits the data
    into NAL units, and runs emulation prevention byte removal on each.
    """
    start_codes = _find_start_codes(data)
    if not start_codes:
        return []

    nal_units = []
    for i, (pos, sc_len) in enumerate(start_codes):
        nal_start = pos + sc_len
        if i + 1 < len(start_codes):
            # NAL data extends to the byte before the next start code.
            # Strip trailing zero bytes that are part of the next start code prefix.
            next_pos = start_codes[i + 1][0]
            nal_end = next_pos
        else:
            nal_end = len(data)

        raw = data[nal_start:nal_end]
        if len(raw) == 0:
            continue

        rbsp = remove_emulation_prevention_bytes(raw)
        nal_units.append(NalUnit(
            offset=pos,
            start_code_len=sc_len,
            raw_data=raw,
            rbsp_data=rbsp,
        ))

    return nal_units


def _find_start_codes(data: bytes) -> list[tuple[int, int]]:
    """Find all start code positions and their lengths (3 or 4 bytes).

    Returns list of (position, length) tuples.
    """
    result = []
    n = len(data)
    i = 0
    while i < n - 2:
        if data[i] == 0 and data[i + 1] == 0:
            if data[i + 2] == 1:
                # Check for 4-byte start code
                if i > 0 and data[i - 1] == 0:
                    # 0x00000001 - but only if we haven't already recorded
                    # this as part of a previous start code
                    if result and result[-1][0] == i - 1:
                        # Update the previous entry to be a 4-byte start code
                        result[-1] = (i - 1, 4)
                    else:
                        result.append((i - 1, 4))
                else:
                    result.append((i, 3))
                i += 3
            elif data[i + 2] == 0:
                i += 1  # could be start of a longer zero sequence
            else:
                i += 3
        else:
            i += 1
    return result


def remove_emulation_prevention_bytes(data: bytes) -> bytes:
    """Remove emulation prevention bytes (0x03) from NAL unit data.

    In the byte stream, the sequence 0x00 0x00 0x03 followed by 0x00, 0x01,
    0x02, or 0x03 has the 0x03 byte inserted to prevent false start code
    detection. This function removes those inserted bytes to recover the RBSP.
    """
    result = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if (
            i + 2 < n
            and data[i] == 0
            and data[i + 1] == 0
            and data[i + 2] == 3
            and (i + 3 >= n or data[i + 3] <= 3)
        ):
            # Found valid EPB: 0x00 0x00 0x03 followed by {0x00-0x03} or end
            result.append(0)
            result.append(0)
            i += 3  # skip the 0x03
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


def parse_h264_nal_header(data: bytes) -> H264NalHeader:
    """Parse a 1-byte H.264 NAL unit header."""
    if len(data) < 1:
        raise ValueError("NAL unit data too short for H.264 header")
    byte = data[0]
    return H264NalHeader(
        forbidden_zero_bit=(byte >> 7) & 1,
        nal_ref_idc=(byte >> 5) & 3,
        nal_unit_type=byte & 0x1F,
    )


def parse_h265_nal_header(data: bytes) -> H265NalHeader:
    """Parse a 2-byte H.265 NAL unit header."""
    if len(data) < 2:
        raise ValueError("NAL unit data too short for H.265 header")
    byte0 = data[0]
    byte1 = data[1]
    return H265NalHeader(
        forbidden_zero_bit=(byte0 >> 7) & 1,
        nal_unit_type=(byte0 >> 1) & 0x3F,
        nuh_layer_id=((byte0 & 1) << 5) | ((byte1 >> 3) & 0x1F),
        nuh_temporal_id_plus1=byte1 & 7,
    )
