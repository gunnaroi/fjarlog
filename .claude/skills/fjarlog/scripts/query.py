#!/usr/bin/env python3
"""Query the fjarlog (Icelandic state budget) SQLite database.

Zero dependencies (stdlib sqlite3 only). Every subcommand prints JSON to
stdout. Run `query.py <subcommand> --help` for that subcommand's options.

Subcommands:
  list-years            years covered, stages available, source docs per year
  list-malefnasvid       catalog of policy areas
  list-malaflokkar       catalog of policy sub-areas
  list-raduneyti         catalog of ministries
  search-line-items      find an agency/program's exact code by name
  get-expenditure        core lookup: summed spending for a filter/year(s)/stage
  compare-years          year-over-year series with change/% change
  compare-stages         bill vs. law vs. actual for one year
  top-movers             biggest increases/decreases between two years
  revenue-detail         tax-code-level revenue (2018-2020 only)
  list-documents         source document metadata, for citation
  sql                    escape hatch: run an arbitrary read-only SELECT
"""
import argparse
import json
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "fjarlog.db")
STAGE_PRIORITY = ["Ríkisreikningur", "Fjárlög", "Frumvarp", "Áætlun"]
STAGES = {"Frumvarp", "Fjárlög", "Ríkisreikningur", "Áætlun"}


def connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def best_stage(available):
    for s in STAGE_PRIORITY:
        if s in available:
            return s
    return available[0] if available else None


def build_where(args, extra_clauses=None, extra_params=None):
    clauses = list(extra_clauses or [])
    params = dict(extra_params or {})
    for field in ("malefnasvid_code", "malaflokkur_code", "raduneyti_code", "lidur_code", "vidfang_code"):
        val = getattr(args, field, None)
        if val:
            clauses.append(f"{field} = :{field}")
            params[field] = val
    if getattr(args, "name_contains", None):
        clauses.append(
            "(malefnasvid_nafn LIKE :name OR malaflokkur_nafn LIKE :name OR "
            "raduneyti_nafn LIKE :name OR lidur_nafn LIKE :name OR vidfang_nafn LIKE :name)"
        )
        params["name"] = f"%{args.name_contains}%"
    return clauses, params


def add_line_filter_args(p):
    p.add_argument("--malefnasvid", dest="malefnasvid_code", help="Málefnasvið code, e.g. '08'")
    p.add_argument("--malaflokkur", dest="malaflokkur_code", help="Málaflokkur code, e.g. '08.20'")
    p.add_argument("--raduneyti", dest="raduneyti_code", help="Ministry code, e.g. '09'")
    p.add_argument("--lidur", dest="lidur_code", help="Budget line/agency code, e.g. '07-275'")
    p.add_argument("--vidfang", dest="vidfang_code", help="Sub-item code, e.g. '110'")
    p.add_argument("--search", dest="name_contains", help="Substring to match against any name field")


# --- subcommands -------------------------------------------------------

def cmd_list_years(conn, args):
    rows = conn.execute(
        "SELECT target_year, stage, COUNT(*) as n FROM budget_lines GROUP BY target_year, stage ORDER BY target_year"
    ).fetchall()
    docs = conn.execute("SELECT year, title, kind FROM documents ORDER BY year").fetchall()
    by_year = {}
    for r in rows:
        y = by_year.setdefault(r["target_year"], {"year": r["target_year"], "stages": [], "documents": []})
        y["stages"].append(r["stage"])
    for d in docs:
        y = by_year.setdefault(d["year"], {"year": d["year"], "stages": [], "documents": []})
        y["documents"].append({"title": d["title"], "kind": d["kind"]})
    return [by_year[y] for y in sorted(by_year)]


def cmd_list_malefnasvid(conn, args):
    clauses, params = [], {}
    if args.year is not None:
        clauses.append("first_year <= :year AND last_year >= :year")
        params["year"] = args.year
    if args.search:
        clauses.append("nafn LIKE :name")
        params["name"] = f"%{args.search}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return rows_to_dicts(conn.execute(
        f"SELECT code, nafn, first_year, last_year FROM malefnasvid_catalog {where} ORDER BY code", params
    ).fetchall())


def cmd_list_malaflokkar(conn, args):
    clauses, params = [], {}
    if args.malefnasvid:
        clauses.append("code LIKE :prefix")
        params["prefix"] = f"{args.malefnasvid}.%"
    if args.search:
        clauses.append("nafn LIKE :name")
        params["name"] = f"%{args.search}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return rows_to_dicts(conn.execute(
        f"SELECT code, nafn, first_year, last_year FROM malaflokkur_catalog {where} ORDER BY code", params
    ).fetchall())


def cmd_list_raduneyti(conn, args):
    clauses, params = [], {}
    if args.year is not None:
        clauses.append("first_year <= :year AND last_year >= :year")
        params["year"] = args.year
    if args.search:
        clauses.append("nafn LIKE :name")
        params["name"] = f"%{args.search}%"
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return rows_to_dicts(conn.execute(
        f"SELECT code, nafn, first_year, last_year FROM raduneyti_catalog {where} ORDER BY code", params
    ).fetchall())


def cmd_search_line_items(conn, args):
    clauses = ["(lidur_nafn LIKE :name OR vidfang_nafn LIKE :name)"]
    params = {"name": f"%{args.search}%", "limit": args.limit}
    if args.raduneyti:
        clauses.append("raduneyti_code = :raduneyti")
        params["raduneyti"] = args.raduneyti
    if args.malefnasvid:
        clauses.append("malefnasvid_code = :malefnasvid")
        params["malefnasvid"] = args.malefnasvid
    where = "WHERE " + " AND ".join(clauses)
    return rows_to_dicts(conn.execute(
        f"""SELECT DISTINCT malefnasvid_code, malefnasvid_nafn, malaflokkur_code, malaflokkur_nafn,
                   raduneyti_code, raduneyti_nafn, lidur_code, lidur_nafn, vidfang_code, vidfang_nafn
            FROM budget_lines_v {where} LIMIT :limit""", params
    ).fetchall())


def cmd_get_expenditure(conn, args):
    tegund = args.tegund or "Heildarútgjöld"
    clauses, params = build_where(args, extra_params={"tegund": tegund})
    clauses.append("tegund = :tegund")
    if args.stage:
        clauses.append("stage = :stage")
        params["stage"] = args.stage
    if args.year:
        placeholders = []
        for i, y in enumerate(args.year):
            key = f"year{i}"
            placeholders.append(f":{key}")
            params[key] = y
        clauses.append(f"target_year IN ({','.join(placeholders)})")
    where = "WHERE " + " AND ".join(clauses)
    rows = rows_to_dicts(conn.execute(
        f"""SELECT target_year, stage, ROUND(SUM(upphaed), 1) as total, COUNT(*) as n_lines
            FROM budget_lines_v {where}
            GROUP BY target_year, stage ORDER BY target_year, stage""", params
    ).fetchall())
    return {"tegund": tegund, "unit": "m.kr.", "rows": rows}


def cmd_compare_years(conn, args):
    tegund = args.tegund or "Heildarútgjöld"
    clauses, params = build_where(args, extra_params={"tegund": tegund})
    clauses.append("tegund = :tegund")
    if args.years:
        placeholders = []
        for i, y in enumerate(args.years):
            key = f"year{i}"
            placeholders.append(f":{key}")
            params[key] = y
        clauses.append(f"target_year IN ({','.join(placeholders)})")
    if args.stage:
        clauses.append("stage = :stage")
        params["stage"] = args.stage
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(
        f"""SELECT target_year, stage, SUM(upphaed) as total FROM budget_lines_v {where}
            GROUP BY target_year, stage ORDER BY target_year""", params
    ).fetchall()
    by_year = {}
    for r in rows:
        by_year.setdefault(r["target_year"], []).append({"stage": r["stage"], "total": r["total"]})
    series = []
    for year in sorted(by_year):
        options = by_year[year]
        stage = args.stage or best_stage([o["stage"] for o in options])
        match = next((o for o in options if o["stage"] == stage), None)
        series.append({"year": year, "stage": stage, "total": round(match["total"], 1) if match else None})
    for i in range(1, len(series)):
        prev, cur = series[i - 1]["total"], series[i]["total"]
        if prev is not None and cur is not None:
            series[i]["change"] = round(cur - prev, 1)
            series[i]["pct_change"] = round((cur - prev) / abs(prev) * 100, 1) if prev else None
        else:
            series[i]["change"] = None
            series[i]["pct_change"] = None
    return {
        "tegund": tegund, "unit": "m.kr.",
        "note": "stage is auto-picked per year (Ríkisreikningur > Fjárlög > Frumvarp > Áætlun) unless --stage was given explicitly",
        "series": series,
    }


def cmd_compare_stages(conn, args):
    tegund = args.tegund or "Heildarútgjöld"
    clauses, params = build_where(args, extra_params={"tegund": tegund, "year": args.year})
    clauses += ["tegund = :tegund", "target_year = :year"]
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(
        f"SELECT stage, ROUND(SUM(upphaed), 1) as total FROM budget_lines_v {where} GROUP BY stage", params
    ).fetchall()
    by_stage = {r["stage"]: r["total"] for r in rows}
    return {
        "year": args.year, "tegund": tegund, "unit": "m.kr.",
        "frumvarp": by_stage.get("Frumvarp"),
        "fjarlog": by_stage.get("Fjárlög"),
        "rikisreikningur": by_stage.get("Ríkisreikningur"),
        "aaetlun": by_stage.get("Áætlun"),
    }


def cmd_top_movers(conn, args):
    tegund = args.tegund or "Heildarútgjöld"
    code_col = f"{args.group_by}_code"
    params = {"tegund": tegund, "year_from": args.year_from, "year_to": args.year_to}
    stage_clause = ""
    if args.stage:
        stage_clause = "AND stage = :stage"
        params["stage"] = args.stage
    rows = conn.execute(
        f"""SELECT target_year, stage, {code_col} as code, SUM(upphaed) as total
            FROM budget_lines
            WHERE tegund = :tegund AND target_year IN (:year_from, :year_to) {stage_clause} AND {code_col} IS NOT NULL
            GROUP BY target_year, stage, {code_col}""", params
    ).fetchall()
    nested = {}
    for r in rows:
        nested.setdefault(r["code"], {}).setdefault(r["target_year"], {})[r["stage"]] = r["total"]
    catalog_table = {"malefnasvid": "malefnasvid_catalog", "raduneyti": "raduneyti_catalog", "malaflokkur": "malaflokkur_catalog"}[args.group_by]
    names = {r["code"]: r["nafn"] for r in conn.execute(f"SELECT code, nafn FROM {catalog_table}").fetchall()}
    results = []
    for code, year_map in nested.items():
        from_stages = list(year_map.get(args.year_from, {}).keys())
        to_stages = list(year_map.get(args.year_to, {}).keys())
        from_stage = args.stage or best_stage(from_stages)
        to_stage = args.stage or best_stage(to_stages)
        frm = year_map.get(args.year_from, {}).get(from_stage) if from_stage else None
        to = year_map.get(args.year_to, {}).get(to_stage) if to_stage else None
        change = round(to - frm, 1) if (frm is not None and to is not None) else None
        pct = round((to - frm) / abs(frm) * 100, 1) if (frm and to is not None) else None
        results.append({"code": code, "name": names.get(code), "from": frm, "to": to, "change": change, "pct_change": pct})
    results = [r for r in results if r["change"] is not None]
    if args.direction == "increase":
        results = [r for r in results if r["change"] > 0]
    elif args.direction == "decrease":
        results = [r for r in results if r["change"] < 0]
    results.sort(key=lambda r: abs(r["change"]), reverse=True)
    return {
        "tegund": tegund, "unit": "m.kr.", "group_by": args.group_by,
        "year_from": args.year_from, "year_to": args.year_to,
        "top": results[: args.limit],
    }


def cmd_revenue_detail(conn, args):
    if args.year < 2018 or args.year > 2020:
        return {
            "error": "Tax-code-level revenue detail is only available for 2018-2020 in this dataset. "
            "For 2021-2027, use get-expenditure with --tegund Rekstrartekjur for agency self-generated "
            "revenue (this dataset does not include a full tax-revenue breakdown for those years) or "
            "consult list-documents for the original 'Tafla 3: Skipting tekna' PDF/table."
        }
    clauses, params = ["target_year = :year"], {"year": args.year}
    if args.search:
        clauses.append("heiti LIKE :name")
        params["name"] = f"%{args.search}%"
    if args.yfirflokkur:
        clauses.append("yfirflokkur_code = :yf")
        params["yf"] = args.yfirflokkur
    where = "WHERE " + " AND ".join(clauses)
    rows = rows_to_dicts(conn.execute(
        f"""SELECT code, heiti, rekstrargrunnur, greidslugrunnur, yfirflokkur_code, yfirflokkur_heiti
            FROM revenue_detail {where} ORDER BY yfirflokkur_code, code""", params
    ).fetchall())
    return {"year": args.year, "unit": "m.kr.", "rows": rows}


def cmd_list_documents(conn, args):
    clauses, params = [], {}
    if args.year is not None:
        clauses.append("year = :year")
        params["year"] = args.year
    if args.kind:
        clauses.append("kind = :kind")
        params["kind"] = args.kind
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return rows_to_dicts(conn.execute(
        f"SELECT year, title, url, kind, note FROM documents {where} ORDER BY year, kind", params
    ).fetchall())


def cmd_sql(conn, args):
    stripped = args.query.strip().rstrip(";")
    if not stripped.lower().startswith("select"):
        return {"error": "Only SELECT statements are allowed."}
    if ";" in stripped:
        return {"error": "Only a single statement is allowed."}
    rows = rows_to_dicts(conn.execute(stripped).fetchmany(args.limit))
    return rows


# --- CLI wiring ----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-years")

    p = sub.add_parser("list-malefnasvid")
    p.add_argument("--year", type=int)
    p.add_argument("--search")

    p = sub.add_parser("list-malaflokkar")
    p.add_argument("--malefnasvid")
    p.add_argument("--search")

    p = sub.add_parser("list-raduneyti")
    p.add_argument("--year", type=int)
    p.add_argument("--search")

    p = sub.add_parser("search-line-items")
    p.add_argument("--search", required=True)
    p.add_argument("--raduneyti")
    p.add_argument("--malefnasvid")
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("get-expenditure")
    add_line_filter_args(p)
    p.add_argument("--year", type=int, nargs="+")
    p.add_argument("--stage", choices=sorted(STAGES))
    p.add_argument("--tegund", default="Heildarútgjöld")

    p = sub.add_parser("compare-years")
    add_line_filter_args(p)
    p.add_argument("--years", type=int, nargs="+")
    p.add_argument("--stage", choices=sorted(STAGES))
    p.add_argument("--tegund", default="Heildarútgjöld")

    p = sub.add_parser("compare-stages")
    add_line_filter_args(p)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--tegund", default="Heildarútgjöld")

    p = sub.add_parser("top-movers")
    p.add_argument("--year-from", type=int, required=True)
    p.add_argument("--year-to", type=int, required=True)
    p.add_argument("--group-by", choices=["malefnasvid", "raduneyti", "malaflokkur"], default="malefnasvid")
    p.add_argument("--tegund", default="Heildarútgjöld")
    p.add_argument("--stage", choices=sorted(STAGES))
    p.add_argument("--direction", choices=["increase", "decrease", "both"], default="both")
    p.add_argument("--limit", type=int, default=10)

    p = sub.add_parser("revenue-detail")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--search")
    p.add_argument("--yfirflokkur")

    p = sub.add_parser("list-documents")
    p.add_argument("--year", type=int)
    p.add_argument("--kind")

    p = sub.add_parser("sql")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=500)

    args = parser.parse_args()
    conn = connect()
    handler = {
        "list-years": cmd_list_years,
        "list-malefnasvid": cmd_list_malefnasvid,
        "list-malaflokkar": cmd_list_malaflokkar,
        "list-raduneyti": cmd_list_raduneyti,
        "search-line-items": cmd_search_line_items,
        "get-expenditure": cmd_get_expenditure,
        "compare-years": cmd_compare_years,
        "compare-stages": cmd_compare_stages,
        "top-movers": cmd_top_movers,
        "revenue-detail": cmd_revenue_detail,
        "list-documents": cmd_list_documents,
        "sql": cmd_sql,
    }[args.command]
    result = handler(conn, args)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    print()


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.stderr.close()
        sys.exit(0)
