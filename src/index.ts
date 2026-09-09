#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as tools from "./tools.js";

const server = new McpServer({
  name: "fjarlog-mcp",
  version: "1.0.0",
});

function text(data: unknown) {
  return { content: [{ type: "text" as const, text: JSON.stringify(data, null, 2) }] };
}

const lineFilterShape = {
  malefnasvid_code: z.string().optional().describe("Málefnasvið code, e.g. '08' (Sjúkrahúsþjónusta's parent area) — see list_malefnasvid"),
  malaflokkur_code: z.string().optional().describe("Málaflokkur code, e.g. '08.20' — see list_malaflokkar"),
  raduneyti_code: z.string().optional().describe("Ministry code, e.g. '09' (Fjármála- og efnahagsráðuneyti) — see list_raduneyti"),
  lidur_code: z.string().optional().describe("Budget line/agency code, e.g. '07-275' — see search_line_items"),
  vidfang_code: z.string().optional().describe("Sub-item code within a lidur, e.g. '110'"),
  name_contains: z.string().optional().describe("Case-sensitive substring to match against any of the málefnasvið/málaflokkur/ráðuneyti/liður/viðfang names"),
};

server.registerTool(
  "list_years",
  {
    title: "List years covered",
    description:
      "Lists every fiscal year covered by this database (2018-2029: the 2018-2027 budget bills also carry 1-2 years of prior actuals and 2 years of forward plan). " +
      "For each year, shows which stages are available (Frumvarp = bill as introduced, Fjárlög = enacted law, Ríkisreikningur = final audited actuals, Áætlun = medium-term plan projection) and lists the source documents for that year.",
    inputSchema: {},
  },
  async () => text(tools.listYears())
);

server.registerTool(
  "list_malefnasvid",
  {
    title: "List málefnasvið (policy areas)",
    description:
      "Lists the ~35 top-level 'málefnasvið' (policy areas) used to classify all Icelandic state expenditure since the 2015 Public Finances Act reform (e.g. '08 Sjúkrahúsþjónusta', '22 Almanna- og réttaröryggi'). " +
      "Use this to discover codes for get_expenditure/compare_years. Optionally filter to areas active in a given year, or by name substring.",
    inputSchema: {
      year: z.number().int().optional().describe("Only include málefnasvið active in this year"),
      name_contains: z.string().optional().describe("Substring to search for in the Icelandic name"),
    },
  },
  async (args) => text(tools.listMalefnasvid(args))
);

server.registerTool(
  "list_malaflokkar",
  {
    title: "List málaflokkar (policy sub-areas)",
    description:
      "Lists 'málaflokkar' (policy sub-areas), the second level of the budget classification below málefnasvið (e.g. málefnasvið '08 Sjúkrahúsþjónusta' contains málaflokkur '08.10 Sjúkrahúsþjónusta'). " +
      "Filter by malefnasvid_code to see only its children, or search by name.",
    inputSchema: {
      malefnasvid_code: z.string().optional().describe("Parent málefnasvið code, e.g. '08'"),
      name_contains: z.string().optional(),
    },
  },
  async (args) => text(tools.listMalaflokkar(args))
);

server.registerTool(
  "list_raduneyti",
  {
    title: "List ministries (ráðuneyti)",
    description:
      "Lists government ministries with the years each code was in use. Ministries have been renamed and reorganized several times across 2018-2027 " +
      "(e.g. code '02' was 'Mennta- og menningarmálaráðuneyti' then became 'Mennta- og barnamálaráðuneyti') — this table's first_year/last_year and name reflect the most recent name seen for each code.",
    inputSchema: {
      year: z.number().int().optional().describe("Only include ministries active in this year"),
      name_contains: z.string().optional(),
    },
  },
  async (args) => text(tools.listRaduneyti(args))
);

server.registerTool(
  "search_line_items",
  {
    title: "Search budget line items (agencies/programs)",
    description:
      "Full-text search over 'liður' (budget line / agency, e.g. '07-275 Húsnæðisbætur') and 'viðfang' (sub-item, e.g. '110 Húsnæðisbætur') names. " +
      "Use this to find the exact codes for a specific agency, institution, or program before calling get_expenditure/compare_years with lidur_code or vidfang_code.",
    inputSchema: {
      name_contains: z.string().describe("Substring to search for, e.g. 'Landspítali' or 'Vegagerðin'"),
      raduneyti_code: z.string().optional(),
      malefnasvid_code: z.string().optional(),
      limit: z.number().int().optional().default(50),
    },
  },
  async (args) => text(tools.searchLineItems(args))
);

const tegundDescription =
  "Which figure to read: 'Heildarútgjöld' (total gross expenditure for the line, default), 'Gjöld', " +
  "'Rekstrarframlög' (operating grants), 'Rekstrartilfærslur' (operating transfers), 'Fjárfestingarframlög' " +
  "(capital grants), 'Fjármagnstilfærslur' (capital transfers), 'Rekstrartekjur'/'Tekjur' (the line's own small " +
  "self-generated revenue, NOT total state tax revenue), 'Fjárhæð' or 'Greiðsla' (net/cash-basis, where available).";

server.registerTool(
  "get_expenditure",
  {
    title: "Look up expenditure figures",
    description:
      "The core lookup tool: returns summed spending (in m.kr., million ISK) matching the given filters, grouped by year and stage. " +
      "Combine any of malefnasvid_code/malaflokkur_code/raduneyti_code/lidur_code/vidfang_code/name_contains to scope the query; " +
      "omit all of them to get the whole-of-government total. `year` can be a single year, an array of years, or omitted for all years. " +
      "`stage` can be 'Frumvarp'|'Fjárlög'|'Ríkisreikningur'|'Áætlun'; omit it to see every stage available for the matched years. " +
      "IMPORTANT: this dataset covers the expenditure (gjöld) side of the budget by málefnasvið/ráðuneyti/liður for 2018-2029. " +
      "It does NOT include total tax revenue (skatttekjur) for 2021+ — use get_revenue_detail for 2018-2020 tax-code revenue instead.",
    inputSchema: {
      ...lineFilterShape,
      year: z.union([z.number().int(), z.array(z.number().int())]).optional(),
      stage: z.enum(["Frumvarp", "Fjárlög", "Ríkisreikningur", "Áætlun"]).optional(),
      tegund: z.string().optional().default("Heildarútgjöld").describe(tegundDescription),
    },
  },
  async (args) => text(tools.getExpenditure(args))
);

server.registerTool(
  "compare_years",
  {
    title: "Compare a figure across years",
    description:
      "Builds a year-by-year series for the given filter and computes change/percent-change between consecutive returned years. " +
      "By default picks the most authoritative stage available for each year (Ríkisreikningur > Fjárlög > Frumvarp > Áætlun) — pass `stage` to pin a single stage across all years instead " +
      "(useful e.g. to compare what successive budget bills *proposed* for the same policy area). Omit `years` to use every year in the database.",
    inputSchema: {
      ...lineFilterShape,
      years: z.array(z.number().int()).optional().describe("Years to compare; omit for all years 2018-2029"),
      stage: z.enum(["Frumvarp", "Fjárlög", "Ríkisreikningur", "Áætlun"]).optional(),
      tegund: z.string().optional().default("Heildarútgjöld").describe(tegundDescription),
    },
  },
  async (args) => text(tools.compareYears(args))
);

server.registerTool(
  "compare_stages",
  {
    title: "Compare bill vs. law vs. actual for one year",
    description:
      "For a single year and filter, shows the figure at every stage it was published at: the original budget bill (Frumvarp), " +
      "the law as enacted by Alþingi (Fjárlög), the medium-term plan's earlier projection (Áætlun), and the final audited outturn (Ríkisreikningur) once available. " +
      "Useful for questions like 'how much did defence spending change between the bill and the final law in 2023?'",
    inputSchema: {
      ...lineFilterShape,
      year: z.number().int(),
      tegund: z.string().optional().default("Heildarútgjöld").describe(tegundDescription),
    },
  },
  async (args) => text(tools.compareStages(args))
);

server.registerTool(
  "top_movers",
  {
    title: "Biggest changes between two years",
    description:
      "Ranks málefnasvið, ráðuneyti, or málaflokkar by the size of their change in spending between two years, largest absolute change first. " +
      "Good for 'what grew/shrank the most between 2020 and 2025?' type questions.",
    inputSchema: {
      year_from: z.number().int(),
      year_to: z.number().int(),
      group_by: z.enum(["malefnasvid", "raduneyti", "malaflokkur"]).default("malefnasvid"),
      tegund: z.string().optional().default("Heildarútgjöld").describe(tegundDescription),
      stage: z.enum(["Frumvarp", "Fjárlög", "Ríkisreikningur", "Áætlun"]).optional().describe("Pin a single stage for both years; omit to auto-pick the best available stage per year"),
      direction: z.enum(["increase", "decrease", "both"]).optional().default("both"),
      limit: z.number().int().optional().default(10),
    },
  },
  async (args) => text(tools.topMovers(args))
);

server.registerTool(
  "get_revenue_detail",
  {
    title: "Tax-code-level revenue detail (2018-2020 only)",
    description:
      "Returns detailed tax/revenue-code-level figures (e.g. 'Tekjuskattur einstaklinga', 'Virðisaukaskattur') on both accrual basis (rekstrargrunnur) " +
      "and cash basis (greiðslugrunnur). Only available for 2018-2020 in this dataset — later years' budget bills do not appear to publish this breakdown " +
      "in the same machine-readable form; for those years consult list_documents for the original PDF revenue tables.",
    inputSchema: {
      year: z.number().int(),
      name_contains: z.string().optional(),
      yfirflokkur_code: z.string().optional().describe("Top-level revenue category code, e.g. '111' (Skattar á tekjur og hagnað)"),
    },
  },
  async (args) => text(tools.getRevenueDetail(args))
);

server.registerTool(
  "list_documents",
  {
    title: "List source documents",
    description:
      "Lists the original stjornarradid.is source documents (budget bills, enacted laws, data files) behind this database, for citation. " +
      "Filter by year and/or kind (frumvarp_pdf, fjarlog_pdf, fylgirit_pdf, talnagogn, expenditure_breakdown, revenue_breakdown).",
    inputSchema: {
      year: z.number().int().optional(),
      kind: z.string().optional(),
    },
  },
  async (args) => text(tools.listDocuments(args))
);

server.registerResource(
  "about",
  "fjarlog://about",
  {
    title: "About this dataset",
    description: "Explains the data model, units, classification scheme, and known limitations of the fjárlög dataset.",
    mimeType: "text/markdown",
  },
  async (uri) => ({
    contents: [
      {
        uri: uri.href,
        mimeType: "text/markdown",
        text: `# Fjárlög (Icelandic state budget) dataset, 2018-2029

Source: stjornarradid.is (Ministry of Finance and Economics), the "Frumvarp til
fjárlaga" / "Fjárlög" documentation published for each fiscal year 2018-2027.
Each year's budget bill also republishes 1-2 prior years' actuals/enacted
figures and 2 forward years of medium-term plan (fjármálaáætlun) projections,
which is how this dataset reaches back to 2018 and forward to 2029.

## Units
All amounts are in **million Icelandic krónur (m.kr.)**, nominal (not
inflation-adjusted), as published in the source documents.

## Classification (2018-2029)
Every expenditure line is classified by:
- **málefnasvið** — top-level policy area (~35, e.g. "08 Sjúkrahúsþjónusta")
- **málaflokkur** — policy sub-area (~150, e.g. "08.10 Sjúkrahúsþjónusta")
- **ráðuneyti** — the ministry it currently sits under (renamed/reorganized
  several times across this period; list_raduneyti shows the years each code
  was used and its most recent name)
- **liður** — the specific budget line, usually one agency or program
  (e.g. "07-275 Húsnæðisbætur")
- **viðfang** — a sub-item within a liður

## Stages
Every figure also carries a **stage**:
- **Frumvarp** — the bill as introduced to Alþingi
- **Fjárlög** — the law as enacted by Alþingi
- **Ríkisreikningur** — final audited actual outturn (published ~1-2 years later)
- **Áætlun** — medium-term plan (fjármálaáætlun) projection for a future year

Comparing stages for the same year (see compare_stages) shows how far a
proposal moved before enactment, or how actual spending differed from what
was budgeted.

## Known limitations
- **Revenue**: this dataset does NOT include total state tax revenue
  (skatttekjur — income tax, VAT, etc.) for 2021 onward; only each line's own
  small self-generated revenue ("Rekstrartekjur"/"Tekjur", which nets against
  its own expenditure) is available at that granularity. Full tax-code-level
  revenue detail (accrual and cash basis) is only available for **2018-2020**
  via get_revenue_detail.
- **2018-2020 stage labeling**: those three years' detailed line-item
  breakdowns predate the "Talnagögn" format that carries an explicit stage
  per row. Their stage (Frumvarp/Fjárlög) was inferred from where the source
  file was linked in that year's document list, not confirmed in the file
  itself — see list_documents' notes for the specific caveat per year.
- Ministry and málefnasvið codes have been reused across reorganizations;
  always check list_raduneyti/list_malefnasvid's first_year/last_year when
  precision matters.
`,
      },
    ],
  })
);

const transport = new StdioServerTransport();
await server.connect(transport);
