import { useEffect, useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { getResults, listRuns, downloadJsonlUrl, listFailedLogRuns, loadFailedLogsToDb } from "../api/client";

export default function ResultsViewer() {
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const [runId,   setRunId]   = useState("");
  const [table,   setTable]   = useState(searchParams.get("table") ?? "");
  const [method,  setMethod]  = useState(searchParams.get("method") ?? "");
  const [status,  setStatus]  = useState("");
  const [page,    setPage]    = useState(1);
  const PAGE_SIZE = 50;

  const { data: runs = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
  });

  // Fetch all results for current run to populate Table/Method dropdowns
  const { data: allData } = useQuery({
    queryKey: ["results-all", runId],
    queryFn: () => getResults({ run_id: runId, page: 1, page_size: 1000 }),
  });
  const allRows: Record<string, unknown>[] = allData?.rows ?? [];
  const tableOptions = [...new Set(allRows.map((r) => r.table_name as string))].filter(Boolean).sort();
  const methodOptions = [...new Set(allRows.map((r) => r.dqmethod as string))].filter(Boolean).sort();

  useEffect(() => {
    const runsList = runs as { run_id: string }[];
    if (runsList.length > 0 && !runId) {
      setRunId(runsList[0].run_id);
    }
  }, [runs, runId]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["results", runId, table, method, status, page],
    queryFn: () =>
      getResults({
        run_id: runId, table, method, status,
        page, page_size: PAGE_SIZE,
      }),
  });

  const rows: Record<string, unknown>[] = data?.rows ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  // Aggregate counts for strip
  const successCount = rows.filter((r) => r.status === "Success").length;
  const failedCount = rows.filter((r) => r.status === "Failed").length;
  const errorCount = rows.filter((r) => r.status === "Error").length;

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="font-medium mb-2" style={{ color: "var(--failed)" }}>Failed to load results</p>
          <button className="btn-secondary text-sm" onClick={() => qc.invalidateQueries({ queryKey: ["results"] })}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-[18px] w-full" style={{ animation: "fadein .4s ease" }}>
      {/* Command bar */}
      <div
        className="glass flex items-center justify-between gap-4 flex-wrap"
        style={{ padding: "0 20px", minHeight: 56 }}
      >
        <div className="text-2xl font-bold text-white">Results Viewer</div>
      </div>

      {/* Filters */}
      <div className="glass" style={{ padding: "16px 20px" }}>
        <div className="flex gap-3 flex-wrap items-center">
          <select className="input-base" value={runId} onChange={(e) => { setRunId(e.target.value); setPage(1); }}>
            <option value="">All Runs</option>
            {(runs as { run_id: string; started_at: string }[]).map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {new Date(r.started_at).toLocaleString()} — {r.run_id.slice(0, 8)}
              </option>
            ))}
          </select>
          <select className="input-base" value={table} onChange={(e) => { setTable(e.target.value); setPage(1); }}>
            <option value="">All Tables</option>
            {tableOptions.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select className="input-base" value={method} onChange={(e) => { setMethod(e.target.value); setPage(1); }}>
            <option value="">All Methods</option>
            {methodOptions.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <select className="input-base" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All Status</option>
            <option>Success</option>
            <option>Failed</option>
            <option>Error</option>
          </select>
          <button className="btn-primary" onClick={() => qc.invalidateQueries({ queryKey: ["results"] })}>Apply</button>
          <button className="btn-secondary" onClick={() => { setRunId(""); setTable(""); setMethod(""); setStatus(""); setPage(1); }}>Clear</button>
        </div>
      </div>

      {/* Stats strip */}
      <div className="glass flex gap-5 flex-wrap" style={{ padding: "14px 20px" }}>
        {[
          { label: `${total} total`, dotStyle: { background: "#94a3b8" } },
          { label: `${successCount} passed`, dotCls: "bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,.5)]" },
          { label: `${failedCount} failed`, dotCls: "bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,.5)]" },
          { label: `${errorCount} errors`, dotCls: "bg-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,.5)]" },
        ].map((s, i) => (
          <span key={i} className="flex items-center gap-1.5 text-xs font-semibold text-white">
            <span className={`w-2.5 h-2.5 rounded-full ${s.dotCls ?? ""}`} style={s.dotStyle} />
            {s.label}
          </span>
        ))}
      </div>

      {/* Results table */}
      <div className="glass overflow-hidden">
        {isLoading ? (
          <p className="p-5 text-sm animate-pulse" style={{ color: "var(--t2)" }}>Loading…</p>
        ) : (
          <>
            <table className="w-full text-[13px]" style={{ borderCollapse: "collapse" }}>
              <thead>
                <tr>
                  {["Run", "Table", "Method", "Column", "Status", "Failed"].map((h) => (
                    <th
                      key={h}
                      className="text-left p-3"
                      style={{
                        background: "rgba(255,255,255,.03)",
                        color: "var(--t2)",
                        fontSize: 11,
                        textTransform: "uppercase",
                        letterSpacing: ".06em",
                        fontWeight: 600,
                        ...(h === "Failed" ? { textAlign: "center" as const } : {}),
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const st = r.status as string;
                  const pillCls = st === "Success" ? "pill-pass" : st === "Failed" ? "pill-fail" : "pill-err";
                  const failCount = r.dqevalcount as number;
                  return (
                    <tr
                      key={i}
                      className="transition-colors"
                      style={{ borderTop: "1px solid var(--border)" }}
                    >
                      <td className="p-3 font-mono" style={{ color: "#a5b4fc" }}>
                        {(r.run_id as string)?.slice(0, 10) ?? "—"}
                      </td>
                      <td className="p-3 text-white">{r.table_name as string}</td>
                      <td className="p-3"><span className="badge-method">{r.dqmethod as string}</span></td>
                      <td className="p-3 font-mono" style={{ color: "var(--t2)" }}>{(r.col as string) || "—"}</td>
                      <td className="p-3"><span className={`pill ${pillCls}`}>{st}</span></td>
                      <td
                        className="p-3 text-center"
                        style={{
                          color: failCount ? "var(--failed)" : undefined,
                          fontWeight: failCount ? 700 : undefined,
                        }}
                      >
                        {failCount || "—"}
                        </td>
                    </tr>
                  );
                })}
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={7} className="p-5 text-center text-sm" style={{ color: "var(--t2)" }}>
                      No results match the current filters.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>

            {/* Pagination */}
            <div className="flex gap-1.5 items-center justify-end" style={{ padding: "14px 20px" }}>
              <button
                className="w-8 h-8 rounded-lg text-[13px] cursor-pointer"
                style={{ background: "rgba(255,255,255,.04)", border: "1px solid var(--border)", color: "var(--t2)" }}
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                ‹
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => i + 1).map((p) => (
                <button
                  key={p}
                  className="w-8 h-8 rounded-lg text-[13px] cursor-pointer"
                  style={
                    page === p
                      ? { background: "var(--grad)", color: "#fff", border: "none" }
                      : { background: "rgba(255,255,255,.04)", border: "1px solid var(--border)", color: "var(--t2)" }
                  }
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              ))}
              <button
                className="w-8 h-8 rounded-lg text-[13px] cursor-pointer"
                style={{ background: "rgba(255,255,255,.04)", border: "1px solid var(--border)", color: "var(--t2)" }}
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                ›
              </button>
            </div>
          </>
        )}
      </div>

      {/* Failed Logs */}
      <FailedLogsSection />
    </div>
  );
}


function FailedLogsSection() {
  const { data: logRuns = [], isLoading } = useQuery({
    queryKey: ["failed-log-runs"],
    queryFn: listFailedLogRuns,
  });

  const [selectedRun, setSelectedRun] = useState("");
  const [selectedTable, setSelectedTable] = useState("");
  const [loadResult, setLoadResult] = useState<Record<string, unknown> | null>(null);

  const runs = logRuns as { run_id: string; tables: string[] }[];
  const currentRun = runs.find((r) => r.run_id === selectedRun);
  const tables = currentRun?.tables ?? [];

  const loadMut = useMutation({
    mutationFn: () => loadFailedLogsToDb(selectedRun, selectedTable),
    onSuccess: (data) => setLoadResult(data),
  });

  return (
    <div className="glass" style={{ padding: 20 }}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[15px] font-bold text-white">Failed Row Logs</div>
          <div className="text-xs mt-0.5" style={{ color: "var(--t2)" }}>
            Download JSONL files or load failed rows into the database as analysis tables
          </div>
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm animate-pulse mt-4" style={{ color: "var(--t2)" }}>Loading…</p>
      ) : runs.length === 0 ? (
        <p className="text-sm mt-4" style={{ color: "var(--t2)" }}>No failed row logs found.</p>
      ) : (
        <div className="space-y-4 mt-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div>
              <p className="text-xs mb-1" style={{ color: "var(--t2)" }}>Run</p>
              <select
                className="input-base"
                value={selectedRun}
                onChange={(e) => { setSelectedRun(e.target.value); setSelectedTable(""); setLoadResult(null); }}
              >
                <option value="">Select run…</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id.slice(0, 8)}… ({r.tables.length} table{r.tables.length !== 1 ? "s" : ""})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <p className="text-xs mb-1" style={{ color: "var(--t2)" }}>Table</p>
              <select
                className="input-base"
                value={selectedTable}
                onChange={(e) => { setSelectedTable(e.target.value); setLoadResult(null); }}
                disabled={!selectedRun}
              >
                <option value="">All tables</option>
                {tables.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>

            {selectedRun && selectedTable && (
              <a href={downloadJsonlUrl(selectedRun, selectedTable)} className="btn-secondary text-xs">
                ↓ Download JSONL
              </a>
            )}

            {selectedRun && (
              <button
                className="btn-primary text-xs"
                disabled={loadMut.isPending}
                onClick={() => loadMut.mutate()}
              >
                {loadMut.isPending ? "Loading…" : `⬆ Load ${selectedTable || "all tables"} into DB`}
              </button>
            )}
          </div>

          {selectedRun && tables.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {tables.map((t) => (
                <a
                  key={t}
                  href={downloadJsonlUrl(selectedRun, t)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono transition-colors"
                  style={{
                    background: "rgba(255,255,255,.04)",
                    border: "1px solid var(--border)",
                    color: "#a5b4fc",
                  }}
                >
                  ↓ {t}.jsonl
                </a>
              ))}
            </div>
          )}

          {loadResult && (
            <div
              className="rounded-[10px] p-3"
              style={{
                background: "rgba(16,185,129,.06)",
                border: "1px solid rgba(16,185,129,.3)",
              }}
            >
              <p className="text-xs font-semibold mb-2" style={{ color: "var(--success)" }}>Loaded into database:</p>
              {Object.entries((loadResult as { loaded: Record<string, unknown> }).loaded ?? {}).map(([tbl, count]) => (
                <div key={tbl} className="flex justify-between text-xs py-0.5">
                  <span className="font-mono" style={{ color: "var(--t1)" }}>{tbl}_failed_rows</span>
                  <span style={{ color: typeof count === "number" ? "var(--success)" : "var(--failed)", fontWeight: 500 }}>
                    {typeof count === "number" ? `${count.toLocaleString()} rows` : String(count)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {loadMut.isError && (
            <div
              className="rounded-[10px] p-2.5 text-xs"
              style={{
                background: "rgba(239,68,68,.08)",
                border: "1px solid rgba(239,68,68,.3)",
                color: "#fca5a5",
              }}
            >
              Failed to load logs into database. Check the backend is connected.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
