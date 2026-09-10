# Fjárlög dataset reference

Source: [stjornarradid.is](https://www.stjornarradid.is/verkefni/opinber-fjarmal/fjarlog/)
(Ministry of Finance and Economics), the "Frumvarp til fjárlaga" / "Fjárlög"
documentation published for each fiscal year 2018-2027. Each year's budget
bill also republishes 1-2 prior years' actuals/enacted figures and 2 forward
years of medium-term plan (fjármálaáætlun) projections, which is how this
dataset reaches back to 2018 and forward to 2029.

## Units

All amounts are in **million Icelandic krónur (m.kr.)**, nominal (not
inflation-adjusted), as published in the source documents. Always state the
unit when reporting a figure — these numbers are large (total state
expenditure runs ~800 billion kr. in 2018 to ~1.8 trillion kr. by 2029) and
"m.kr." vs. "kr." vs. "ISK" is an easy way to be off by a factor of a million.

## Classification

Every expenditure line is classified by:
- **málefnasvið** — top-level policy area (~35, e.g. "08 Sjúkrahúsþjónusta").
  `query.py list-malefnasvid`
- **málaflokkur** — policy sub-area (~150, e.g. "08.10 Sjúkrahúsþjónusta").
  `query.py list-malaflokkar --malefnasvid 08`
- **ráðuneyti** — the ministry it currently sits under (renamed/reorganized
  several times across 2018-2027). `query.py list-raduneyti`
- **liður** — the specific budget line, usually one agency or program (e.g.
  "07-275 Húsnæðisbætur"). Find codes with `query.py search-line-items --search <name>`.
- **viðfang** — a sub-item within a liður.

## Stages

Every figure also carries a **stage**, and get-expenditure/compare-years will
return one row per (year, stage) combination unless you pin a stage with
`--stage`:

- **Frumvarp** — the bill as introduced to Alþingi
- **Fjárlög** — the law as enacted by Alþingi
- **Ríkisreikningur** — final audited actual outturn (published ~1-2 years later)
- **Áætlun** — medium-term plan (fjármálaáætlun) projection for a future year

Comparing stages for the same year (`compare-stages`) shows how far a
proposal moved before enactment, or how actual spending differed from what
was budgeted. `compare-years`'s default behavior auto-picks the most
authoritative known stage per year (Ríkisreikningur > Fjárlög > Frumvarp >
Áætlun) — this is almost always what you want for a "how did X change over
time" question. Pin `--stage Frumvarp` explicitly only for questions
specifically about what successive *bills* proposed.

## `tegund` (which figure)

Each line has several possible measures (the `--tegund` flag, default
`Heildarútgjöld`):

| tegund | meaning |
|---|---|
| `Heildarútgjöld` | total gross expenditure for the line (the usual "how much was spent" figure) |
| `Gjöld` | gross expenditure (near-synonym of Heildarútgjöld in most years) |
| `Rekstrarframlög` | operating grants |
| `Rekstrartilfærslur` | operating transfers |
| `Fjárfestingarframlög` | capital grants |
| `Fjármagnstilfærslur` | capital transfers |
| `Rekstrartekjur` / `Tekjur` | the line's own small self-generated revenue — **not** total state tax revenue, see limitation below |
| `Fjárhæð` / `Greiðsla` | net / cash-basis figure, only present in some years |

## Known limitations — read before answering revenue/balance questions

- **No total tax revenue for 2021+.** This dataset does NOT include total
  state tax revenue (skatttekjur — income tax, VAT, etc.) for 2021 onward;
  only each line's own small self-generated revenue (`Rekstrartekjur`/`Tekjur`,
  which nets against its own expenditure) is available at that granularity.
  Don't sum `Tekjur` across the whole dataset for 2021+ and call it "total
  government revenue" — it will be off by roughly a factor of 20.
- **Tax-code-level revenue is in the dataset only for 2018-2020 — but it
  exists in the source for every year.** `revenue-detail` covers 2018-2020
  because the "Fjárlagasundurliðun tekna" spreadsheet stopped being
  published after 2020. This is a gap in this dataset, NOT a gap in the
  public record. Every budget bill and enacted budget 2018-2027 contains
  **Sundurliðun 1 — Tekjur ríkissjóðs (A1-hluta)**, a line-by-line table of
  every tax code (Virðisaukaskattur, Kílómetragjald, Olíugjald,
  Kolefnisgjald, Bifreiðagjald, Vörugjald af ökutækjum ...) on both
  rekstrargrunnur and greiðslugrunnur. For 2021+ go and fetch it — see
  "Retrieving revenue by tax code" below. Never tell the user a tax revenue
  figure is unavailable.
- **2018-2020 stage labeling is inferred, not confirmed.** Those three years'
  detailed line-item breakdowns predate the "Talnagögn" format that carries
  an explicit stage per row in the source file. Their stage (Frumvarp/Fjárlög)
  was inferred from where the source file was linked in that year's document
  list on stjornarradid.is, not confirmed in the file itself. Mention this if
  precision about bill-vs-law for exactly those three years matters to the
  question.
- **Codes get reused across reorganizations.** Ministry and málefnasvið codes
  have been renamed/restructured multiple times 2018-2027 (e.g. ráðuneyti
  code "02" was "Mennta- og menningarmálaráðuneyti" then became "Mennta- og
  barnamálaráðuneyti"). `list_raduneyti`/`list_malefnasvid` show
  first_year/last_year and the *most recent* name for each code — if a
  question is about an old name specifically, note that the code's current
  catalog entry may show a newer name.
- Revenue codes change with tax reform. "Kílómetragjald" is 114.5.1.6
  (the old heavy-vehicle levy) through 2024 but 114.5.1.8 "Kílómetragjald
  vegna notkunar bifreiða" from the 2024 reform onward, and both can appear
  in the same year. Bensín- and olíugjald lines disappear entirely from
  2026 because the levies were abolished — that is a real zero, not a
  missing value, and must not be plotted as a gap.
  Note also that `revenue_detail`'s `code` column is not formatted
  consistently across years: 2018 and 2020 use dotted codes ("114.5.1.6")
  but 2019 uses a padded flat form ("I  114050106"), so match on `heiti`
  rather than `code` when querying across those years.
- **No sub-national or off-budget data.** This covers A-hluti ríkissjóðs
  (the primary central-government budget) only — no municipalities, no
  state-owned enterprises' own budgets, no B/C-hluti entities.

## Retrieving revenue by tax code (2021+)

**Do not ask the PDF-fetching tool to read the table for you.** These bills
are ~8MB and the fetch tool hands the raw stream to a small model, which
reports mojibake even for documents that extract perfectly. Download the
file and extract the text locally instead:

1. `list-documents --year <Y>` to get the frumvarp/fjárlög PDF title.
2. Web-search that title to get the real URL. The URLs stored in
   `documents` are `library/?itemid=...` redirect links intended for
   citation, not direct file paths; the search result gives the actual
   `.../Fjarlagafrumvarp...pdf` under
   `stjornarradid.is/library/03-Verkefni/Efnahagsmal-og-opinber-fjarmal/`.
3. Download it (`curl -sSL -o <f>.pdf <url>`) and extract with layout
   preserved: `pdftotext -layout <f>.pdf <f>.txt`. `pdftotext` may not be
   installed — `apt-get update && apt-get install -y poppler-utils`. Do not
   reach for `pypdf` in this image; its `cryptography` dependency is broken.
4. `grep -n "Sundurliðun 1" <f>.txt` to find the table, then read forward.
   Codes are in column 1, heiti next, then two amount columns —
   rekstrargrunnur and greiðslugrunnur, in m.kr.
5. Say which stage the figure is from. A frumvarp figure is a forecast and
   the enacted fjárlög can differ.

Verified example (2026 frumvarp): `114.1.1 Virðisaukaskattur 465.600,0 /
460.800,0`, `114.5.1.8 Kílómetragjald vegna notkunar bifreiða 37.056,5`,
`114.2.2.4 Kolefnisgjald 14.530,0`.

Known snags:
- **The 2025 frumvarp PDF is genuinely unreadable** for Sundurliðun 1 —
  broken font encoding, and `pdftotext` cannot recover it either (the
  surrounding prose extracts fine, only the table pages are scrambled).
  Use the enacted fjárlög or the althingi.is þingskjal for 2025.
- A mojibake report from the *fetch tool* proves nothing about the
  document; confirm with `pdftotext` before believing a year is unreadable.
- The greinargerð near the end of each bill carries a summary table
  comparing the last three years per tax type — useful as a cross-check,
  and it shows abolished levies explicitly as 0.
- adverts.stjornartidindi.is blocks automated fetches, but its content does
  surface in search snippets.

## CLI quick reference

All commands print JSON to stdout. Run from the skill directory, or with an
absolute path to `scripts/query.py`.

```
query.py list-years
query.py list-malefnasvid [--year Y] [--search TEXT]
query.py list-malaflokkar [--malefnasvid CODE] [--search TEXT]
query.py list-raduneyti [--year Y] [--search TEXT]
query.py search-line-items --search TEXT [--raduneyti CODE] [--malefnasvid CODE] [--limit N]
query.py get-expenditure [--malefnasvid C] [--malaflokkur C] [--raduneyti C] [--lidur C] [--vidfang C]
                         [--search TEXT] [--year Y [Y ...]] [--stage STAGE] [--tegund T]
query.py compare-years [same filters as above] [--years Y [Y ...]] [--stage STAGE] [--tegund T]
query.py compare-stages [same filters as above] --year Y [--tegund T]
query.py top-movers --year-from Y --year-to Y --group-by {malefnasvid,raduneyti,malaflokkur}
                     [--tegund T] [--stage STAGE] [--direction {increase,decrease,both}] [--limit N]
query.py revenue-detail --year Y [--search TEXT] [--yfirflokkur CODE]
query.py list-documents [--year Y] [--kind KIND]
query.py sql "SELECT ..."   # read-only escape hatch, single SELECT statement only
```

`sql` queries against the database directly. Useful tables/views:
- `budget_lines` — raw line items (codes only, no names)
- `budget_lines_v` — same, joined with all catalog names (use this for
  anything involving `--search`/name filtering)
- `revenue_detail`, `documents`, `malefnasvid_catalog`, `malaflokkur_catalog`,
  `raduneyti_catalog`, `lidur_catalog`, `vidfang_catalog`
