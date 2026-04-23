"""Tests for NAL unit extraction."""

import unittest
from stream_analysis.nal import (
    find_nal_units,
    remove_emulation_prevention_bytes,
    parse_h264_nal_header,
    parse_h265_nal_header,
)


class TestEPBRemoval(unittest.TestCase):

    def test_basic_epb_removal(self):
        # 0x00 0x00 0x03 0x00 -> 0x00 0x00 0x00
        data = bytes([0x00, 0x00, 0x03, 0x00])
        self.assertEqual(remove_emulation_prevention_bytes(data), bytes([0x00, 0x00, 0x00]))

    def test_epb_removal_01(self):
        # 0x00 0x00 0x03 0x01 -> 0x00 0x00 0x01
        data = bytes([0x00, 0x00, 0x03, 0x01])
        self.assertEqual(remove_emulation_prevention_bytes(data), bytes([0x00, 0x00, 0x01]))

    def test_epb_removal_02(self):
        data = bytes([0x00, 0x00, 0x03, 0x02])
        self.assertEqual(remove_emulation_prevention_bytes(data), bytes([0x00, 0x00, 0x02]))

    def test_epb_removal_03(self):
        data = bytes([0x00, 0x00, 0x03, 0x03])
        self.assertEqual(remove_emulation_prevention_bytes(data), bytes([0x00, 0x00, 0x03]))

    def test_no_false_removal(self):
        # 0x00 0x00 0x03 0x04 should NOT have 0x03 removed
        data = bytes([0x00, 0x00, 0x03, 0x04])
        self.assertEqual(remove_emulation_prevention_bytes(data), data)

    def test_no_epb(self):
        data = bytes([0x67, 0x42, 0x00, 0x1E])
        self.assertEqual(remove_emulation_prevention_bytes(data), data)

    def test_multiple_epb(self):
        data = bytes([0x00, 0x00, 0x03, 0x00, 0xFF, 0x00, 0x00, 0x03, 0x01])
        expected = bytes([0x00, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x01])
        self.assertEqual(remove_emulation_prevention_bytes(data), expected)


class TestFindNalUnits(unittest.TestCase):

    def test_single_nal_3byte_start_code(self):
        # 0x000001 + NAL data
        data = bytes([0x00, 0x00, 0x01, 0x67, 0x42, 0x00])
        nals = find_nal_units(data)
        self.assertEqual(len(nals), 1)
        self.assertEqual(nals[0].offset, 0)
        self.assertEqual(nals[0].start_code_len, 3)
        self.assertEqual(nals[0].raw_data, bytes([0x67, 0x42, 0x00]))

    def test_single_nal_4byte_start_code(self):
        # 0x00000001 + NAL data
        data = bytes([0x00, 0x00, 0x00, 0x01, 0x67, 0x42])
        nals = find_nal_units(data)
        self.assertEqual(len(nals), 1)
        self.assertEqual(nals[0].offset, 0)
        self.assertEqual(nals[0].start_code_len, 4)

    def test_two_nals(self):
        # Two NAL units with 4-byte start codes
        data = bytes([
            0x00, 0x00, 0x00, 0x01, 0x67, 0x42,  # NAL 1 (SPS-like)
            0x00, 0x00, 0x00, 0x01, 0x68, 0x00,  # NAL 2 (PPS-like)
        ])
        nals = find_nal_units(data)
        self.assertEqual(len(nals), 2)
        self.assertEqual(nals[0].raw_data, bytes([0x67, 0x42]))
        self.assertEqual(nals[1].raw_data, bytes([0x68, 0x00]))

    def test_mixed_start_codes(self):
        # 4-byte then 3-byte start code
        data = bytes([
            0x00, 0x00, 0x00, 0x01, 0x67, 0x42,
            0x00, 0x00, 0x01, 0x68, 0x00,
        ])
        nals = find_nal_units(data)
        self.assertEqual(len(nals), 2)

    def test_empty_data(self):
        nals = find_nal_units(b"")
        self.assertEqual(len(nals), 0)

    def test_no_start_code(self):
        nals = find_nal_units(b"\x67\x42\x00\x1E")
        self.assertEqual(len(nals), 0)

    def test_epb_removal_in_nal(self):
        # NAL with EPB inside
        data = bytes([
            0x00, 0x00, 0x00, 0x01,  # start code
            0x67,  # NAL header
            0x00, 0x00, 0x03, 0x00,  # EPB sequence
            0xFF,
        ])
        nals = find_nal_units(data)
        self.assertEqual(len(nals), 1)
        # RBSP should have EPB removed
        self.assertEqual(nals[0].rbsp_data, bytes([0x67, 0x00, 0x00, 0x00, 0xFF]))


class TestH264NalHeader(unittest.TestCase):

    def test_sps_header(self):
        # 0x67 = 0b01100111 -> forbidden=0, nal_ref_idc=3, type=7 (SPS)
        hdr = parse_h264_nal_header(bytes([0x67]))
        self.assertEqual(hdr.forbidden_zero_bit, 0)
        self.assertEqual(hdr.nal_ref_idc, 3)
        self.assertEqual(hdr.nal_unit_type, 7)

    def test_pps_header(self):
        # 0x68 = 0b01101000 -> forbidden=0, nal_ref_idc=3, type=8 (PPS)
        hdr = parse_h264_nal_header(bytes([0x68]))
        self.assertEqual(hdr.forbidden_zero_bit, 0)
        self.assertEqual(hdr.nal_ref_idc, 3)
        self.assertEqual(hdr.nal_unit_type, 8)

    def test_idr_header(self):
        # 0x65 = 0b01100101 -> forbidden=0, nal_ref_idc=3, type=5 (IDR)
        hdr = parse_h264_nal_header(bytes([0x65]))
        self.assertEqual(hdr.nal_unit_type, 5)

    def test_non_idr_header(self):
        # 0x41 = 0b01000001 -> forbidden=0, nal_ref_idc=2, type=1
        hdr = parse_h264_nal_header(bytes([0x41]))
        self.assertEqual(hdr.nal_ref_idc, 2)
        self.assertEqual(hdr.nal_unit_type, 1)

    def test_sei_header(self):
        # 0x06 = 0b00000110 -> forbidden=0, nal_ref_idc=0, type=6 (SEI)
        hdr = parse_h264_nal_header(bytes([0x06]))
        self.assertEqual(hdr.nal_ref_idc, 0)
        self.assertEqual(hdr.nal_unit_type, 6)


class TestH265NalHeader(unittest.TestCase):

    def test_vps_header(self):
        # VPS: nal_unit_type=32
        # byte0: forbidden(0) | type(32=100000) | layer_id_msb(0) = 0_100000_0 = 0x40
        # byte1: layer_id_lsb(00000) | temporal_id+1(001) = 00000_001 = 0x01
        hdr = parse_h265_nal_header(bytes([0x40, 0x01]))
        self.assertEqual(hdr.forbidden_zero_bit, 0)
        self.assertEqual(hdr.nal_unit_type, 32)
        self.assertEqual(hdr.nuh_layer_id, 0)
        self.assertEqual(hdr.nuh_temporal_id_plus1, 1)

    def test_sps_header(self):
        # SPS: nal_unit_type=33
        # byte0: 0_100001_0 = 0x42
        # byte1: 00000_001 = 0x01
        hdr = parse_h265_nal_header(bytes([0x42, 0x01]))
        self.assertEqual(hdr.nal_unit_type, 33)

    def test_pps_header(self):
        # PPS: nal_unit_type=34
        # byte0: 0_100010_0 = 0x44
        hdr = parse_h265_nal_header(bytes([0x44, 0x01]))
        self.assertEqual(hdr.nal_unit_type, 34)

    def test_empty_data(self):
        with self.assertRaises(ValueError):
            parse_h265_nal_header(b"")


if __name__ == "__main__":
    unittest.main()
