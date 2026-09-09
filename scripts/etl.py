#!/usr/bin/env python3
"""Build data/fjarlog.db from the raw source files in scripts/raw/.

Normalizes every year's published figures (2018-2027, plus the multi-year
plan/actual figures each budget bill carries) into one long-format table,
`budget_lines`, keyed by (target_year, stage, malefnasvid, malaflokkur,
raduneyti, lidur, vidfang, tegund). Several budget bills republish 2-4
neighboring years of figures; when the same (year, stage, ...) combination
appears in more than one source file, only the value from the most recently
published file (highest source_year) is kept, to avoid redundant storage.

Names for málefnasvið/málaflokkur/ráðuneyti/liður/viðfang codes are
normalized into small catalog tables instead of being repeated on every
row, since state budget documents reuse the same ~30 málefnasvið, ~150
málaflokkar, ~15 ráðuneyti, and ~700 liðir across hundreds of thousands of
line items.

Usage: python3 scripts/etl.py
Requires: openpyxl (pip install openpyxl)
"""
import csv
import json
import os
import re
import sqlite3

import openpyxl

HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "raw")
DB_PATH = os.path.join(HERE, "..", "data", "fjarlog.db")
SOURCES_JSON = os.path.join(HERE, "..", "data", "sources.json")

UNIT = "m.kr."  # million Icelandic kronur, as published throughout

# Deduplication buffer, keyed by every dimension except the amount itself.
# Value: (target_year, stage, mv_code, mf_code, rn_code, li_code, vf_code,
#         tegund, upphaed, source_year)
BEST = {}

# name lookups, filled in as rows are parsed; last-seen-by-year wins so a
# renamed ministry/málefnasvið shows its most recent name.
NAMES = {"malefnasvid": {}, "malaflokkur": {}, "raduneyti": {}, "lidur": {}, "vidfang": {}}


def remember_name(table, code, name, year):
    if code is None or name is None:
        return
    prev = NAMES[table].get(code)
    if prev is None or year >= prev[1]:
        NAMES[table][code] = (name, year)


def parse_num(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if s == "" or s == "-":
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def split_code_name(s):
    """Split 'M 01 Alþingi...' style or '01 Alþingi og eftirlitsstofnanir þess'
    into (code, name). Handles both 'M 01'/'R 00'/'L 201'/'V 101' prefixed
    codes (older files) and plain '01 Heiti' codes (newer long-format files).
    """
    if s is None:
        return (None, None)
    s = str(s).strip()
    if s == "":
        return (None, None)
    m = re.match(r"^([A-Z]?\s?[\d.\-]+)\s+(.*)$", s)
    if m:
        return (m.group(1).strip(), m.group(2).strip())
    return (s, s)


_LEGACY_PREFIX = re.compile(r"^[A-Z]\s*")


def normalize_legacy_codes(mv_code, mf_code, rn_code, li_code, vf_code):
    """2018/2019/2020 files use an older code style ('M 01', 'M 0110', 'R 00',
    'L 201', 'V 101') where the 2021+ long-format files use the current style
    ('01', '01.10', '00', '00-201', '101'). Convert the former to the latter
    so the same málefnasvið/ráðuneyti/liður lines up across all years.
    """
    rn = _LEGACY_PREFIX.sub("", rn_code).strip() if rn_code else rn_code
    mv = _LEGACY_PREFIX.sub("", mv_code).strip() if mv_code else mv_code
    mf_raw = _LEGACY_PREFIX.sub("", mf_code).strip() if mf_code else mf_code
    mf = f"{mf_raw[:2]}.{mf_raw[2:]}" if mf_raw and len(mf_raw) == 4 and mf_raw.isdigit() else mf_raw
    li_raw = _LEGACY_PREFIX.sub("", li_code).strip() if li_code else li_code
    li = f"{rn}-{li_raw}" if rn and li_raw else li_raw
    vf = _LEGACY_PREFIX.sub("", vf_code).strip() if vf_code else vf_code
    return mv, mf, rn, li, vf


def open_rows_xlsx(path):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    next(rows)  # header
    for row in rows:
        if row[0] is None:
            continue
        yield row


def open_rows_csv(path, encoding, delimiter=";"):
    with open(path, encoding=encoding) as f:
        reader = csv.reader(f, delimiter=delimiter)
        next(reader)  # header
        for row in reader:
            if not row or row[0] is None or str(row[0]).strip() == "":
                continue
            yield row


def normalize_stage(stage):
    """A few source files append the year to the stage label
    (e.g. 'Fjárlög 2023' instead of 'Fjárlög'); strip that for consistency."""
    if stage is None:
        return stage
    return re.sub(r"\s+\d{4}$", "", str(stage).strip())


def remember_line(year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year):
    stage = normalize_stage(stage)
    mv_code, mv_name = mv
    mf_code, mf_name = mf
    rn_code, rn_name = rn
    li_code, li_name = li
    vf_code, vf_name = vf
    remember_name("malefnasvid", mv_code, mv_name, year)
    remember_name("malaflokkur", mf_code, mf_name, year)
    remember_name("raduneyti", rn_code, rn_name, year)
    remember_name("lidur", li_code, li_name, year)
    remember_name("vidfang", (li_code, vf_code), vf_name, year)
    key = (year, stage, mv_code, mf_code, rn_code, li_code, vf_code, tegund)
    row = (year, stage, mv_code, mf_code, rn_code, li_code, vf_code, tegund, upphaed, source_year)
    existing = BEST.get(key)
    if existing is None or source_year >= existing[9]:
        BEST[key] = row


def load_long(rows, col_map, source_year):
    n = 0
    for row in rows:
        try:
            year = int(row[col_map["year"]])
        except (TypeError, ValueError):
            continue
        stage = row[col_map["afurd"]]
        mv = split_code_name(row[col_map["malefnasvid"]])
        mf = split_code_name(row[col_map["malaflokkur"]])
        rn = split_code_name(row[col_map["raduneyti"]])
        li = split_code_name(row[col_map["lidur"]])
        vf = split_code_name(row[col_map["vidfang"]])
        tegund = row[col_map["tegund"]]
        upphaed = parse_num(row[col_map["upphaed"]])
        if upphaed is None:
            continue
        remember_line(year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year)
        n += 1
    return n


LONG_COL_MAP = {"year": 0, "afurd": 1, "malefnasvid": 3, "malaflokkur": 4,
                 "raduneyti": 5, "lidur": 6, "vidfang": 7, "tegund": 8, "upphaed": 9}


def load_long_xlsx(filename, source_year, label):
    rows = open_rows_xlsx(os.path.join(RAW, filename))
    n = load_long(rows, LONG_COL_MAP, source_year)
    print(f"  {label}: processed {n} long-format rows")


def load_long_csv(filename, source_year, label, encoding="utf-8-sig"):
    rows = open_rows_csv(os.path.join(RAW, filename), encoding=encoding)
    n = load_long(rows, LONG_COL_MAP, source_year)
    print(f"  {label}: processed {n} long-format rows")


def load_wide_yfirlit(filename, source_year, label):
    """2021 'Yfirlit yfir utgjold' file: one column per tegund."""
    rows = open_rows_xlsx(os.path.join(RAW, filename))
    tegund_cols = {
        8: "Gjöld", 9: "Tekjur", 10: "Fjárhæð", 11: "Greiðsla",
        12: "Rekstrarframlög", 13: "Rekstrartilfærslur", 14: "Fjármagnstilfærslur",
        15: "Fjárfestingarframlög", 16: "Heildarútgjöld", 17: "Rekstrartekjur",
    }
    n = 0
    for row in rows:
        try:
            year = int(row[0])
        except (TypeError, ValueError):
            continue
        stage = row[1]
        mv = split_code_name(row[3])
        mf = split_code_name(row[4])
        rn = split_code_name(row[5])
        li = split_code_name(row[6])
        vf = split_code_name(row[7])
        for idx, tegund in tegund_cols.items():
            if idx >= len(row):
                continue
            upphaed = parse_num(row[idx])
            if upphaed is None:
                continue
            remember_line(year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year)
            n += 1
    print(f"  {label}: processed {n} wide-format (melted) rows")


WIDE_GJALDA_TEGUND_COLS_INTERLEAVED = {
    # 2018/2020 style: Ar;Malefnasvid;Heiti;Malaflokkur;Heiti;Raduneyti;Heiti;
    #                  Lidur;Heiti;Vidfang;Heiti;Rekstrarframlog;Rekstrartilfaerslur;
    #                  Fjarfestingarframlog;Fjarmagnstilfaerslur;Heildargjold;
    #                  Rekstrartekjur;Framlag ur rikissjodi;Vidskiptahreyfingar
    11: "Rekstrarframlög", 12: "Rekstrartilfærslur", 13: "Fjárfestingarframlög",
    14: "Fjármagnstilfærslur", 15: "Heildarútgjöld", 16: "Rekstrartekjur",
    17: "Framlag úr ríkissjóði", 18: "Viðskiptahreyfingar",
}


def load_wide_gjalda_interleaved(filename, source_year, label, stage, encoding="iso-8859-1"):
    rows = open_rows_csv(os.path.join(RAW, filename), encoding=encoding)
    n = 0
    for row in rows:
        try:
            year = int(str(row[0]).strip())
        except (TypeError, ValueError):
            continue
        mv_c, mf_c, rn_c, li_c, vf_c = normalize_legacy_codes(
            row[1].strip(), row[3].strip(), row[5].strip(), row[7].strip(), row[9].strip())
        mv = (mv_c, row[2].strip())
        mf = (mf_c, row[4].strip())
        rn = (rn_c, row[6].strip())
        li = (li_c, row[8].strip())
        vf = (vf_c, row[10].strip())
        for idx, tegund in WIDE_GJALDA_TEGUND_COLS_INTERLEAVED.items():
            if idx >= len(row):
                continue
            upphaed = parse_num(row[idx])
            if upphaed is None:
                continue
            remember_line(year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year)
            n += 1
    print(f"  {label}: processed {n} wide-format (melted) rows")


def load_wide_gjalda_xlsx_2019(filename, source_year, label, stage):
    # header: faerslu_ar, mes_svid, mes_svid_heiti, mes_flokkur, mes_flokkur_heiti,
    #         raduneyti, raduneyti_heiti, lidur, lidur_heiti, vidfang, heiti,
    #         rekstrarframlog, rekstrartilfaerslur, fjarframlog, fjarmtilfaerslur,
    #         gjold, tekjur, greidsla, vidskiptahreyfingar
    rows = open_rows_xlsx(os.path.join(RAW, filename))
    tegund_cols = {
        11: "Rekstrarframlög", 12: "Rekstrartilfærslur", 13: "Fjárfestingarframlög",
        14: "Fjármagnstilfærslur", 15: "Heildarútgjöld", 16: "Rekstrartekjur",
        17: "Greiðsla", 18: "Viðskiptahreyfingar",
    }
    n = 0
    for row in rows:
        try:
            year = int(row[0])
        except (TypeError, ValueError):
            continue
        mv_c, mf_c, rn_c, li_c, vf_c = normalize_legacy_codes(row[1], row[3], row[5], row[7], row[9])
        mv = (mv_c, row[2])
        mf = (mf_c, row[4])
        rn = (rn_c, row[6])
        li = (li_c, row[8])
        vf = (vf_c, row[10])
        for idx, tegund in tegund_cols.items():
            if idx >= len(row):
                continue
            upphaed = parse_num(row[idx])
            if upphaed is None:
                continue
            remember_line(year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year)
            n += 1
    print(f"  {label}: processed {n} wide-format (melted) rows")


def load_revenue_detail_csv(conn, filename, source_year, source_doc, encoding="iso-8859-1"):
    rows = open_rows_csv(os.path.join(RAW, filename), encoding=encoding)
    cur = conn.cursor()
    n = 0
    for row in rows:
        try:
            year = int(str(row[0]).strip())
        except (TypeError, ValueError):
            continue
        code, heiti = row[1].strip(), row[2].strip()
        rek = parse_num(row[3])
        grei = parse_num(row[4])
        yf_code = row[5].strip() if len(row) > 5 else None
        yf_heiti = row[6].strip() if len(row) > 6 else None
        cur.execute(
            """INSERT INTO revenue_detail
            (target_year, code, heiti, rekstrargrunnur, greidslugrunnur,
             yfirflokkur_code, yfirflokkur_heiti, source_year)
            VALUES (?,?,?,?,?,?,?,?)""",
            (year, code, heiti, rek, grei, yf_code, yf_heiti, source_year),
        )
        n += 1
    conn.commit()
    print(f"  {source_doc}: inserted {n} revenue_detail rows")


def load_revenue_detail_xlsx(conn, filename, source_year, source_doc):
    rows = open_rows_xlsx(os.path.join(RAW, filename))
    cur = conn.cursor()
    n = 0
    for row in rows:
        try:
            year = int(row[0])
        except (TypeError, ValueError):
            continue
        code, heiti = row[1], row[2]
        rek = parse_num(row[3])
        grei = parse_num(row[4])
        yf_code = row[5] if len(row) > 5 else None
        yf_heiti = row[6] if len(row) > 6 else None
        cur.execute(
            """INSERT INTO revenue_detail
            (target_year, code, heiti, rekstrargrunnur, greidslugrunnur,
             yfirflokkur_code, yfirflokkur_heiti, source_year)
            VALUES (?,?,?,?,?,?,?,?)""",
            (year, code, heiti, rek, grei, yf_code, yf_heiti, source_year),
        )
        n += 1
    conn.commit()
    print(f"  {source_doc}: inserted {n} revenue_detail rows")


def init_db(conn):
    conn.executescript(
        """
        PRAGMA journal_mode=OFF;

        CREATE TABLE budget_lines (
            id INTEGER PRIMARY KEY,
            target_year INTEGER NOT NULL,
            stage TEXT NOT NULL,
            malefnasvid_code TEXT,
            malaflokkur_code TEXT,
            raduneyti_code TEXT,
            lidur_code TEXT,
            vidfang_code TEXT,
            tegund TEXT NOT NULL,
            upphaed REAL NOT NULL,
            source_year INTEGER NOT NULL
        );
        CREATE INDEX idx_bl_target_year ON budget_lines(target_year);
        CREATE INDEX idx_bl_malefnasvid ON budget_lines(malefnasvid_code);
        CREATE INDEX idx_bl_raduneyti ON budget_lines(raduneyti_code);
        CREATE INDEX idx_bl_lidur ON budget_lines(lidur_code);

        CREATE TABLE revenue_detail (
            id INTEGER PRIMARY KEY,
            target_year INTEGER NOT NULL,
            code TEXT,
            heiti TEXT,
            rekstrargrunnur REAL,
            greidslugrunnur REAL,
            yfirflokkur_code TEXT,
            yfirflokkur_heiti TEXT,
            source_year INTEGER NOT NULL
        );
        CREATE INDEX idx_rd_target_year ON revenue_detail(target_year);

        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            year INTEGER NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            kind TEXT NOT NULL,
            note TEXT
        );

        CREATE TABLE malefnasvid_catalog (
            code TEXT PRIMARY KEY,
            nafn TEXT NOT NULL,
            first_year INTEGER,
            last_year INTEGER
        );
        CREATE TABLE malaflokkur_catalog (
            code TEXT PRIMARY KEY,
            nafn TEXT NOT NULL,
            first_year INTEGER,
            last_year INTEGER
        );
        CREATE TABLE raduneyti_catalog (
            code TEXT PRIMARY KEY,
            nafn TEXT NOT NULL,
            first_year INTEGER,
            last_year INTEGER
        );
        CREATE TABLE lidur_catalog (
            code TEXT PRIMARY KEY,
            nafn TEXT NOT NULL,
            first_year INTEGER,
            last_year INTEGER
        );
        CREATE TABLE vidfang_catalog (
            lidur_code TEXT NOT NULL,
            vidfang_code TEXT NOT NULL,
            nafn TEXT NOT NULL,
            PRIMARY KEY (lidur_code, vidfang_code)
        );

        CREATE VIEW budget_lines_v AS
        SELECT bl.id, bl.target_year, bl.stage,
               bl.malefnasvid_code, mv.nafn AS malefnasvid_nafn,
               bl.malaflokkur_code, mf.nafn AS malaflokkur_nafn,
               bl.raduneyti_code, rn.nafn AS raduneyti_nafn,
               bl.lidur_code, li.nafn AS lidur_nafn,
               bl.vidfang_code, vf.nafn AS vidfang_nafn,
               bl.tegund, bl.upphaed, bl.source_year
        FROM budget_lines bl
        LEFT JOIN malefnasvid_catalog mv ON mv.code = bl.malefnasvid_code
        LEFT JOIN malaflokkur_catalog mf ON mf.code = bl.malaflokkur_code
        LEFT JOIN raduneyti_catalog rn ON rn.code = bl.raduneyti_code
        LEFT JOIN lidur_catalog li ON li.code = bl.lidur_code
        LEFT JOIN vidfang_catalog vf ON vf.lidur_code = bl.lidur_code AND vf.vidfang_code = bl.vidfang_code;
        """
    )


def flush_budget_lines(conn):
    cur = conn.cursor()
    cur.executemany(
        """INSERT INTO budget_lines
        (target_year, stage, malefnasvid_code, malaflokkur_code, raduneyti_code,
         lidur_code, vidfang_code, tegund, upphaed, source_year)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        list(BEST.values()),
    )
    conn.commit()
    print(f"Flushed {len(BEST)} deduplicated rows into budget_lines")


def flush_catalogs(conn):
    cur = conn.cursor()

    # first/last year per code, derived straight from BEST (cheaper than re-scanning)
    year_range = {"malefnasvid": {}, "malaflokkur": {}, "raduneyti": {}, "lidur": {}}
    for (year, stage, mv, mf, rn, li, vf, tegund, upphaed, source_year) in BEST.values():
        for table, code in (("malefnasvid", mv), ("malaflokkur", mf),
                             ("raduneyti", rn), ("lidur", li)):
            if code is None:
                continue
            lo, hi = year_range[table].get(code, (year, year))
            year_range[table][code] = (min(lo, year), max(hi, year))

    for table, tbl_name in (("malefnasvid", "malefnasvid_catalog"),
                             ("malaflokkur", "malaflokkur_catalog"),
                             ("raduneyti", "raduneyti_catalog"),
                             ("lidur", "lidur_catalog")):
        rows = []
        for code, (name, _y) in NAMES[table].items():
            lo, hi = year_range[table].get(code, (None, None))
            rows.append((code, name, lo, hi))
        cur.executemany(f"INSERT INTO {tbl_name} (code, nafn, first_year, last_year) VALUES (?,?,?,?)", rows)

    vf_rows = [(li_code, vf_code, name) for (li_code, vf_code), (name, _y) in NAMES["vidfang"].items()
               if li_code is not None and vf_code is not None]
    cur.executemany("INSERT INTO vidfang_catalog (lidur_code, vidfang_code, nafn) VALUES (?,?,?)", vf_rows)
    conn.commit()


DOCUMENTS = [
    (2018, "Fjárlagasundurliðun gjalda 2018 (frumvarp)",
     "https://www.stjornarradid.is/library/?itemid=05592db8-e0ac-11e7-9420-005056bc4d74",
     "expenditure_breakdown",
     "Elsta aðgengilega sundurliðun í þessum gagnagrunni. Stig (frumvarp) er ályktað af "
     "staðsetningu skjalsins innan skjalalista frumvarpsins, ekki staðfest í sjálfu skjalinu."),
    (2018, "Fjárlagasundurliðun tekna 2018 (frumvarp)",
     "https://www.stjornarradid.is/library/?itemid=05592db9-e0ac-11e7-9420-005056bc4d74",
     "revenue_breakdown", ""),
    (2019, "Fjárlagasundurliðun gjalda 2019 (samþykkt fjárlög)",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/fj%c3%a1rlagasundurli%c3%b0un%20gjalda%202019.xlsx",
     "expenditure_breakdown", ""),
    (2019, "Fjárlagasundurliðun tekna 2019 (samþykkt fjárlög)",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/fj%c3%a1rlagasundurli%c3%b0un%20tekna.xlsx",
     "revenue_breakdown", ""),
    (2020, "Fjárlagasundurliðun gjalda 2020 (frumvarp)",
     "https://www.stjornarradid.is/library/?itemid=41f9d4ac-cfec-11e9-9449-005056bc530c",
     "expenditure_breakdown", ""),
    (2020, "Fjárlagasundurliðun tekna 2020 (frumvarp)",
     "https://www.stjornarradid.is/library/?itemid=41f9d4ab-cfec-11e9-9449-005056bc530c",
     "revenue_breakdown", ""),
    (2021, "Yfirlit yfir útgjöld í fjárlagafrumvarpi 2021",
     "https://www.stjornarradid.is/library/?itemid=2423aeaf-07be-11eb-8123-005056bc8c60",
     "talnagogn", "Nær yfir árin 2019-2023 (ríkisreikningur/fjárlög/frumvarp/áætlun)."),
    (2022, "Fjárlagafrumvarp 2022 Talnagögn",
     "https://www.stjornarradid.is/library/?itemid=e540f155-5150-11ec-8142-005056bc8c60",
     "talnagogn", "Nær yfir árin 2020-2024."),
    (2022, "Fjárlög 2022 talnagögn",
     "https://www.stjornarradid.is/library/?itemid=6998355b-82c4-11ec-8144-005056bc8c60",
     "talnagogn", "Nær yfir árin 2020-2024."),
    (2023, "Fjárlagafrumvarp 2023 Talnagögn",
     "https://www.stjornarradid.is/library/03-Verkefni/Efnahagsmal-og-opinber-fjarmal/Fjarlagafrumvarp-fyrir-2023/Fj%c3%a1rlagafrumvarp%202023%20Talnag%c3%b6gn.xlsx",
     "talnagogn", "Nær yfir árin 2021-2025."),
    (2023, "Fjárlög 2023 talnagögn",
     "https://www.stjornarradid.is/library/?itemid=e3172217-ab25-11ed-9bb5-f992086adea7",
     "talnagogn", "Nær yfir árin 2021-2025."),
    (2024, "Talnagögn úr fjárlagafrumvarpi 2024",
     "https://www.stjornarradid.is/library/?itemid=df59c487-5097-11ee-9bbe-005056bc4727",
     "talnagogn", "Nær yfir árin 2022-2026."),
    (2024, "Fjárlög 2024 talnagögn",
     "https://stjornarradid.is/library/02-Rit--skyrslur-og-skrar/Fj%c3%a1rl%c3%b6g%202024%20csv.csv",
     "talnagogn", "Aðeins árið 2024."),
    (2025, "Talnagögn úr fjárlagafrumvarpi 2025",
     "https://www.stjornarradid.is/library/?itemid=85b4f2ac-702e-11ef-b888-005056bcde1f",
     "talnagogn", "Nær yfir árin 2023-2027."),
    (2026, "Talnagögn úr fjárlagafrumvarpi 2026",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/Talnag%c3%b6gn%20%c3%bar%20fj%c3%a1rlagafrumvarpi%20-%20003.csv",
     "talnagogn", "Nær yfir árin 2024-2028."),
    (2027, "Talnagögn úr fjárlagafrumvarpi 2027",
     "https://www.stjornarradid.is/library/?itemid=cfa1b9d9-e504-4b7e-a73d-8c48a7c95004",
     "talnagogn", "Nær yfir árin 2025-2029."),
    (2027, "Frumvarp til fjárlaga 2027",
     "https://www.stjornarradid.is/library/?itemid=6d41488b-6385-438f-8ae7-0eedddffe8fe",
     "frumvarp_pdf", ""),
    (2026, "Frumvarp til fjárlaga 2026",
     "https://www.stjornarradid.is/library/?itemid=ec506b11-8b23-11f0-b895-005056bcde1f",
     "frumvarp_pdf", ""),
    (2026, "Samþykkt fjárlög fyrir árið 2026",
     "https://www.stjornarradid.is/library/?itemid=d5756c8e-dfec-11f0-b898-005056bcde1f",
     "fjarlog_pdf", ""),
    (2025, "Frumvarp til fjárlaga 2025",
     "https://www.stjornarradid.is/library/?itemid=7298d79e-6ecd-11ef-b888-005056bcde1f",
     "frumvarp_pdf", ""),
    (2025, "Samþykkt fjárlög fyrir árið 2025",
     "https://www.stjornarradid.is/library/?itemid=b90a5377-acad-11ef-b88a-005056bcde1f",
     "fjarlog_pdf", ""),
    (2024, "Frumvarp til fjárlaga 2024",
     "https://www.stjornarradid.is/library/?itemid=0094d687-50bf-11ee-9bbe-005056bc4727",
     "frumvarp_pdf", ""),
    (2024, "Samþykkt fjárlög fyrir árið 2024",
     "https://www.stjornarradid.is/library/?itemid=d4236ad1-d196-11ee-b882-005056bcde1f",
     "fjarlog_pdf", ""),
    (2023, "Fjárlagafrumvarp fyrir árið 2023",
     "https://www.stjornarradid.is/library/01--Frettatengt---myndir-og-skrar/Skjol---Frettatengt/FJR_Fjarlagafrumvarp_060922_vefur.pdf",
     "frumvarp_pdf", ""),
    (2023, "Samþykkt fjárlög fyrir árið 2023",
     "https://www.stjornarradid.is/library/01--Frettatengt---myndir-og-skrar/Skjol---Frettatengt/Fj%c3%a1rl%c3%b6g%202023.pdf",
     "fjarlog_pdf", ""),
    (2022, "Fjárlagafrumvarp fyrir árið 2022",
     "https://www.stjornarradid.is/library/?itemid=5ff091fa-514f-11ec-8142-005056bc8c60",
     "frumvarp_pdf", ""),
    (2021, "Fjárlagafrumvarp fyrir árið 2021",
     "https://www.stjornarradid.is/library/?itemid=11041167-03ca-11eb-8123-005056bc8c60",
     "frumvarp_pdf", ""),
    (2020, "Fjárlög 2020",
     "https://www.stjornarradid.is/library/?itemid=3c54b43f-3225-11ea-9451-005056bc530c",
     "fjarlog_pdf", ""),
    (2020, "Frumvarp til fjárlaga fyrir árið 2020",
     "https://www.stjornarradid.is/library/?itemid=1adfa80a-cffa-11e9-9449-005056bc530c",
     "frumvarp_pdf", ""),
    (2019, "Fjárlög 2019",
     "https://www.stjornarradid.is/library/01--Frettatengt---myndir-og-skrar/FJR/Fjarlog%202019_lokaskjal.pdf",
     "fjarlog_pdf", ""),
    (2019, "Frumvarp til fjárlaga fyrir árið 2019",
     "https://www.stjornarradid.is/library/03-Verkefni/Efnahagsmal-og-opinber-fjarmal/Fjarlagafrumvarp-2019/Frumvarp_til_fjarlaga_2019.pdf",
     "frumvarp_pdf", ""),
    (2018, "Fylgirit með fjárlögum 2018",
     "https://www.stjornarradid.is/library/?itemid=412669af-027c-11e8-9423-005056bc4d74",
     "fylgirit_pdf", ""),
]


def load_documents(conn):
    cur = conn.cursor()
    for year, title, url, kind, note in DOCUMENTS:
        cur.execute(
            "INSERT INTO documents (year, title, url, kind, note) VALUES (?,?,?,?,?)",
            (year, title, url, kind, note),
        )
    conn.commit()
    with open(SOURCES_JSON, "w", encoding="utf-8") as f:
        json.dump(
            [{"year": y, "title": t, "url": u, "kind": k, "note": n} for y, t, u, k, n in DOCUMENTS],
            f, ensure_ascii=False, indent=2,
        )


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    print("Loading long-format (Málefnasvið-classified) sources...")
    load_wide_yfirlit("2021_yfirlit.xlsx", 2021, "Yfirlit yfir útgjöld í fjárlagafrumvarpi 2021")
    load_long_xlsx("2022_frumvarp.xlsx", 2022, "Fjárlagafrumvarp 2022 Talnagögn")
    load_long_xlsx("2022_enacted.xlsx", 2022, "Fjárlög 2022 talnagögn")
    load_long_xlsx("2023_frumvarp.xlsx", 2023, "Fjárlagafrumvarp 2023 Talnagögn")
    load_long_xlsx("2023_enacted.xlsx", 2023, "Fjárlög 2023 talnagögn")
    load_long_xlsx("2024_frumvarp.xlsx", 2024, "Talnagögn úr fjárlagafrumvarpi 2024")
    load_long_csv("2024_enacted.csv", 2024, "Fjárlög 2024 talnagögn", encoding="utf-8-sig")
    load_long_xlsx("2025_frumvarp.xlsx", 2025, "Talnagögn úr fjárlagafrumvarpi 2025")
    load_long_csv("2026.csv", 2026, "Talnagögn úr fjárlagafrumvarpi 2026", encoding="utf-8-sig")
    load_long_xlsx("2027.xlsx", 2027, "Talnagögn úr fjárlagafrumvarpi 2027")

    print("Loading older (2018-2020) ministry-level breakdown sources...")
    load_wide_gjalda_interleaved("2018_gjalda.csv", 2018,
                                  "Fjárlagasundurliðun gjalda 2018 (frumvarp)", "Frumvarp",
                                  encoding="iso-8859-1")
    load_wide_gjalda_xlsx_2019("2019_gjalda.xlsx", 2019,
                                "Fjárlagasundurliðun gjalda 2019 (samþykkt fjárlög)", "Fjárlög")
    load_wide_gjalda_interleaved("2020_gjalda.csv", 2020,
                                  "Fjárlagasundurliðun gjalda 2020 (frumvarp)", "Frumvarp",
                                  encoding="iso-8859-1")

    flush_budget_lines(conn)
    flush_catalogs(conn)

    print("Loading revenue tax-code detail (2018-2020 only)...")
    load_revenue_detail_csv(conn, "2018_tekna.csv", 2018,
                             "Fjárlagasundurliðun tekna 2018 (frumvarp)", encoding="iso-8859-1")
    load_revenue_detail_xlsx(conn, "2019_tekna.xlsx", 2019,
                              "Fjárlagasundurliðun tekna 2019 (samþykkt fjárlög)")
    load_revenue_detail_csv(conn, "2020_tekna.csv", 2020,
                             "Fjárlagasundurliðun tekna 2020 (frumvarp)", encoding="iso-8859-1")

    print("Loading document metadata...")
    load_documents(conn)

    cur = conn.execute("SELECT COUNT(*) FROM budget_lines")
    print(f"Total budget_lines rows: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM revenue_detail")
    print(f"Total revenue_detail rows: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT MIN(target_year), MAX(target_year) FROM budget_lines")
    print(f"Year range: {cur.fetchone()}")

    conn.execute("VACUUM")
    conn.close()
    print(f"Wrote {DB_PATH}")


if __name__ == "__main__":
    main()
