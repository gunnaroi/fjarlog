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
- **Full tax-code-level revenue** (accrual basis `rekstrargrunnur` and cash
  basis `greiðslugrunnur`, broken down by tax type like "Tekjuskattur
  einstaklinga" or "Virðisaukaskattur") is only available for **2018-2020**
  via `query.py revenue-detail --year <2018|2019|2020>`. For other years,
  point the user at `list-documents` for the original "Tafla 3: Skipting
  tekna" table/PDF instead of guessing.
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
- **No sub-national or off-budget data.** This covers A-hluti ríkissjóðs
  (the primary central-government budget) only — no municipalities, no
  state-owned enterprises' own budgets, no B/C-hluti entities.

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
