# fjarlog-mcp

An MCP (Model Context Protocol) server for the Icelandic state budget
("fjárlög"), covering fiscal years **2018-2029** (the 2018-2027 budget bills
each also republish 1-2 years of prior actuals and 2 years of forward
medium-term-plan projections). It gives an MCP client (Claude, etc.) tools to
look up expenditure by policy area/ministry/agency, compare figures across
years, and compare a bill's original proposal against the enacted law and the
final audited outturn.

Source: [stjornarradid.is](https://www.stjornarradid.is/verkefni/opinber-fjarmal/fjarlog/)
(Ministry of Finance and Economics). See `list_documents` / `data/sources.json`
for the exact source file behind every figure.

## What's in the data

- **~230,000 line items** across 2018-2029, classified by málefnasvið (policy
  area), málaflokkur (policy sub-area), ráðuneyti (ministry), liður (agency/
  budget line) and viðfang (sub-item) — the classification scheme introduced
  by the 2015 Public Finances Act.
- Each line carries a **stage**: `Frumvarp` (bill as introduced), `Fjárlög`
  (enacted law), `Ríkisreikningur` (final audited actual), or `Áætlun`
  (medium-term plan projection).
- Amounts are in **million ISK (m.kr.)**, nominal.
- Tax-code-level revenue detail (income tax, VAT, etc.) is only available for
  **2018-2020**; later years' bills don't publish that breakdown in the same
  machine-readable form, so 2021+ only has each line's small self-generated
  revenue, not total government tax revenue. See the `fjarlog://about` MCP
  resource for the full list of caveats.

## Tools

| Tool | Purpose |
|---|---|
| `list_years` | Years covered + stages + source docs per year |
| `list_malefnasvid` / `list_malaflokkar` / `list_raduneyti` | Browse the classification catalogs |
| `search_line_items` | Find an agency/program's exact code by name |
| `get_expenditure` | Core lookup: summed spending for any filter/year(s)/stage |
| `compare_years` | Year-over-year series with automatic change/% change |
| `compare_stages` | Bill vs. law vs. actual for one year |
| `top_movers` | Biggest increases/decreases between two years |
| `get_revenue_detail` | Tax-code-level revenue (2018-2020 only) |
| `list_documents` | Source document metadata, for citation |

## Setup

```bash
npm install
npm run build
```

This uses Node's built-in `node:sqlite` (no native build step, no extra
dependency) — requires **Node 22.5+**.

### Rebuilding the database from source

The processed database (`data/fjarlog.db`) is committed to the repo so the
server works out of the box. To rebuild it from the original government
files:

```bash
python3 scripts/fetch_sources.py   # downloads raw files into scripts/raw/
python3 scripts/etl.py             # writes data/fjarlog.db + data/sources.json
```

Requires Python 3 with `openpyxl` installed.

## Using with an MCP client

```json
{
  "mcpServers": {
    "fjarlog": {
      "command": "node",
      "args": ["/absolute/path/to/fjarlog/build/index.js"]
    }
  }
}
```

Or with the Claude Code CLI:

```bash
claude mcp add fjarlog -- node /absolute/path/to/fjarlog/build/index.js
```

## Example questions this can answer

- "How much did Iceland spend on hospital services (Sjúkrahúsþjónusta) in 2025?"
- "Compare unemployment-benefit spending between 2020 and 2023."
- "What changed the most between the 2023 budget bill and the enacted law?"
- "Which policy areas grew the fastest between 2020 and 2025?"
- "What was total income tax revenue in 2019, accrual vs. cash basis?"
