---
name: fjarlog
description: Look up and compare Icelandic state budget (fjárlög) figures for 2018-2029 — expenditure by policy area, ministry, agency, or program, year-over-year comparisons, and bill-vs-enacted-law-vs-actual comparisons, backed by a bundled SQLite database of ~230,000 line items from stjornarradid.is. Use this whenever the user asks about Icelandic government/state spending or revenue, fjárlög, ríkisfjármál, fjárlagafrumvarp, a specific Icelandic ministry or agency (e.g. Landspítali, Vegagerðin, a ráðuneyti), or wants to compare Icelandic budget years or budget stages — even if they don't say "budget" or name this skill explicitly, e.g. "how much does Iceland spend on hospitals", "how did defence spending change under the last budget", "what got cut in the 2023 fjárlög". Do not rely on general knowledge for exact Icelandic budget figures — always query this dataset instead.
---

# Fjárlög (Icelandic state budget)

This skill answers questions about Icelandic central-government spending
using a bundled, pre-normalized SQLite database (`data/fjarlog.db`, ~27MB)
built from official budget-bill data files published on stjornarradid.is.
Query it with the bundled CLI instead of estimating or recalling figures from
memory — the whole point of this skill is exact, sourced numbers.

## Before answering: read the reference doc once per conversation

`references/schema.md` explains the classification scheme (málefnasvið /
málaflokkur / ráðuneyti / liður / viðfang), the four stages (Frumvarp /
Fjárlög / Ríkisreikningur / Áætlun) and how `compare-years` picks between
them, the `tegund` measures, and — importantly — this dataset's limitations
(no total tax revenue for 2021+, 2018-2020 stage labels are inferred, codes
get reused across ministry reorganizations). Read it before your first query
in a conversation; skip re-reading it on later turns of the same
conversation.

## How to answer a question

1. **Find the code.** If the question names a ministry, agency, or program
   (e.g. "Landspítali", "Vegagerðin"), run `search-line-items --search <name>`
   first to get its exact `lidur_code`/`malefnasvid_code` — don't guess codes.
   `list-malefnasvid`, `list-malaflokkar`, and `list-raduneyti` (all support
   `--search`) work the same way for broader policy areas or ministries.
2. **Query.** Use `get-expenditure` for a single point-in-time figure,
   `compare-years` for a trend across years, `compare-stages` for
   bill-vs-law-vs-actual in one year, or `top-movers` for "what changed the
   most" questions. All commands are in
   `scripts/query.py --help` and detailed in `references/schema.md`.
3. **Report with units and stage.** State the amount in **million ISK
   (m.kr.)**, and say which stage it's from (e.g. "as enacted in the 2023
   Fjárlög" vs. "per the original 2023 bill" vs. "final Ríkisreikningur
   actual") — these can differ meaningfully and silently picking the wrong
   one is the most common way to get this wrong. `compare-years` tells you
   which stage it auto-picked for each year in its `note`/per-year `stage`
   field; say so if it's relevant.
4. **Cite the source** for anything beyond a casual mention — run
   `list-documents --year <Y>` and link the relevant bill/law PDF or data file.

## Running the CLI

```bash
python3 <skill-dir>/scripts/query.py <subcommand> [options]
```

No dependencies — it's pure Python stdlib (`sqlite3`), opens the database
read-only, and prints JSON to stdout. Two quick examples:

```bash
# How much did Iceland spend on hospital services (málefnasvið 23) in 2020 vs 2025?
python3 scripts/query.py compare-years --malefnasvid 23 --years 2020 2025

# What changed the most between the 2020 and 2025 budgets, by policy area?
python3 scripts/query.py top-movers --year-from 2020 --year-to 2025 --group-by malefnasvid
```

If a canned subcommand can't express what's needed, use the `sql` escape
hatch (read-only, single `SELECT` only) against the tables listed at the end
of `references/schema.md` — e.g. `query.py sql "SELECT DISTINCT raduneyti_nafn FROM raduneyti_catalog"`.

## Common mistakes to avoid

- Don't sum `Tekjur`/`Rekstrartekjur` across the database and call it "total
  government revenue" for 2021+ — see the limitations section in
  `references/schema.md`, this dataset only has that for expenditure lines'
  own small self-generated revenue.
- Don't report a number without saying which year *and* which stage it's for
  — "spending on X" is ambiguous between the original bill, the enacted law,
  and the final actual outturn, and they can differ by double-digit percent.
- Don't hand-roll a code (e.g. assuming a ministry's málefnasvið number) —
  always resolve it via `search-line-items`/`list-malefnasvid`/etc. first.
