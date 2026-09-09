#!/usr/bin/env python3
"""Download the raw fjarlog (Icelandic state budget) source files used by etl.py.

Source: stjornarradid.is (Icelandic Government), Ministry of Finance and
Economics (fjarmala- og efnahagsraduneytid). Files are published as part of
each year's "Frumvarp til fjarlaga" (budget bill) / "Fjarlog" (enacted
budget) documentation packages, under CC / public-sector open-data terms.

Run this, then run etl.py, to rebuild data/fjarlog.db from scratch.
Downloads go into scripts/raw/ (not committed to git).
"""
import os
import urllib.request

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")

# (output filename, source URL, human title, notes)
SOURCES = [
    ("2018_gjalda.csv",
     "https://www.stjornarradid.is/library/?itemid=05592db8-e0ac-11e7-9420-005056bc4d74",
     "Fjarlagasundurlidun gjalda 2018 (fjarlagafrumvarp)",
     "ISO-8859-1 encoded ';'-delimited text"),
    ("2018_tekna.csv",
     "https://www.stjornarradid.is/library/?itemid=05592db9-e0ac-11e7-9420-005056bc4d74",
     "Fjarlagasundurlidun tekna 2018 (fjarlagafrumvarp)",
     "ISO-8859-1 encoded ';'-delimited text"),
    ("2019_gjalda.xlsx",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/fj%c3%a1rlagasundurli%c3%b0un%20gjalda%202019.xlsx",
     "Fjarlagasundurlidun gjalda 2019 (samthykkt fjarlog)", ""),
    ("2019_tekna.xlsx",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/fj%c3%a1rlagasundurli%c3%b0un%20tekna.xlsx",
     "Fjarlagasundurlidun tekna 2019 (samthykkt fjarlog)", ""),
    ("2020_gjalda.csv",
     "https://www.stjornarradid.is/library/?itemid=41f9d4ac-cfec-11e9-9449-005056bc530c",
     "Fjarlagasundurlidun gjalda 2020 (fjarlagafrumvarp)",
     "ISO-8859-1 encoded ';'-delimited text"),
    ("2020_tekna.csv",
     "https://www.stjornarradid.is/library/?itemid=41f9d4ab-cfec-11e9-9449-005056bc530c",
     "Fjarlagasundurlidun tekna 2020 (fjarlagafrumvarp)",
     "ISO-8859-1 encoded ';'-delimited text"),
    ("2021_yfirlit.xlsx",
     "https://www.stjornarradid.is/library/?itemid=2423aeaf-07be-11eb-8123-005056bc8c60",
     "Yfirlit yfir utgjold i fjarlagafrumvarpi 2021 (covers 2019-2023)", ""),
    ("2022_frumvarp.xlsx",
     "https://www.stjornarradid.is/library/?itemid=e540f155-5150-11ec-8142-005056bc8c60",
     "Fjarlagafrumvarp 2022 Talnagogn (covers 2020-2024)", ""),
    ("2022_enacted.xlsx",
     "https://www.stjornarradid.is/library/?itemid=6998355b-82c4-11ec-8144-005056bc8c60",
     "Fjarlog 2022 talnagogn (covers 2020-2024)", ""),
    ("2023_frumvarp.xlsx",
     "https://www.stjornarradid.is/library/03-Verkefni/Efnahagsmal-og-opinber-fjarmal/Fjarlagafrumvarp-fyrir-2023/Fj%c3%a1rlagafrumvarp%202023%20Talnag%c3%b6gn.xlsx",
     "Fjarlagafrumvarp 2023 Talnagogn (covers 2021-2025)", ""),
    ("2023_enacted.xlsx",
     "https://www.stjornarradid.is/library/?itemid=e3172217-ab25-11ed-9bb5-f992086adea7",
     "Fjarlog 2023 talnagogn (covers 2021-2025)", ""),
    ("2024_frumvarp.xlsx",
     "https://www.stjornarradid.is/library/?itemid=df59c487-5097-11ee-9bbe-005056bc4727",
     "Talnagogn ur fjarlagafrumvarpi 2024 (covers 2022-2026)", ""),
    ("2024_enacted.csv",
     "https://stjornarradid.is/library/02-Rit--skyrslur-og-skrar/Fj%c3%a1rl%c3%b6g%202024%20csv.csv",
     "Fjarlog 2024 talnagogn (2024 only)", "UTF-8 BOM ';'-delimited text"),
    ("2025_frumvarp.xlsx",
     "https://www.stjornarradid.is/library/?itemid=85b4f2ac-702e-11ef-b888-005056bcde1f",
     "Talnagogn ur fjarlagafrumvarpi 2025 (covers 2023-2027)", ""),
    ("2026.csv",
     "https://www.stjornarradid.is/library/02-Rit--skyrslur-og-skrar/Talnag%c3%b6gn%20%c3%bar%20fj%c3%a1rlagafrumvarpi%20-%20003.csv",
     "Talnagogn ur fjarlagafrumvarpi 2026 (covers 2024-2028)", "UTF-8 BOM ';'-delimited text"),
    ("2027.xlsx",
     "https://www.stjornarradid.is/library/?itemid=cfa1b9d9-e504-4b7e-a73d-8c48a7c95004",
     "Talnagogn ur fjarlagafrumvarpi 2027 (covers 2025-2029)", ""),
]


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    for filename, url, title, note in SOURCES:
        dest = os.path.join(RAW_DIR, filename)
        print(f"Fetching {title} -> {filename}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(dest, "wb") as out:
            out.write(resp.read())
    print("Done. Now run etl.py")


if __name__ == "__main__":
    main()
