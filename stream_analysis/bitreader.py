"""Bit-level reader for H.264/H.265 bitstream parsing.

Supports reading individual bits, fixed-length unsigned integers,
and Exp-Golomb coded values (ue(v), se(v)) as defined in ITU-T H.264/H.265.
"""


class BitReader:
    """Reads bits from a bytes buffer, MSB-first within each byte."""

    def __init__(self, data: bytes):
        self._data = data
        self._byte_offset = 0
        self._bit_offset = 0  # 0-7, 0 = MSB

    def read_bits(self, n: int) -> int:
        """Read n bits as an unsigned integer."""
        if n == 0:
            return 0
        if n < 0 or n > 64:
            raise ValueError(f"Cannot read {n} bits (must be 0-64)")
        result = 0
        for _ in range(n):
            if self._byte_offset >= len(self._data):
                raise EOFError("Read past end of bitstream")
            bit = (self._data[self._byte_offset] >> (7 - self._bit_offset)) & 1
            result = (result << 1) | bit
            self._bit_offset += 1
            if self._bit_offset == 8:
                self._bit_offset = 0
                self._byte_offset += 1
        return result

    def read_bool(self) -> bool:
        """Read a single bit as a boolean."""
        return self.read_bits(1) == 1

    def read_unsigned_exp_golomb(self) -> int:
        """Read an unsigned Exp-Golomb coded value ue(v).

        Encoding: leading_zeros '1' remainder (leading_zeros bits)
        Value = (1 << leading_zeros) - 1 + remainder
        """
        leading_zeros = 0
        while self.read_bits(1) == 0:
            leading_zeros += 1
            if leading_zeros > 31:
                raise ValueError("Exp-Golomb code exceeds 31 leading zeros")
        if leading_zeros == 0:
            return 0
        remainder = self.read_bits(leading_zeros)
        return (1 << leading_zeros) - 1 + remainder

    def read_signed_exp_golomb(self) -> int:
        """Read a signed Exp-Golomb coded value se(v).

        Maps unsigned value k:
          k=0 -> 0, k=1 -> 1, k=2 -> -1, k=3 -> 2, k=4 -> -2, ...
        """
        k = self.read_unsigned_exp_golomb()
        if k == 0:
            return 0
        if k & 1:  # odd
            return (k + 1) >> 1
        else:  # even
            return -(k >> 1)

    def peek_bits(self, n: int) -> int:
        """Look ahead n bits without consuming them."""
        saved_byte = self._byte_offset
        saved_bit = self._bit_offset
        try:
            return self.read_bits(n)
        finally:
            self._byte_offset = saved_byte
            self._bit_offset = saved_bit

    def skip_bits(self, n: int) -> None:
        """Advance the position by n bits without returning data."""
        total_bits = self._bit_offset + n
        self._byte_offset += total_bits >> 3
        self._bit_offset = total_bits & 7
        if self._byte_offset > len(self._data) or (
            self._byte_offset == len(self._data) and self._bit_offset > 0
        ):
            raise EOFError("Skip past end of bitstream")

    def bits_remaining(self) -> int:
        """Return the number of bits remaining in the buffer."""
        return (len(self._data) - self._byte_offset) * 8 - self._bit_offset

    def byte_aligned(self) -> bool:
        """Return True if the current position is byte-aligned."""
        return self._bit_offset == 0

    def align_to_byte(self) -> None:
        """Skip to the next byte boundary."""
        if self._bit_offset != 0:
            self._bit_offset = 0
            self._byte_offset += 1

    def bit_position(self) -> int:
        """Return the absolute bit position from the start of the buffer."""
        return self._byte_offset * 8 + self._bit_offset

    def more_rbsp_data(self) -> bool:
        """Check if there is more RBSP data remaining.

        RBSP trailing bits are: one '1' bit (stop bit) followed by
        0-7 '0' bits for byte alignment. If the remaining bits exactly
        match this pattern, there is no more RBSP data.
        """
        remaining = self.bits_remaining()
        if remaining <= 0:
            return False
        if remaining > 8:
            return True

        # Check if the remaining bits are just the stop bit + alignment zeros
        saved_byte = self._byte_offset
        saved_bit = self._bit_offset
        try:
            val = self.read_bits(remaining)
            # The pattern is: 1 followed by (remaining-1) zeros
            # That equals 1 << (remaining - 1)
            return val != (1 << (remaining - 1))
        finally:
            self._byte_offset = saved_byte
            self._bit_offset = saved_bit
