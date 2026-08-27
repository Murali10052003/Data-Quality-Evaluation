import axios from "axios";

const api = axios.create({ baseURL: "/api" });

// ── Discovery ──────────────────────────────────────────────────────────────────
export const getSchemas = () =>
  api.get<string[]>("/schemas").then((r) => r.data);

export const getTables = (schema: string) =>
  api.get<string[]>("/tables", { params: { schema } }).then((r) => r.data);

export const getColumns = (schema: string, table: string) =>
  api
    .get<{ column_name: string; data_type: string }[]>("/columns", {
      params: { schema, table },
    })
    .then((r) => r.data);

// ── Rules ──────────────────────────────────────────────────────────────────────
export const getRules = (schema = "", table = "", active_only = false) =>
  api
    .get("/rules", { params: { schema, table, active_only } })
    .then((r) => r.data);

export const createRule = (body: object) =>
  api.post("/rules", body).then((r) => r.data);

export const patchRule = (id: number, is_active: boolean) =>
  api.patch(`/rules/${id}`, { is_active }).then((r) => r.data);

export const deleteRule = (id: number) =>
  api.delete(`/rules/${id}`).then((r) => r.data);

export const validateLambda = (func_str: string) =>
  api
    .post<{ valid: boolean; error: string | null }>("/validate-lambda", {
      func_str,
    })
    .then((r) => r.data);

// ── Pipeline ───────────────────────────────────────────────────────────────────
export const runPipeline = (
  schema_name?: string | null,
  table_name?: string | null
) =>
  api
    .post<{ run_id: string }>("/run", { schema_name, table_name })
    .then((r) => r.data);

export const getRunStatus = (run_id: string) =>
  api
    .get<{
      status: string;
      log_tail: string[];
      returncode: number | null;
    }>(`/run/${run_id}/status`)
    .then((r) => r.data);

// ── Results ────────────────────────────────────────────────────────────────────
export const getResults = (params: Record<string, unknown>) =>
  api.get("/results", { params }).then((r) => r.data);

export const getSummary = (params: Record<string, string> = {}) =>
  api.get("/results/summary", { params }).then((r) => r.data);

export const getTrend = (params: Record<string, string> = {}) =>
  api.get<{ ts: string; Success: number; Failed: number; Error: number }[]>(
    "/results/trend",
    { params }
  ).then((r) => r.data);

export const listRuns = () => api.get("/runs").then((r) => r.data);

// ── Failed rows ────────────────────────────────────────────────────────────────
export const getFailedRows = (params: Record<string, unknown>) =>
  api.get("/failed-rows", { params }).then((r) => r.data);

export const exportUrl = (run_id: string, table: string, method = "") =>
  `/api/failed-rows/export?run_id=${encodeURIComponent(
    run_id
  )}&table=${encodeURIComponent(table)}&method=${encodeURIComponent(method)}`;

export const downloadJsonlUrl = (run_id: string, table: string) =>
  `/api/failed-rows/download-jsonl?run_id=${encodeURIComponent(
    run_id
  )}&table=${encodeURIComponent(table)}`;

export const listFailedLogRuns = () =>
  api.get("/failed-logs/runs").then((r) => r.data);

export const loadFailedLogsToDb = (run_id: string, table = "") =>
  api
    .post("/failed-logs/load-to-db", null, { params: { run_id, table } })
    .then((r) => r.data);
