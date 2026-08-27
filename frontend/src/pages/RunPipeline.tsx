import { useEffect, useRef, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getSchemas, getTables, runPipeline, getRunStatus, getResults } from "../api/client";
import { useToast } from "../context/ToastContext";

interface RunStatus {
  status: string;
  log_tail: string[];
  returncode: number | null;
}

type ResultRow = {
  table_name: string;
  dqmethod: string;
  col: string;
  dqevalcount: number;
  run_timestamp: string;
  status: string;
};

interface TableStep {
  schema: string;
  table: string;
  ruleCount: number;
  status: "pending" | "running" | "done" | "error";
  resultCount?: number;
  failedCount?: number;
}

function parseProgress(lines: string[]): {
  steps: TableStep[];
  totalRules: number;
  completedSteps: number;
  currentTable: string | null;
  pipelineRunId: string | null;
  hasError: boolean;
} {
  const steps: TableStep[] = [];
  let totalRules = 0;
  let currentTable: string | null = null;
  let pipelineRunId: string | null = null;
  let hasError = false;

  for (const line of lines) {
    // Parse run_id
    const runIdMatch = line.match(/Pipeline run_id:\s*(\S+)/);
    if (runIdMatch) pipelineRunId = runIdMatch[1];

    // Parse "→ Evaluating schema.table (N rule(s))" or batch variant
    const evalMatch = line.match(/→\s*(?:\[Batch\]\s*)?Evaluating\s+(\S+)\.(\S+)\s+\((\d+)\s+rule/);
    if (evalMatch) {
      const [, schema, table, count] = evalMatch;
      const ruleCount = parseInt(count, 10);
      // Mark previous running step as done if not already
      steps.forEach((s) => { if (s.status === "running") s.status = "done"; });
      steps.push({ schema, table, ruleCount, status: "running" });
      totalRules += ruleCount;
      currentTable = `${schema}.${table}`;
    }

    // Parse "✓ schema.table → X result row(s), Y failed row(s)"
    const doneMatch = line.match(/✓\s+(\S+)\.(\S+)\s+→\s+(\d+)\s+result.*?(\d+)\s+failed/);
    if (doneMatch) {
      const [, schema, table, results, failed] = doneMatch;
      const step = steps.find((s) => s.schema === schema && s.table === table);
      if (step) {
        step.status = "done";
        step.resultCount = parseInt(results, 10);
        step.failedCount = parseInt(failed, 10);
      }
      currentTable = null;
    }

    // Parse errors
    const errorMatch = line.match(/Evaluation failed for\s+(\S+)\.(\S+)/);
    if (errorMatch) {
      const [, schema, table] = errorMatch;
      const step = steps.find((s) => s.schema === schema && s.table === table);
      if (step) step.status = "error";
      hasError = true;
      currentTable = null;
    }

    // Catch general exceptions
    if (line.match(/ERROR|Exception|Traceback|failed with an unhandled/i)) {
      hasError = true;
    }
  }

  const completedSteps = steps.filter((s) => s.status === "done" || s.status === "error").length;
  return { steps, totalRules, completedSteps, currentTable, pipelineRunId, hasError };
}

export default function RunPipeline() {
  const { toast } = useToast();
  const [schema, setSchema] = useState("");
  const [table, setTable]   = useState("");
  const [runId, setRunId]   = useState<string | null>(null);
  const [status, setStatus] = useState<RunStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  const { data: schemas = [] } = useQuery({
    queryKey: ["schemas"],
    queryFn: getSchemas,
  });

  const { data: tables = [] } = useQuery({
    queryKey: ["tables", schema],
    queryFn: () => getTables(schema || "public"),
    enabled: true,
  });

  const { data: runResults } = useQuery({
    queryKey: ["run-results", runId],
    queryFn: () => getResults({ run_id: runId, page: 1, page_size: 500 }),
    enabled: !!runId && status?.status === "complete",
  });

  useEffect(() => {
    if (!runId || !polling) return;
    const tick = async () => {
      const s = await getRunStatus(runId);
      setStatus(s);
      if (s.status !== "running") {
        setPolling(false);
        if (s.status === "complete") toast("Pipeline completed successfully");
        else if (s.status === "failed") toast("Pipeline failed", "error");
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => clearInterval(id);
  }, [runId, polling]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [status?.log_tail]);

  const handleRun = async () => {
    const resp = await runPipeline(schema || null, table || null);
    setRunId(resp.run_id);
    setStatus(null);
    setPolling(true);
    setShowLog(false);
    toast("Pipeline started", "info");
  };

  const progress = useMemo(
    () => parseProgress(status?.log_tail ?? []),
    [status?.log_tail]
  );

  const pct = progress.steps.length > 0
    ? Math.round((progress.completedSteps / progress.steps.length) * 100)
    : 0;

  const isRunning = polling || status?.status === "running";
  const isComplete = status?.status === "complete";
  const isFailed = status?.status === "failed";

  const rows: ResultRow[] = (runResults as { rows?: ResultRow[] })?.rows ?? [];
  const totalRan  = rows.length;
  const passed    = rows.filter((r) => r.status === "Success").length;
  const failedCnt = rows.filter((r) => r.status === "Failed").length;

  return (
    <div className="space-y-[22px] w-full" style={{ animation: "fadein .4s ease" }}>
      {/* Command bar */}
      <div
        className="glass flex items-center justify-between gap-4 flex-wrap"
        style={{ padding: "0 20px", minHeight: 56 }}
      >
        <div className="text-2xl font-bold text-white">Run Pipeline</div>
      </div>

      {/* Wizard */}
      <div className="max-w-[760px] mx-auto space-y-0">
        {/* Config card with top gradient bar */}
        <div className="glass relative overflow-hidden" style={{ padding: 20 }}>
          <div
            className="absolute top-0 left-0 right-0 h-1"
            style={{ background: "var(--grad)", borderRadius: "16px 16px 0 0" }}
          />

          <div className="text-[15px] font-bold text-white">Configure Pipeline Scope</div>
          <div className="text-xs mt-0.5 mb-4" style={{ color: "var(--t3)" }}>
            Select the schema and tables to evaluate in this run.
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Schema</label>
              <select
                className="input-base w-full"
                value={schema}
                onChange={(e) => { setSchema(e.target.value); setTable(""); }}
              >
                <option value="">All schemas</option>
                {schemas.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Table</label>
              <select
                className="input-base w-full"
                value={table}
                onChange={(e) => setTable(e.target.value)}
              >
                <option value="">All Tables</option>
                {tables.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
          </div>

          <div
            className="mt-4 rounded-lg text-[13px]"
            style={{
              background: "rgba(59,130,246,.06)",
              borderLeft: "3px solid var(--blue)",
              padding: "12px 14px",
              color: "var(--t2)",
            }}
          >
            ℹ️ The pipeline will execute all active rules matching the selected scope.
          </div>
        </div>

        {/* Launch button */}
        <button
          className="btn-primary w-full justify-center text-[15px] my-[18px]"
          style={{ height: 52 }}
          disabled={polling}
          onClick={handleRun}
        >
          {polling ? (
            <span>Running…</span>
          ) : (
            "▶ Launch Pipeline"
          )}
        </button>

        {/* Progress panel */}
        {runId && (
          <div className="glass" style={{ padding: 20 }}>
            {/* Header row: run ID + status */}
            <div className="flex justify-between items-center mb-4">
              <span
                className="font-mono text-xs py-1 px-2.5 rounded-lg"
                style={{
                  background: "rgba(255,255,255,.05)",
                  border: "1px solid var(--border)",
                  color: "#a5b4fc",
                }}
              >
                {runId}
              </span>
              <span
                className={`pill ${
                  isComplete ? "pill-pass" :
                  isFailed ? "pill-fail" : "pill-err"
                }`}
              >
                {isRunning && (
                  <span className="inline-block w-2 h-2 rounded-full mr-1 animate-pulse" style={{ background: "#fff" }} />
                )}
                {isComplete ? "Completed" : isFailed ? "Failed" : status?.status ?? "Starting…"}
              </span>
            </div>

            {/* Overall progress bar */}
            <div className="mb-5">
              <div className="flex justify-between items-center mb-2">
                <span className="text-xs font-semibold" style={{ color: "var(--t2)" }}>
                  {isRunning
                    ? `Processing ${progress.currentTable ?? "…"}`
                    : isComplete
                    ? "All tables processed"
                    : isFailed
                    ? "Pipeline encountered an error"
                    : "Initializing…"}
                </span>
                <span className="text-sm font-bold text-white">
                  {isComplete ? "100" : pct}%
                </span>
              </div>
              <div
                className="h-2 rounded-full overflow-hidden"
                style={{ background: "rgba(255,255,255,.06)" }}
              >
                <div
                  className="h-full rounded-full transition-all duration-700 ease-out"
                  style={{
                    width: `${isComplete ? 100 : pct}%`,
                    background: isFailed
                      ? "var(--failed)"
                      : progress.hasError
                      ? "linear-gradient(90deg, var(--success), var(--warning))"
                      : "var(--grad)",
                    boxShadow: isRunning ? "0 0 12px rgba(99,102,241,.5)" : undefined,
                  }}
                />
              </div>
              <div className="flex justify-between mt-1.5">
                <span className="text-[11px]" style={{ color: "var(--t3)" }}>
                  {progress.completedSteps} of {progress.steps.length} table{progress.steps.length !== 1 ? "s" : ""}
                </span>
                <span className="text-[11px]" style={{ color: "var(--t3)" }}>
                  {progress.totalRules} rule{progress.totalRules !== 1 ? "s" : ""} total
                </span>
              </div>
            </div>

            {/* Table steps */}
            {progress.steps.length > 0 && (
              <div className="space-y-2 mb-4">
                {progress.steps.map((step, i) => {
                  const stepHasFailures = (step.failedCount ?? 0) > 0;
                  return (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-300"
                      style={{
                        background: step.status === "running"
                          ? "rgba(59,130,246,.08)"
                          : step.status === "error"
                          ? "rgba(239,68,68,.06)"
                          : "rgba(255,255,255,.02)",
                        border: step.status === "running"
                          ? "1px solid rgba(59,130,246,.2)"
                          : "1px solid var(--border)",
                      }}
                    >
                      {/* Status icon */}
                      <div className="shrink-0">
                        {step.status === "pending" && (
                          <span className="inline-block w-5 h-5 rounded-full" style={{ background: "#334155" }} />
                        )}
                        {step.status === "running" && (
                          <span
                            className="inline-block w-5 h-5 rounded-full animate-pulse"
                            style={{ background: "var(--blue)", boxShadow: "0 0 12px rgba(59,130,246,.6)" }}
                          />
                        )}
                        {step.status === "done" && !stepHasFailures && (
                          <span
                            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white"
                            style={{ background: "var(--success)", boxShadow: "0 0 8px rgba(16,185,129,.4)" }}
                          >
                            ✓
                          </span>
                        )}
                        {step.status === "done" && stepHasFailures && (
                          <span
                            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white"
                            style={{ background: "var(--warning)", boxShadow: "0 0 8px rgba(245,158,11,.4)" }}
                          >
                            !
                          </span>
                        )}
                        {step.status === "error" && (
                          <span
                            className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white"
                            style={{ background: "var(--failed)", boxShadow: "0 0 8px rgba(239,68,68,.4)" }}
                          >
                            ✗
                          </span>
                        )}
                      </div>

                      {/* Table info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-white truncate">
                            {step.schema}.{step.table}
                          </span>
                          <span className="text-[11px] shrink-0" style={{ color: "var(--t3)" }}>
                            {step.ruleCount} rule{step.ruleCount !== 1 ? "s" : ""}
                          </span>
                        </div>
                        {step.status === "running" && (
                          <div className="text-[11px] mt-0.5" style={{ color: "var(--blue)" }}>
                            Evaluating…
                          </div>
                        )}
                        {step.status === "done" && (
                          <div className="text-[11px] mt-0.5" style={{ color: "var(--t3)" }}>
                            {step.resultCount} result{(step.resultCount ?? 0) !== 1 ? "s" : ""}
                            {stepHasFailures && (
                              <span style={{ color: "var(--failed)", fontWeight: 700 }}>
                                {" "}· {step.failedCount} failed row{(step.failedCount ?? 0) !== 1 ? "s" : ""}
                              </span>
                            )}
                          </div>
                        )}
                        {step.status === "error" && (
                          <div className="text-[11px] mt-0.5" style={{ color: "var(--failed)" }}>
                            Evaluation failed — skipped
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Waiting state when no steps parsed yet */}
            {progress.steps.length === 0 && isRunning && (
              <div className="text-center py-6">
                <div className="text-sm animate-pulse" style={{ color: "var(--t2)" }}>
                  Initializing pipeline…
                </div>
                <div className="text-xs mt-1" style={{ color: "var(--t3)" }}>
                  Loading active rules and connecting to database
                </div>
              </div>
            )}

            {/* Toggle log viewer */}
            <button
              className="w-full text-xs font-medium py-2 mt-1 rounded-lg transition-colors"
              style={{
                background: "rgba(255,255,255,.03)",
                border: "1px solid var(--border)",
                color: "var(--t3)",
                cursor: "pointer",
              }}
              onClick={() => setShowLog(!showLog)}
            >
              {showLog ? "▲ Hide Log Output" : "▼ Show Log Output"}
            </button>

            {/* Collapsible log */}
            {showLog && (
              <div
                ref={logRef}
                className="rounded-xl overflow-y-auto font-mono text-[12px] leading-relaxed mt-3"
                style={{
                  background: "#050507",
                  maxHeight: 260,
                  padding: 14,
                  color: "#4ADE80",
                }}
              >
                {(status?.log_tail ?? []).map((line, i) => (
                  <div
                    key={i}
                    className="whitespace-pre-wrap"
                    style={{
                      color: line.match(/ERROR|Exception|Traceback|failed/i)
                        ? "#EF4444"
                        : line.includes("✓")
                        ? "#4ADE80"
                        : line.includes("→")
                        ? "#67e8f9"
                        : "#94A3B8",
                    }}
                  >
                    {line}
                  </div>
                ))}
                {isRunning && <div className="animate-pulse" style={{ color: "#06B6D4" }}>…</div>}
              </div>
            )}

            {/* Error banner */}
            {isFailed && (
              <div
                className="mt-3 rounded-[10px] p-3 text-[13px] flex items-start gap-2"
                style={{
                  background: "rgba(239,68,68,.08)",
                  border: "1px solid rgba(239,68,68,.3)",
                  color: "#fca5a5",
                }}
              >
                <span className="text-base">✗</span>
                <div>
                  <span className="font-semibold">Pipeline failed</span>
                  <span> with exit code {status?.returncode}. </span>
                  {!showLog && (
                    <button
                      className="underline font-semibold"
                      style={{ color: "#fca5a5", background: "none", border: "none", cursor: "pointer" }}
                      onClick={() => setShowLog(true)}
                    >
                      Show log for details
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Post-run summary */}
        {isComplete && (
          <div className="grid grid-cols-3 gap-4 mt-5">
            {[
              { label: "Total Checks", value: totalRan,  color: "var(--blue)" },
              { label: "Passed",       value: passed,    color: "var(--success)" },
              { label: "Failed",       value: failedCnt, color: "var(--failed)" },
            ].map(({ label, value, color }) => (
              <div key={label} className="glass text-center relative" style={{ padding: 20 }}>
                <div
                  className="absolute left-0 top-0 bottom-0 w-1 rounded"
                  style={{ background: color }}
                />
                <div className="text-[32px] font-extrabold text-white">{value.toLocaleString()}</div>
                <div
                  className="text-xs uppercase tracking-wider font-semibold mt-1.5"
                  style={{ color: "var(--t2)" }}
                >
                  {label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
