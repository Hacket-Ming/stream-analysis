"""H.265 (HEVC) NAL unit type definitions and constants."""

from enum import IntEnum


class NalUnitType(IntEnum):
    TRAIL_N = 0
    TRAIL_R = 1
    TSA_N = 2
    TSA_R = 3
    STSA_N = 4
    STSA_R = 5
    RADL_N = 6
    RADL_R = 7
    RASL_N = 8
    RASL_R = 9
    RSV_VCL_N10 = 10
    RSV_VCL_R11 = 11
    RSV_VCL_N12 = 12
    RSV_VCL_R13 = 13
    RSV_VCL_N14 = 14
    RSV_VCL_R15 = 15
    BLA_W_LP = 16
    BLA_W_RADL = 17
    BLA_N_LP = 18
    IDR_W_RADL = 19
    IDR_N_LP = 20
    CRA_NUT = 21
    RSV_IRAP_VCL22 = 22
    RSV_IRAP_VCL23 = 23
    VPS = 32
    SPS = 33
    PPS = 34
    AUD = 35
    EOS = 36
    EOB = 37
    FILLER_DATA = 38
    SEI_PREFIX = 39
    SEI_SUFFIX = 40
    RSV_NVCL41 = 41


NAL_TYPE_NAMES = {
    0: "TRAIL_N", 1: "TRAIL_R",
    2: "TSA_N", 3: "TSA_R",
    4: "STSA_N", 5: "STSA_R",
    6: "RADL_N", 7: "RADL_R",
    8: "RASL_N", 9: "RASL_R",
    16: "BLA_W_LP", 17: "BLA_W_RADL", 18: "BLA_N_LP",
    19: "IDR_W_RADL", 20: "IDR_N_LP",
    21: "CRA_NUT",
    32: "VPS", 33: "SPS", 34: "PPS",
    35: "AUD", 36: "EOS", 37: "EOB",
    38: "Filler Data",
    39: "SEI (prefix)", 40: "SEI (suffix)",
}

SLICE_TYPE_NAMES = {0: "B", 1: "P", 2: "I"}

PROFILE_NAMES = {
    1: "Main",
    2: "Main 10",
    3: "Main Still Picture",
    4: "Format Range Extensions",
    5: "High Throughput",
    6: "Multiview Main",
    7: "Scalable Main",
    8: "3D Main",
    9: "Screen Content Coding Extensions",
    10: "Scalable Format Range Extensions",
    11: "High Throughput Screen Content Coding Extensions",
}

PRIMARY_PIC_TYPE_NAMES = {
    0: "I",
    1: "I, P",
    2: "I, P, B",
}


def is_irap(nal_type: int) -> bool:
    """Check if NAL type is an IRAP picture."""
    return 16 <= nal_type <= 23


def is_vcl(nal_type: int) -> bool:
    """Check if NAL type is a VCL (Video Coding Layer) NAL unit."""
    return 0 <= nal_type <= 31
