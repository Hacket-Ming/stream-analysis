"""Tests for BitReader."""

import unittest
from stream_analysis.bitreader import BitReader


class TestBitReader(unittest.TestCase):

    def test_read_bits_single_byte(self):
        reader = BitReader(b"\xA5")  # 10100101
        self.assertEqual(reader.read_bits(1), 1)   # 1
        self.assertEqual(reader.read_bits(1), 0)   # 0
        self.assertEqual(reader.read_bits(3), 0b100)  # 100
        self.assertEqual(reader.read_bits(3), 0b101)  # 101

    def test_read_bits_cross_byte(self):
        reader = BitReader(b"\xFF\x00")  # 11111111 00000000
        self.assertEqual(reader.read_bits(4), 0xF)
        self.assertEqual(reader.read_bits(8), 0xF0)  # crosses byte boundary

    def test_read_bits_zero(self):
        reader = BitReader(b"\xFF")
        self.assertEqual(reader.read_bits(0), 0)
        self.assertEqual(reader.bits_remaining(), 8)

    def test_read_bits_eof(self):
        reader = BitReader(b"\xFF")
        reader.read_bits(8)
        with self.assertRaises(EOFError):
            reader.read_bits(1)

    def test_read_bool(self):
        reader = BitReader(b"\x80")  # 10000000
        self.assertTrue(reader.read_bool())
        self.assertFalse(reader.read_bool())

    def test_unsigned_exp_golomb(self):
        # ue(v) test values:
        # 0: bits=1 (just the stop bit)
        # 1: bits=010
        # 2: bits=011
        # 3: bits=00100
        # 7: bits=0001000

        # Value 0: binary 1xxxxxxx
        reader = BitReader(b"\x80")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 0)

        # Value 1: binary 010xxxxx
        reader = BitReader(b"\x40")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 1)

        # Value 2: binary 011xxxxx
        reader = BitReader(b"\x60")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 2)

        # Value 3: binary 00100xxx
        reader = BitReader(b"\x20")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 3)

        # Value 4: binary 00101xxx
        reader = BitReader(b"\x28")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 4)

        # Value 7: binary 0001000x
        reader = BitReader(b"\x10")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 7)

    def test_signed_exp_golomb(self):
        # se(v) maps: 0->0, 1->1, 2->-1, 3->2, 4->-2

        # Value 0 (k=0): binary 1
        reader = BitReader(b"\x80")
        self.assertEqual(reader.read_signed_exp_golomb(), 0)

        # Value 1 (k=1): binary 010
        reader = BitReader(b"\x40")
        self.assertEqual(reader.read_signed_exp_golomb(), 1)

        # Value -1 (k=2): binary 011
        reader = BitReader(b"\x60")
        self.assertEqual(reader.read_signed_exp_golomb(), -1)

        # Value 2 (k=3): binary 00100
        reader = BitReader(b"\x20")
        self.assertEqual(reader.read_signed_exp_golomb(), 2)

        # Value -2 (k=4): binary 00101
        reader = BitReader(b"\x28")
        self.assertEqual(reader.read_signed_exp_golomb(), -2)

    def test_peek_bits(self):
        reader = BitReader(b"\xAB")
        val = reader.peek_bits(4)
        self.assertEqual(val, 0xA)
        # Position should not have changed
        self.assertEqual(reader.read_bits(4), 0xA)

    def test_skip_bits(self):
        reader = BitReader(b"\xFF\x00")
        reader.skip_bits(4)
        self.assertEqual(reader.read_bits(4), 0xF)
        reader.skip_bits(4)
        self.assertEqual(reader.read_bits(4), 0x0)

    def test_bits_remaining(self):
        reader = BitReader(b"\xFF\x00")
        self.assertEqual(reader.bits_remaining(), 16)
        reader.read_bits(5)
        self.assertEqual(reader.bits_remaining(), 11)

    def test_byte_aligned(self):
        reader = BitReader(b"\xFF")
        self.assertTrue(reader.byte_aligned())
        reader.read_bits(1)
        self.assertFalse(reader.byte_aligned())
        reader.read_bits(7)
        self.assertTrue(reader.byte_aligned())

    def test_align_to_byte(self):
        reader = BitReader(b"\xFF\xAA")
        reader.read_bits(3)
        reader.align_to_byte()
        self.assertTrue(reader.byte_aligned())
        self.assertEqual(reader.read_bits(8), 0xAA)

    def test_more_rbsp_data_with_stop_bit(self):
        # Only stop bit + alignment: 10000000 -> no more data
        reader = BitReader(b"\x80")
        self.assertFalse(reader.more_rbsp_data())

    def test_more_rbsp_data_with_data(self):
        # 11000000 -> the stop bit would be at bit 0, but bit 1 is also 1
        # This means there is more data
        reader = BitReader(b"\xC0")
        self.assertTrue(reader.more_rbsp_data())

    def test_more_rbsp_data_after_partial_read(self):
        # Read some bits, then check
        reader = BitReader(b"\xFF\x80")
        reader.read_bits(8)
        # Remaining: 10000000 -> just stop bit
        self.assertFalse(reader.more_rbsp_data())

    def test_consecutive_exp_golomb(self):
        # Pack multiple ue values: 0 (1), 1 (010), 2 (011), 0 (1)
        # Binary: 1 010 011 1 = 10100111 = 0xA7
        reader = BitReader(b"\xA7")
        self.assertEqual(reader.read_unsigned_exp_golomb(), 0)
        self.assertEqual(reader.read_unsigned_exp_golomb(), 1)
        self.assertEqual(reader.read_unsigned_exp_golomb(), 2)
        self.assertEqual(reader.read_unsigned_exp_golomb(), 0)


if __name__ == "__main__":
    unittest.main()
