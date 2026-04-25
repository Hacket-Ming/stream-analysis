"""H.266 (VVC) NAL unit type definitions and constants."""

from enum import IntEnum


class NalUnitType(IntEnum):
    # VCL NAL unit types (0-6)
    TRAIL_NUT = 0
    STSA_NUT = 1
    RADL_NUT = 2
    RASL_NUT = 3
    RSV_VCL_4 = 4
    RSV_VCL_5 = 5
    RSV_VCL_6 = 6
    IDR_W_RADL = 7
    IDR_N_LP = 8
    CRA_NUT = 9
    GDR_NUT = 10
    RSV_IRAP_11 = 11

    # Non-VCL NAL unit types
    OPI_NUT = 12
    DCI_NUT = 13
    VPS_NUT = 14
    SPS_NUT = 15
    PPS_NUT = 16
    PREFIX_APS_NUT = 17
    SUFFIX_APS_NUT = 18
    PH_NUT = 19
    AUD_NUT = 20
    EOS_NUT = 21
    EOB_NUT = 22
    PREFIX_SEI_NUT = 23
    SUFFIX_SEI_NUT = 24
    FD_NUT = 25
    RSV_NVCL_26 = 26
    RSV_NVCL_27 = 27


NAL_TYPE_NAMES = {
    0: "TRAIL",
    1: "STSA",
    2: "RADL",
    3: "RASL",
    7: "IDR_W_RADL",
    8: "IDR_N_LP",
    9: "CRA",
    10: "GDR",
    12: "OPI",
    13: "DCI",
    14: "VPS",
    15: "SPS",
    16: "PPS",
    17: "APS (prefix)",
    18: "APS (suffix)",
    19: "PH",
    20: "AUD",
    21: "EOS",
    22: "EOB",
    23: "SEI (prefix)",
    24: "SEI (suffix)",
    25: "Filler Data",
}

SLICE_TYPE_NAMES = {0: "B", 1: "P", 2: "I"}

PROFILE_NAMES = {
    1: "Main 10",
    17: "Multilayer Main 10",
    33: "Main 10 4:4:4",
    49: "Multilayer Main 10 4:4:4",
    65: "Main 10 Still Picture",
    81: "Main 10 4:4:4 Still Picture",
    97: "Main 10 16-bit Still Picture",  # reserved but known
}

APS_PARAMS_TYPE_NAMES = {
    0: "ALF",
    1: "LMCS",
    2: "Scaling List",
}

PRIMARY_PIC_TYPE_NAMES = {
    0: "I",
    1: "I, P",
    2: "I, P, B",
}


def is_irap(nal_type: int) -> bool:
    """Check if NAL type is an IRAP picture (IDR or CRA)."""
    return nal_type in (NalUnitType.IDR_W_RADL, NalUnitType.IDR_N_LP,
                        NalUnitType.CRA_NUT)


def is_idr(nal_type: int) -> bool:
    """Check if NAL type is an IDR picture."""
    return nal_type in (NalUnitType.IDR_W_RADL, NalUnitType.IDR_N_LP)


def is_gdr(nal_type: int) -> bool:
    """Check if NAL type is a GDR picture."""
    return nal_type == NalUnitType.GDR_NUT


def is_vcl(nal_type: int) -> bool:
    """Check if NAL type is a VCL (Video Coding Layer) NAL unit."""
    return 0 <= nal_type <= 11
