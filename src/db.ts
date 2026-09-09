import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_PATH = path.join(__dirname, "..", "data", "fjarlog.db");

export const db = new DatabaseSync(DB_PATH, { readOnly: true });

export const STAGES = ["Frumvarp", "Fjárlög", "Ríkisreikningur", "Áætlun"] as const;
export type Stage = (typeof STAGES)[number];

export const TEGUNDIR = [
  "Gjöld",
  "Tekjur",
  "Fjárhæð",
  "Greiðsla",
  "Rekstrarframlög",
  "Rekstrartilfærslur",
  "Fjármagnstilfærslur",
  "Fjárfestingarframlög",
  "Heildarútgjöld",
  "Rekstrartekjur",
  "Framlag úr ríkissjóði",
  "Viðskiptahreyfingar",
] as const;

export interface BudgetRow {
  id: number;
  target_year: number;
  stage: string;
  malefnasvid_code: string | null;
  malefnasvid_nafn: string | null;
  malaflokkur_code: string | null;
  malaflokkur_nafn: string | null;
  raduneyti_code: string | null;
  raduneyti_nafn: string | null;
  lidur_code: string | null;
  lidur_nafn: string | null;
  vidfang_code: string | null;
  vidfang_nafn: string | null;
  tegund: string;
  upphaed: number;
  source_year: number;
}

export function queryAll<T = Record<string, unknown>>(sql: string, params: Record<string, unknown> = {}): T[] {
  const stmt = db.prepare(sql);
  return stmt.all(params as never) as T[];
}

export function queryOne<T = Record<string, unknown>>(sql: string, params: Record<string, unknown> = {}): T | undefined {
  const stmt = db.prepare(sql);
  return stmt.get(params as never) as T | undefined;
}
