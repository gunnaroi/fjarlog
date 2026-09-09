import { queryAll, queryOne } from "./db.js";

export const STAGE_PRIORITY = ["Ríkisreikningur", "Fjárlög", "Frumvarp", "Áætlun"];

export function bestStage(available: string[]): string | null {
  for (const s of STAGE_PRIORITY) {
    if (available.includes(s)) return s;
  }
  return available[0] ?? null;
}

export interface LineFilter {
  malefnasvid_code?: string;
  malaflokkur_code?: string;
  raduneyti_code?: string;
  lidur_code?: string;
  vidfang_code?: string;
  name_contains?: string;
}

function buildWhere(filter: LineFilter, extra: Record<string, unknown> = {}) {
  const clauses: string[] = [];
  const params: Record<string, unknown> = { ...extra };
  if (filter.malefnasvid_code) {
    clauses.push("malefnasvid_code = $malefnasvid_code");
    params.$malefnasvid_code = filter.malefnasvid_code;
  }
  if (filter.malaflokkur_code) {
    clauses.push("malaflokkur_code = $malaflokkur_code");
    params.$malaflokkur_code = filter.malaflokkur_code;
  }
  if (filter.raduneyti_code) {
    clauses.push("raduneyti_code = $raduneyti_code");
    params.$raduneyti_code = filter.raduneyti_code;
  }
  if (filter.lidur_code) {
    clauses.push("lidur_code = $lidur_code");
    params.$lidur_code = filter.lidur_code;
  }
  if (filter.vidfang_code) {
    clauses.push("vidfang_code = $vidfang_code");
    params.$vidfang_code = filter.vidfang_code;
  }
  if (filter.name_contains) {
    clauses.push(
      "(malefnasvid_nafn LIKE $name OR malaflokkur_nafn LIKE $name OR raduneyti_nafn LIKE $name OR lidur_nafn LIKE $name OR vidfang_nafn LIKE $name)"
    );
    params.$name = `%${filter.name_contains}%`;
  }
  return { where: clauses.length ? "WHERE " + clauses.join(" AND ") : "", params };
}

// ---------------------------------------------------------------------------

export function listYears() {
  const rows = queryAll<{ target_year: number; stage: string; n: number }>(
    `SELECT target_year, stage, COUNT(*) as n FROM budget_lines GROUP BY target_year, stage ORDER BY target_year`
  );
  const docs = queryAll<{ year: number; title: string; kind: string }>(
    `SELECT year, title, kind FROM documents ORDER BY year`
  );
  const byYear = new Map<number, { year: number; stages: string[]; documents: { title: string; kind: string }[] }>();
  for (const r of rows) {
    if (!byYear.has(r.target_year)) byYear.set(r.target_year, { year: r.target_year, stages: [], documents: [] });
    byYear.get(r.target_year)!.stages.push(r.stage);
  }
  for (const d of docs) {
    if (!byYear.has(d.year)) byYear.set(d.year, { year: d.year, stages: [], documents: [] });
    byYear.get(d.year)!.documents.push({ title: d.title, kind: d.kind });
  }
  return [...byYear.values()].sort((a, b) => a.year - b.year);
}

export function listMalefnasvid(args: { year?: number; name_contains?: string }) {
  const clauses: string[] = [];
  const params: Record<string, unknown> = {};
  if (args.year !== undefined) {
    clauses.push("first_year <= $year AND last_year >= $year");
    params.$year = args.year;
  }
  if (args.name_contains) {
    clauses.push("nafn LIKE $name");
    params.$name = `%${args.name_contains}%`;
  }
  const where = clauses.length ? "WHERE " + clauses.join(" AND ") : "";
  return queryAll(`SELECT code, nafn, first_year, last_year FROM malefnasvid_catalog ${where} ORDER BY code`, params);
}

export function listMalaflokkar(args: { malefnasvid_code?: string; name_contains?: string }) {
  const clauses: string[] = [];
  const params: Record<string, unknown> = {};
  if (args.malefnasvid_code) {
    clauses.push("code LIKE $prefix");
    params.$prefix = `${args.malefnasvid_code}.%`;
  }
  if (args.name_contains) {
    clauses.push("nafn LIKE $name");
    params.$name = `%${args.name_contains}%`;
  }
  const where = clauses.length ? "WHERE " + clauses.join(" AND ") : "";
  return queryAll(`SELECT code, nafn, first_year, last_year FROM malaflokkur_catalog ${where} ORDER BY code`, params);
}

export function listRaduneyti(args: { year?: number; name_contains?: string }) {
  const clauses: string[] = [];
  const params: Record<string, unknown> = {};
  if (args.year !== undefined) {
    clauses.push("first_year <= $year AND last_year >= $year");
    params.$year = args.year;
  }
  if (args.name_contains) {
    clauses.push("nafn LIKE $name");
    params.$name = `%${args.name_contains}%`;
  }
  const where = clauses.length ? "WHERE " + clauses.join(" AND ") : "";
  return queryAll(`SELECT code, nafn, first_year, last_year FROM raduneyti_catalog ${where} ORDER BY code`, params);
}

export function searchLineItems(args: { name_contains: string; raduneyti_code?: string; malefnasvid_code?: string; limit?: number }) {
  const clauses: string[] = ["(lidur_nafn LIKE $name OR vidfang_nafn LIKE $name)"];
  const params: Record<string, unknown> = { $name: `%${args.name_contains}%`, $limit: args.limit ?? 50 };
  if (args.raduneyti_code) {
    clauses.push("raduneyti_code = $raduneyti_code");
    params.$raduneyti_code = args.raduneyti_code;
  }
  if (args.malefnasvid_code) {
    clauses.push("malefnasvid_code = $malefnasvid_code");
    params.$malefnasvid_code = args.malefnasvid_code;
  }
  const where = "WHERE " + clauses.join(" AND ");
  return queryAll(
    `SELECT DISTINCT malefnasvid_code, malefnasvid_nafn, malaflokkur_code, malaflokkur_nafn,
            raduneyti_code, raduneyti_nafn, lidur_code, lidur_nafn, vidfang_code, vidfang_nafn
     FROM budget_lines_v
     ${where}
     LIMIT $limit`,
    params
  );
}

export interface ExpenditureArgs extends LineFilter {
  year?: number | number[];
  stage?: string;
  tegund?: string;
}

export function getExpenditure(args: ExpenditureArgs) {
  const tegund = args.tegund ?? "Heildarútgjöld";
  const extra: Record<string, unknown> = { $tegund: tegund };
  const { where: baseWhere, params } = buildWhere(args, extra);
  const clauses: string[] = [baseWhere.replace(/^WHERE /, "")].filter(Boolean);
  clauses.push("tegund = $tegund");
  if (args.stage) {
    clauses.push("stage = $stage");
    params.$stage = args.stage;
  }
  if (args.year !== undefined) {
    if (Array.isArray(args.year)) {
      const placeholders = args.year.map((y, i) => `$year${i}`);
      placeholders.forEach((p, i) => (params[p] = (args.year as number[])[i]));
      clauses.push(`target_year IN (${placeholders.join(",")})`);
    } else {
      clauses.push("target_year = $year");
      params.$year = args.year;
    }
  }
  const where = "WHERE " + clauses.join(" AND ");
  const rows = queryAll<{ target_year: number; stage: string; total: number; n_lines: number }>(
    `SELECT target_year, stage, ROUND(SUM(upphaed), 1) as total, COUNT(*) as n_lines
     FROM budget_lines_v
     ${where}
     GROUP BY target_year, stage
     ORDER BY target_year, stage`,
    params
  );
  return { tegund, unit: "m.kr.", rows };
}

export interface CompareYearsArgs extends LineFilter {
  years?: number[];
  tegund?: string;
  stage?: string;
}

export function compareYears(args: CompareYearsArgs) {
  const tegund = args.tegund ?? "Heildarútgjöld";
  const { where: baseWhere, params } = buildWhere(args, { $tegund: tegund });
  const clauses = [baseWhere.replace(/^WHERE /, ""), "tegund = $tegund"].filter(Boolean);
  if (args.years && args.years.length) {
    const placeholders = args.years.map((_, i) => `$year${i}`);
    args.years.forEach((y, i) => (params[`$year${i}`] = y));
    clauses.push(`target_year IN (${placeholders.join(",")})`);
  }
  if (args.stage) {
    clauses.push("stage = $stage");
    params.$stage = args.stage;
  }
  const where = "WHERE " + clauses.join(" AND ");
  const rows = queryAll<{ target_year: number; stage: string; total: number }>(
    `SELECT target_year, stage, SUM(upphaed) as total
     FROM budget_lines_v ${where}
     GROUP BY target_year, stage
     ORDER BY target_year`,
    params
  );
  const byYear = new Map<number, { stage: string; total: number }[]>();
  for (const r of rows) {
    if (!byYear.has(r.target_year)) byYear.set(r.target_year, []);
    byYear.get(r.target_year)!.push({ stage: r.stage, total: r.total });
  }
  const series = [...byYear.keys()].sort((a, b) => a - b).map((year) => {
    const options = byYear.get(year)!;
    const stage = args.stage ?? bestStage(options.map((o) => o.stage));
    const match = options.find((o) => o.stage === stage);
    return { year, stage, total: match ? Math.round(match.total * 10) / 10 : null };
  });
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1].total;
    const cur = series[i].total;
    (series[i] as any).change = prev !== null && cur !== null ? Math.round((cur - prev) * 10) / 10 : null;
    (series[i] as any).pct_change = prev ? Math.round(((cur! - prev) / Math.abs(prev)) * 1000) / 10 : null;
  }
  return { tegund, unit: "m.kr.", note: "stage is auto-picked per year (Ríkisreikningur > Fjárlög > Frumvarp > Áætlun) unless `stage` was given explicitly", series };
}

export interface CompareStagesArgs extends LineFilter {
  year: number;
  tegund?: string;
}

export function compareStages(args: CompareStagesArgs) {
  const tegund = args.tegund ?? "Heildarútgjöld";
  const { where: baseWhere, params } = buildWhere(args, { $tegund: tegund, $year: args.year });
  const clauses = [baseWhere.replace(/^WHERE /, ""), "tegund = $tegund", "target_year = $year"].filter(Boolean);
  const where = "WHERE " + clauses.join(" AND ");
  const rows = queryAll<{ stage: string; total: number }>(
    `SELECT stage, ROUND(SUM(upphaed), 1) as total FROM budget_lines_v ${where} GROUP BY stage`,
    params
  );
  const byStage = new Map(rows.map((r) => [r.stage, r.total]));
  return {
    year: args.year,
    tegund,
    unit: "m.kr.",
    frumvarp: byStage.get("Frumvarp") ?? null,
    fjarlog: byStage.get("Fjárlög") ?? null,
    rikisreikningur: byStage.get("Ríkisreikningur") ?? null,
    aaetlun: byStage.get("Áætlun") ?? null,
  };
}

export interface TopMoversArgs {
  year_from: number;
  year_to: number;
  group_by: "malefnasvid" | "raduneyti" | "malaflokkur";
  tegund?: string;
  stage?: string;
  limit?: number;
  direction?: "increase" | "decrease" | "both";
}

export function topMovers(args: TopMoversArgs) {
  const tegund = args.tegund ?? "Heildarútgjöld";
  const codeCol = `${args.group_by}_code`;
  const params: Record<string, unknown> = {
    $tegund: tegund,
    $year_from: args.year_from,
    $year_to: args.year_to,
  };
  let stageClause = "";
  if (args.stage) {
    stageClause = "AND stage = $stage";
    params.$stage = args.stage;
  }
  const rows = queryAll<{ target_year: number; stage: string; code: string; total: number }>(
    `SELECT target_year, stage, ${codeCol} as code, SUM(upphaed) as total
     FROM budget_lines
     WHERE tegund = $tegund AND target_year IN ($year_from, $year_to) ${stageClause} AND ${codeCol} IS NOT NULL
     GROUP BY target_year, stage, ${codeCol}`,
    params
  );
  // code -> year -> stage -> total, then pick the best available stage per year.
  const nested = new Map<string, Map<number, Map<string, number>>>();
  for (const r of rows) {
    if (!nested.has(r.code)) nested.set(r.code, new Map());
    const yearMap = nested.get(r.code)!;
    if (!yearMap.has(r.target_year)) yearMap.set(r.target_year, new Map());
    yearMap.get(r.target_year)!.set(r.stage, r.total);
  }
  const catalogTable = args.group_by === "malefnasvid" ? "malefnasvid_catalog" : args.group_by === "raduneyti" ? "raduneyti_catalog" : "malaflokkur_catalog";
  const names = new Map(
    queryAll<{ code: string; nafn: string }>(`SELECT code, nafn FROM ${catalogTable}`).map((r) => [r.code, r.nafn])
  );
  const results: { code: string; name: string | undefined; from: number | null; to: number | null; change: number | null; pct_change: number | null }[] = [];
  for (const [code, yearMap] of nested) {
    const fromStages = [...(yearMap.get(args.year_from)?.keys() ?? [])];
    const toStages = [...(yearMap.get(args.year_to)?.keys() ?? [])];
    const fromStage = args.stage ?? bestStage(fromStages);
    const toStage = args.stage ?? bestStage(toStages);
    const from = fromStage ? yearMap.get(args.year_from)?.get(fromStage) ?? null : null;
    const to = toStage ? yearMap.get(args.year_to)?.get(toStage) ?? null : null;
    const change = from !== null && to !== null ? Math.round((to - from) * 10) / 10 : null;
    const pct_change = from ? Math.round(((to! - from) / Math.abs(from)) * 1000) / 10 : null;
    results.push({ code, name: names.get(code), from, to, change, pct_change });
  }
  let filtered = results.filter((r) => r.change !== null);
  if (args.direction === "increase") filtered = filtered.filter((r) => r.change! > 0);
  if (args.direction === "decrease") filtered = filtered.filter((r) => r.change! < 0);
  filtered.sort((a, b) => Math.abs(b.change!) - Math.abs(a.change!));
  return {
    tegund,
    unit: "m.kr.",
    group_by: args.group_by,
    year_from: args.year_from,
    year_to: args.year_to,
    top: filtered.slice(0, args.limit ?? 10),
  };
}

export function getRevenueDetail(args: { year: number; name_contains?: string; yfirflokkur_code?: string }) {
  if (args.year < 2018 || args.year > 2020) {
    return {
      error:
        "Tax-code-level revenue detail is only available for 2018-2020 in this dataset. " +
        "For 2021-2027, use get_expenditure with tegund='Rekstrartekjur' for agency self-generated revenue " +
        "(this dataset does not include a full tax-revenue breakdown for those years) or consult list_documents " +
        "for the original 'Tafla 3: Skipting tekna' PDF/table.",
    };
  }
  const clauses = ["target_year = $year"];
  const params: Record<string, unknown> = { $year: args.year };
  if (args.name_contains) {
    clauses.push("heiti LIKE $name");
    params.$name = `%${args.name_contains}%`;
  }
  if (args.yfirflokkur_code) {
    clauses.push("yfirflokkur_code = $yf");
    params.$yf = args.yfirflokkur_code;
  }
  const where = "WHERE " + clauses.join(" AND ");
  const rows = queryAll(
    `SELECT code, heiti, rekstrargrunnur, greidslugrunnur, yfirflokkur_code, yfirflokkur_heiti
     FROM revenue_detail ${where} ORDER BY yfirflokkur_code, code`,
    params
  );
  return { year: args.year, unit: "m.kr.", rows };
}

export function listDocuments(args: { year?: number; kind?: string }) {
  const clauses: string[] = [];
  const params: Record<string, unknown> = {};
  if (args.year !== undefined) {
    clauses.push("year = $year");
    params.$year = args.year;
  }
  if (args.kind) {
    clauses.push("kind = $kind");
    params.$kind = args.kind;
  }
  const where = clauses.length ? "WHERE " + clauses.join(" AND ") : "";
  return queryAll(`SELECT year, title, url, kind, note FROM documents ${where} ORDER BY year, kind`, params);
}
