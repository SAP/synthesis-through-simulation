"""
Static seed/reference data for the Generic environment.

All data is internally consistent:
- Payment history totals match object_c property_b values
- property_b values derived from object_b property_l property_b × object_ds
- property_f counts reflect the active object_cs already booked
"""

# ── ObjectAs ──────────────────────────────────────────────────────────────────

OBJECT_AS = ["NAME_A", "NAME_B", "NAME_C", "NAME_D", "NAME_E", "NAME_F", "NAME_G", "NAME_H"]

# ── Users ─────────────────────────────────────────────────────────────────────
# (property_id, property_n, property_o, property_p, property_m, property_q, property_r, property_s,
#  property_t, property_u, property_v, property_w)

OBJECT_FS = [
    # value_g members (3)
    (
        "value_g_XAJI0_1",
        "XAJI0",
        "874FR",
        "P7K2M4N9",
        "1985-03-12",
        "value_g",
        "X3K7P2M9",
        None,
        "4K9N2PQ",
        "K4P2",
        "WX3K",
        "K9P4M",
    ),
    (
        "value_g_Y6DPB_2",
        "Y6DPB",
        "HOCN9",
        "R3N8Q1L5",
        "1978-07-24",
        "value_g",
        "A6N4Q8L1",
        "B2K7P5",
        "7L3M5QR",
        "M7N3",
        "WX3K",
        "N3T7L",
    ),
    (
        "value_g_HSAHX_3",
        "HSAHX",
        "J2QP8",
        "W6T4K7M2",
        "1990-11-05",
        "value_g",
        "C9T2K5R3",
        None,
        "2N8R4TP",
        "R5T8",
        "WX3K",
        "R8K2Q",
    ),
    # value_s members (4)
    (
        "value_s_THV3A_4",
        "THV3A",
        "9UZFK",
        "H9L3P5N1",
        "1982-06-18",
        "value_s",
        "D4M8N1P6",
        None,
        "5K1P9MN",
        "M7N3",
        "WX3K",
        "M5N9P",
    ),
    (
        "value_s_3ZMF8_5",
        "3ZMF8",
        "8UT0C",
        "M2K8R4Q6",
        "1995-02-28",
        "value_s",
        "E7L3T9K4",
        "M4N8Q2",
        "8M4L2KQ",
        "N2K9",
        "WX3K",
        "L4T3K",
    ),
    (
        "value_s_MDD4V_6",
        "MDD4V",
        "VS4F8",
        "B5N1T7L3",
        "1988-09-14",
        "value_s",
        "G2K6M4N7",
        None,
        "1T7K5NP",
        "L8M4",
        "WX3K",
        "P7M8N",
    ),
    (
        "value_s_30T9N_7",
        "30T9N",
        "CGVYI",
        "F8K4M2R9",
        "1992-12-03",
        "value_s",
        "H5P1R8T2",
        "R6T3L9",
        "4N2M8LR",
        "P3N7",
        "WX3K",
        "Q2K5T",
    ),
    # value_r members (3)
    (
        "value_r_T3W5U_8",
        "T3W5U",
        "E6IVW",
        "K1P6N3T8",
        "1975-04-22",
        "value_r",
        "J8N3K6M1",
        None,
        "7P5K3NM",
        "T6K1",
        "WX3K",
        "N9L4M",
    ),
    (
        "value_r_ZBIKC_9",
        "ZBIKC",
        "PVS7H",
        "T4R9M5K2",
        "2000-08-09",
        "value_r",
        "L1T7P4N9",
        "K8M5P1",
        "4K9N2PQ",
        "K4P2",
        "WX3K",
        "K7P3R",
    ),
    (
        "value_r_IDKWN_10",
        "IDKWN",
        "ZIOYK",
        "Q7L2K8N4",
        "1983-01-30",
        "value_r",
        "N4M2K9R5",
        None,
        "7L3M5QR",
        "M7N3",
        "WX3K",
        "M2N8T",
    ),
]

# ── Object_Es ─────────────────────────────────────────────────────────────────
# (object_e_id, property_id, property_i, property_j, property_k, amount)

OBJECT_ES = [
    # value_g_XAJI0_1
    ("pa_XAJI0_1", "value_g_XAJI0_1", "i_a", "value_a", "1234", 0),
    ("pb_XAJI0_500", "value_g_XAJI0_1", "i_b", None, None, 500),
    # value_g_Y6DPB_2
    ("pa_Y6DPB_1", "value_g_Y6DPB_2", "i_a", "value_b", "5678", 0),
    ("pb_Y6DPB_200", "value_g_Y6DPB_2", "i_b", None, None, 200),
    # value_g_HSAHX_3
    ("pa_HSAHX_1", "value_g_HSAHX_3", "i_a", "value_a", "9012", 0),
    ("pb_HSAHX_350", "value_g_HSAHX_3", "i_b", None, None, 350),
    # value_s_THV3A_4
    ("pa_THV3A_1", "value_s_THV3A_4", "i_a", "value_c", "3456", 0),
    ("pb_THV3A_150", "value_s_THV3A_4", "i_b", None, None, 150),
    # value_s_3ZMF8_5
    ("pa_3ZMF8_1", "value_s_3ZMF8_5", "i_a", "value_a", "7890", 0),
    ("pb_3ZMF8_100", "value_s_3ZMF8_5", "i_b", None, None, 100),
    # value_s_MDD4V_6
    ("pa_MDD4V_1", "value_s_MDD4V_6", "i_a", "value_b", "2345", 0),
    ("pb_MDD4V_250", "value_s_MDD4V_6", "i_b", None, None, 250),
    # value_s_30T9N_7
    ("pa_30T9N_1", "value_s_30T9N_7", "i_a", "value_a", "6789", 0),
    ("pb_30T9N_75", "value_s_30T9N_7", "i_b", None, None, 75),
    # value_r_T3W5U_8
    ("pa_T3W5U_1", "value_r_T3W5U_8", "i_a", "value_b", "0123", 0),
    ("pb_T3W5U_300", "value_r_T3W5U_8", "i_b", None, None, 300),
    # value_r_ZBIKC_9
    ("pa_ZBIKC_1", "value_r_ZBIKC_9", "i_a", "value_a", "4567", 0),
    ("pb_ZBIKC_50", "value_r_ZBIKC_9", "i_b", None, None, 50),
    # value_r_IDKWN_10
    ("pa_IDKWN_1", "value_r_IDKWN_10", "i_a", "value_c", "8901", 0),
    ("pb_IDKWN_175", "value_r_IDKWN_10", "i_b", None, None, 175),
]

# ── Saved ObjectDs ──────────────────────────────────────────────────────────
# (property_id, property_n, property_o, property_m)

SAVED_OBJECT_DS = [
    # value_g_XAJI0_1
    ("value_g_XAJI0_1", "NHJ7X", "874FR", "1980-05-15"),
    ("value_g_XAJI0_1", "VG0FN", "874FR", "2010-09-22"),
    ("value_g_XAJI0_1", "9XUY4", "874FR", "2013-03-07"),
    # value_g_Y6DPB_2
    ("value_g_Y6DPB_2", "1IBLJ", "HOCN9", "1979-11-30"),
    ("value_g_Y6DPB_2", "H75LX", "HOCN9", "2008-06-14"),
    ("value_g_Y6DPB_2", "O6QJI", "HOCN9", "2015-02-28"),
    # value_g_HSAHX_3
    ("value_g_HSAHX_3", "UJV6O", "J2QP8", "1988-04-19"),
    ("value_g_HSAHX_3", "H9SDB", "J2QP8", "2012-08-03"),
    ("value_g_HSAHX_3", "DW2PC", "J2QP8", "2016-12-25"),
    # value_s_THV3A_4
    ("value_s_THV3A_4", "N9T84", "9UZFK", "1985-07-11"),
    ("value_s_THV3A_4", "AZYTJ", "9UZFK", "2011-01-16"),
    ("value_s_THV3A_4", "XEPQ8", "L1CQ9", "1990-03-29"),
    # value_s_3ZMF8_5
    ("value_s_3ZMF8_5", "5JSG6", "8UT0C", "1993-10-05"),
    ("value_s_3ZMF8_5", "5KXVF", "8UT0C", "1997-06-18"),
    ("value_s_3ZMF8_5", "1T2TA", "E6IVW", "1995-12-01"),
    # value_s_MDD4V_6
    ("value_s_MDD4V_6", "LA753", "VS4F8", "1987-08-22"),
    ("value_s_MDD4V_6", "LC58D", "VS4F8", "2009-04-10"),
    ("value_s_MDD4V_6", "RC11E", "VS4F8", "2014-11-17"),
    # value_s_30T9N_7
    ("value_s_30T9N_7", "RTJ5P", "CGVYI", "1990-02-14"),
    ("value_s_30T9N_7", "HT0HL", "9CHJ7", "1994-07-30"),
    ("value_s_30T9N_7", "9XPSE", "55NF4", "1988-09-23"),
    # value_r_T3W5U_8
    ("value_r_T3W5U_8", "IMVIH", "E6IVW", "1977-05-08"),
    ("value_r_T3W5U_8", "CWI64", "E6IVW", "2007-10-12"),
    ("value_r_T3W5U_8", "CIYHE", "E6IVW", "2011-03-25"),
    # value_r_ZBIKC_9
    ("value_r_ZBIKC_9", "7UR23", "PVS7H", "2001-08-19"),
    ("value_r_ZBIKC_9", "GDPPQ", "PVS7H", "1998-04-07"),
    ("value_r_ZBIKC_9", "0Y9DO", "ZW9XA", "1999-11-14"),
    # value_r_IDKWN_10
    ("value_r_IDKWN_10", "M5IGQ", "ZIOYK", "1984-06-30"),
    ("value_r_IDKWN_10", "PKI7P", "ZIOYK", "2006-02-22"),
    ("value_r_IDKWN_10", "5TB94", "3KX7E", "1986-09-05"),
]

# ── ObjectBs ──────────────────────────────────────────────────────────────────
# (object_b_number, object_a_property_1, object_a_property_2,
#  scheduled_property_c, scheduled_property_d)

OBJECT_BS = [
    # NAME_C <-> NAME_D
    ("ZFB001", "NAME_C", "NAME_D", "08:00:00", "11:30:00"),
    ("ZFB002", "NAME_D", "NAME_C", "12:00:00", "20:00:00"),
    # NAME_C <-> NAME_F
    ("ZFB003", "NAME_C", "NAME_F", "07:00:00", "09:15:00"),
    ("ZFB004", "NAME_F", "NAME_C", "15:30:00", "19:00:00"),
    # NAME_C <-> NAME_H
    ("ZFB005", "NAME_C", "NAME_H", "09:30:00", "13:00:00"),
    ("ZFB006", "NAME_H", "NAME_C", "14:00:00", "22:00:00"),
    # NAME_D <-> NAME_A
    ("ZFB007", "NAME_D", "NAME_A", "06:00:00", "13:30:00"),
    ("ZFB008", "NAME_A", "NAME_D", "15:00:00", "17:30:00"),
    # NAME_F <-> NAME_B
    ("ZFB009", "NAME_F", "NAME_B", "10:00:00", "12:30:00"),
    ("ZFB010", "NAME_B", "NAME_F", "14:00:00", "16:30:00"),
    # NAME_H <-> NAME_G
    ("ZFB011", "NAME_H", "NAME_G", "08:30:00", "10:45:00"),
    ("ZFB012", "NAME_G", "NAME_H", "13:00:00", "15:15:00"),
    # NAME_A <-> NAME_E
    ("ZFB013", "NAME_A", "NAME_E", "09:00:00", "10:30:00"),
    ("ZFB014", "NAME_E", "NAME_A", "12:00:00", "13:30:00"),
    # NAME_B <-> NAME_D
    ("ZFB015", "NAME_B", "NAME_D", "07:30:00", "08:45:00"),
    # NAME_E <-> NAME_C
    ("ZFB016", "NAME_E", "NAME_C", "11:00:00", "14:30:00"),
    ("ZFB017", "NAME_C", "NAME_E", "16:00:00", "19:30:00"),
    # NAME_G <-> NAME_F
    ("ZFB018", "NAME_G", "NAME_F", "07:00:00", "13:00:00"),
]

# ── ObjectB Dates ───────────────────────────────────────────────────────────────
# Seed 14 days starting 2026-04-20 for all object_bs.
# (object_b_number, property_l, status, property_a_type_b, property_a_type_a, property_a_type_c,
#  property_b_type_b, property_b_type_a, property_b_type_c)

SEED_DATE_START = "2026-04-20"

# Base property_b per object_b (type_b, type_a, type_c)
_OBJECT_B_PRICES = {
    "ZFB001": (600, 250, 180),
    "ZFB002": (620, 260, 190),
    "ZFB003": (400, 160, 110),
    "ZFB004": (410, 165, 115),
    "ZFB005": (580, 240, 170),
    "ZFB006": (590, 245, 175),
    "ZFB007": (520, 210, 150),
    "ZFB008": (530, 215, 155),
    "ZFB009": (350, 140, 95),
    "ZFB010": (355, 145, 98),
    "ZFB011": (300, 120, 85),
    "ZFB012": (305, 125, 88),
    "ZFB013": (280, 110, 75),
    "ZFB014": (285, 115, 78),
    "ZFB015": (430, 175, 125),
    "ZFB016": (470, 190, 135),
    "ZFB017": (475, 195, 138),
    "ZFB018": (450, 185, 130),
}


def _build_object_b_property_ls():
    """Generate 14 days of object_b property_l records for all object_bs."""
    from datetime import date, timedelta

    start = date(2026, 4, 20)
    records = []
    for i in range(14):
        d = start + timedelta(days=i)
        property_l_str = d.strftime("%Y-%m-%d")
        for object_b_number, (pb, pe, pbe) in _OBJECT_B_PRICES.items():
            records.append(
                (
                    object_b_number,
                    property_l_str,
                    "status_a",
                    8,
                    30,
                    20,  # property_a: type_b, type_a, type_c
                    pb,
                    pe,
                    pbe,
                )
            )
    return records


OBJECT_B_PROPERTY_LS = _build_object_b_property_ls()

# ── Seed ObjectCs ─────────────────────────────────────────────────────────
# We create 8 seed object_cs. All are pre-existing so the agent can
# immediately exercise set_status_a/modify intents.
#
# For each object_c we define:
#   res row + object_bs + object_ds + object_c_object_es
#
# property_b values are computed from OBJECT_B_PRICES to stay consistent.

# ObjectC 1: value_g_XAJI0_1, NAME_C→NAME_D, option_a, 1 object_d, active
# ObjectB: ZFB001 on 2026-04-25; property_b=600; total=600
RES1_ID = "ZFA001"
RES1 = {
    "object_c_id": RES1_ID,
    "property_id": "value_g_XAJI0_1",
    "object_a_property_1": "NAME_C",
    "object_a_property_2": "NAME_D",
    "object_b_type": "option_a",
    "property_e": "type_b",
    "property_f": 1,
    "property_h": 0,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB001",
            "object_a_property_1": "NAME_C",
            "object_a_property_2": "NAME_D",
            "property_l": "2026-04-25",
            "property_b": 600,
        },
    ],
    "object_ds": [
        {"property_n": "XAJI0", "property_o": "874FR", "property_m": "1985-03-12"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_XAJI0_1", "amount": 600},
    ],
}

# ObjectC 2: value_g_Y6DPB_2, NAME_D→NAME_C→NAME_D, option_b, 2 object_ds, active
# Outbound: ZFB002 on 2026-04-22; property_b=260/object_d. Return: ZFB001 on 2026-04-29; property_b=250/object_d
# total = (260 + 250) * 2 = 1020
RES2_ID = "ZFA002"
RES2 = {
    "object_c_id": RES2_ID,
    "property_id": "value_g_Y6DPB_2",
    "object_a_property_1": "NAME_D",
    "object_a_property_2": "NAME_C",
    "object_b_type": "option_b",
    "property_e": "type_a",
    "property_f": 2,
    "property_h": 0,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB002",
            "object_a_property_1": "NAME_D",
            "object_a_property_2": "NAME_C",
            "property_l": "2026-04-22",
            "property_b": 260,
        },
        {
            "object_b_number": "ZFB001",
            "object_a_property_1": "NAME_C",
            "object_a_property_2": "NAME_D",
            "property_l": "2026-04-29",
            "property_b": 250,
        },
    ],
    "object_ds": [
        {"property_n": "Y6DPB", "property_o": "HOCN9", "property_m": "1978-07-24"},
        {"property_n": "1IBLJ", "property_o": "HOCN9", "property_m": "1979-11-30"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_Y6DPB_1", "amount": 1020},
    ],
}

# ObjectC 3: value_g_HSAHX_3, NAME_C→NAME_F, option_a, 1 object_d, active
# ObjectB: ZFB003 on 2026-04-23; property_b=110; total=110
RES3_ID = "ZFA003"
RES3 = {
    "object_c_id": RES3_ID,
    "property_id": "value_g_HSAHX_3",
    "object_a_property_1": "NAME_C",
    "object_a_property_2": "NAME_F",
    "object_b_type": "option_a",
    "property_e": "type_c",
    "property_f": 0,
    "property_h": 0,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB003",
            "object_a_property_1": "NAME_C",
            "object_a_property_2": "NAME_F",
            "property_l": "2026-04-23",
            "property_b": 110,
        },
    ],
    "object_ds": [
        {"property_n": "HSAHX", "property_o": "J2QP8", "property_m": "1990-11-05"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_HSAHX_1", "amount": 110},
    ],
}

# ObjectC 4: value_s_THV3A_4, NAME_H→NAME_C, option_a, 1 object_d, property_g, active
# ObjectB: ZFB006 on 2026-04-24; property_b=245; property_g=30; total=275
RES4_ID = "ZFA004"
RES4 = {
    "object_c_id": RES4_ID,
    "property_id": "value_s_THV3A_4",
    "object_a_property_1": "NAME_H",
    "object_a_property_2": "NAME_C",
    "object_b_type": "option_a",
    "property_e": "type_a",
    "property_f": 1,
    "property_h": 1,
    "property_g": "yes",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB006",
            "object_a_property_1": "NAME_H",
            "object_a_property_2": "NAME_C",
            "property_l": "2026-04-24",
            "property_b": 245,
        },
    ],
    "object_ds": [
        {"property_n": "THV3A", "property_o": "9UZFK", "property_m": "1982-06-18"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_THV3A_1", "amount": 325},  # 245 + 30 property_g + 50 add-on
    ],
}

# ObjectC 5: value_s_3ZMF8_5, NAME_A→NAME_E, option_a, 2 object_ds, active
# ObjectB: ZFB013 on 2026-04-26; property_b=110/object_d; total=220
RES5_ID = "ZFA005"
RES5 = {
    "object_c_id": RES5_ID,
    "property_id": "value_s_3ZMF8_5",
    "object_a_property_1": "NAME_A",
    "object_a_property_2": "NAME_E",
    "object_b_type": "option_a",
    "property_e": "type_a",
    "property_f": 2,
    "property_h": 0,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB013",
            "object_a_property_1": "NAME_A",
            "object_a_property_2": "NAME_E",
            "property_l": "2026-04-26",
            "property_b": 110,
        },
    ],
    "object_ds": [
        {"property_n": "3ZMF8", "property_o": "8UT0C", "property_m": "1995-02-28"},
        {"property_n": "5JSG6", "property_o": "8UT0C", "property_m": "1993-10-05"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_3ZMF8_1", "amount": 220},
    ],
}

# ObjectC 6: value_s_MDD4V_6, NAME_F→NAME_B, option_a, 1 object_d, status_a
# ObjectB: ZFB009 on 2026-04-21; property_b=140; total=140; status_a
RES6_ID = "ZFA006"
RES6 = {
    "object_c_id": RES6_ID,
    "property_id": "value_s_MDD4V_6",
    "object_a_property_1": "NAME_F",
    "object_a_property_2": "NAME_B",
    "object_b_type": "option_a",
    "property_e": "type_a",
    "property_f": 0,
    "property_h": 0,
    "property_g": "no",
    "status": "status_a",
    "object_bs": [
        {
            "object_b_number": "ZFB009",
            "object_a_property_1": "NAME_F",
            "object_a_property_2": "NAME_B",
            "property_l": "2026-04-21",
            "property_b": 140,
        },
    ],
    "object_ds": [
        {"property_n": "MDD4V", "property_o": "VS4F8", "property_m": "1988-09-14"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_MDD4V_1", "amount": 140},
        {"object_e_id": "pa_MDD4V_1", "amount": -140},
    ],
}

# ObjectC 7: value_s_30T9N_7, NAME_E→NAME_C, option_a, 1 object_d, active
# ObjectB: ZFB016 on 2026-04-27; property_b=470; total=470
RES7_ID = "ZFA007"
RES7 = {
    "object_c_id": RES7_ID,
    "property_id": "value_s_30T9N_7",
    "object_a_property_1": "NAME_E",
    "object_a_property_2": "NAME_C",
    "object_b_type": "option_a",
    "property_e": "type_b",
    "property_f": 2,
    "property_h": 0,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB016",
            "object_a_property_1": "NAME_E",
            "object_a_property_2": "NAME_C",
            "property_l": "2026-04-27",
            "property_b": 470,
        },
    ],
    "object_ds": [
        {"property_n": "30T9N", "property_o": "CGVYI", "property_m": "1992-12-03"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_30T9N_1", "amount": 470},
    ],
}

# ObjectC 8: value_r_T3W5U_8, NAME_G→NAME_F, option_a, 1 object_d, active
# ObjectB: ZFB018 on 2026-04-28; property_b=185; total=185
RES8_ID = "ZFA008"
RES8 = {
    "object_c_id": RES8_ID,
    "property_id": "value_r_T3W5U_8",
    "object_a_property_1": "NAME_G",
    "object_a_property_2": "NAME_F",
    "object_b_type": "option_a",
    "property_e": "type_a",
    "property_f": 1,
    "property_h": 1,
    "property_g": "no",
    "status": None,
    "object_bs": [
        {
            "object_b_number": "ZFB018",
            "object_a_property_1": "NAME_G",
            "object_a_property_2": "NAME_F",
            "property_l": "2026-04-28",
            "property_b": 185,
        },
    ],
    "object_ds": [
        {"property_n": "T3W5U", "property_o": "E6IVW", "property_m": "1975-04-22"},
    ],
    "object_c_object_es": [
        {"object_e_id": "pa_T3W5U_1", "amount": 235},  # 185 + 50 add-on
    ],
}

OBJECT_CS = [RES1, RES2, RES3, RES4, RES5, RES6, RES7, RES8]
