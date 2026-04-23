"""H.264 NAL unit type definitions and constants."""

from enum import IntEnum


class NalUnitType(IntEnum):
    UNSPECIFIED = 0
    SLICE_NON_IDR = 1
    SLICE_PART_A = 2
    SLICE_PART_B = 3
    SLICE_PART_C = 4
    SLICE_IDR = 5
    SEI = 6
    SPS = 7
    PPS = 8
    AUD = 9
    END_OF_SEQUENCE = 10
    END_OF_STREAM = 11
    FILLER_DATA = 12
    SPS_EXTENSION = 13
    PREFIX_NAL = 14
    SUBSET_SPS = 15
    DEPTH_PARAMETER_SET = 16
    # 17-18 reserved
    SLICE_AUX = 19
    SLICE_EXTENSION = 20
    SLICE_EXTENSION_DEPTH = 21
    # 22-23 reserved
    # 24-31 unspecified


NAL_TYPE_NAMES = {
    0: "Unspecified",
    1: "Slice (non-IDR)",
    2: "Slice Data Partition A",
    3: "Slice Data Partition B",
    4: "Slice Data Partition C",
    5: "Slice (IDR)",
    6: "SEI",
    7: "SPS",
    8: "PPS",
    9: "AUD",
    10: "End of Sequence",
    11: "End of Stream",
    12: "Filler Data",
    13: "SPS Extension",
    14: "Prefix NAL Unit",
    15: "Subset SPS",
    16: "Depth Parameter Set",
    19: "Slice Auxiliary",
    20: "Slice Extension",
    21: "Slice Extension (Depth)",
}

SLICE_TYPE_NAMES = {
    0: "P", 1: "B", 2: "I", 3: "SP", 4: "SI",
    5: "P", 6: "B", 7: "I", 8: "SP", 9: "SI",
}

PROFILE_NAMES = {
    66: "Baseline",
    77: "Main",
    88: "Extended",
    100: "High",
    110: "High 10",
    122: "High 4:2:2",
    244: "High 4:4:4 Predictive",
    44: "CAVLC 4:4:4 Intra",
    83: "Scalable Baseline",
    86: "Scalable High",
    118: "Multiview High",
    128: "Stereo High",
    138: "Multiview Depth High",
    139: "Enhanced Multiview Depth High",
    134: "MFC High",
    135: "MFC Depth High",
}

# Profiles that have extended SPS fields (chroma_format_idc, etc.)
HIGH_PROFILES = {100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135}

PRIMARY_PIC_TYPE_NAMES = {
    0: "I",
    1: "I, P",
    2: "I, P, B",
    3: "SI",
    4: "SI, SP",
    5: "I, SI",
    6: "I, SI, P, SP",
    7: "I, SI, P, SP, B",
}
