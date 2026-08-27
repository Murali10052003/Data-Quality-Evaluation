import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
} from "recharts";
import { getSummary, getResults, getRules, listRuns } from "../api/client";
import TableHealthMatrix from "../components/TableHealthMatrix";

const PIE_COLORS = ["#10B981", "#EF4444", "#D97706"];

const KPI_CONFIGS = [
  { key: "totalRules",  label: "Total Rules",  color: "#3B82F6", glow: "rgba(59,130,246,.15)",  icon: "📋" },
  { key: "activeRules", label: "Active Rules", color: "#06B6D4", glow: "rgba(6,182,212,.15)",   icon: "✅" },
  { key: "totalChecks", label: "Total Checks", color: "#8B5CF6", glow: "rgba(139,92,246,.15)",  icon: "🔍" },
  { key: "passed",      label: "Passed",       color: "#10B981", glow: "rgba(16,185,129,.15)",  icon: "✓" },
  { key: "failed",      label: "Failed",       color: "#EF4444", glow: "rgba(239,68,68,.15)",   icon: "✗" },
  { key: "errors",      label: "Errors",       color: "#F59E0B", glow: "rgba(245,158,11,.15)",  icon: "⚠" },
];

function KpiCard({ label, value, color, glow, icon, trend, pct }: {
  label: string; value: string; color: string; glow: string;
  icon: string; trend?: { text: string; up: boolean }; pct: number;
}) {
  return (
    <div
      className="glass relative overflow-hidden transition-all duration-300"
      style={{
        padding: "18px 18px 16px",
        ["--kc" as string]: color,
        ["--kg" as string]: glow,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-6px)";
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.boxShadow = `0 14px 40px -10px ${glow}`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "";
        e.currentTarget.style.borderColor = "";
        e.currentTarget.style.boxShadow = "";
      }}
    >
      {/* Left accent bar */}
      <div
        className="absolute left-0 top-0 bottom-0 w-1 rounded"
        style={{ background: color }}
      />
      <div className="flex justify-between items-start mb-3">
        {trend && (
          <span className="text-[11px] font-bold" style={{ color: trend.up ? "var(--success)" : "var(--failed)" }}>
            {trend.text}
          </span>
        )}
      </div>
      <div className="text-4xl font-extrabold text-white leading-none tracking-tight">
        {value}
      </div>
      <div
        className="text-[11px] uppercase tracking-wider font-semibold mt-2"
        style={{ color: "var(--t2)" }}
      >
        {label}
      </div>
      <div className="h-1 rounded mt-3 overflow-hidden" style={{ background: "rgba(255,255,255,.06)" }}>
        <div
          className="h-full rounded transition-all duration-1000"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}

export default function Dashboard() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [spinning, setSpinning] = useState(false);

  const [runId, setRunId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const filterParams = useMemo(() => {
    const p: Record<string, string> = {};
    if (runId) p.run_id = runId;
    // Only apply date filter when both from and to are selected
    if (dateFrom && dateTo) {
      p.from = dateFrom;
      p.to = dateTo;
    }
    return p;
  }, [runId, dateFrom, dateTo]);

  const { data: runs = [] } = useQuery({
    queryKey: ["runs"],
    queryFn: listRuns,
  });

  const { data: summary, isLoading: sl, isError: se } = useQuery({
    queryKey: ["summary", filterParams],
    queryFn: () => getSummary(filterParams),
  });
  const { data: recentRes, isLoading: rl } = useQuery({
    queryKey: ["recent-results", filterParams],
    queryFn: () => getResults({ page: 1, page_size: 200, ...filterParams }),
  });
  const { data: allRules = [] } = useQuery({
    queryKey: ["rules"],
    queryFn: () => getRules(),
  });

  const handleRefresh = () => {
    setSpinning(true);
    qc.invalidateQueries();
    setTimeout(() => setSpinning(false), 600);
  };

  if (sl || rl) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-lg animate-pulse" style={{ color: "var(--t2)" }}>Loading dashboard…</p>
      </div>
    );
  }
  if (se) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="font-medium mb-2" style={{ color: "var(--failed)" }}>Failed to load dashboard</p>
          <button className="btn-secondary text-sm" onClick={() => qc.invalidateQueries()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const rows = recentRes?.rows ?? [];
  const total   = summary?.total   ?? 0;
  const success = summary?.success ?? 0;
  const failed  = summary?.failed  ?? 0;
  const error   = summary?.error   ?? 0;
  const totalRules  = (allRules as { is_active: boolean }[]).length;
  const activeRules = (allRules as { is_active: boolean }[]).filter((r) => r.is_active).length;

  const kpiValues: Record<string, { value: string; pct: number; trend?: { text: string; up: boolean } }> = {
    totalRules:  { value: totalRules.toLocaleString(),  pct: totalRules > 0 ? 84 : 0 },
    activeRules: { value: activeRules.toLocaleString(), pct: totalRules > 0 ? (activeRules / totalRules) * 100 : 0 },
    totalChecks: { value: total.toLocaleString(),       pct: total > 0 ? 78 : 0 },
    passed:      { value: success.toLocaleString(),     pct: total > 0 ? (success / total) * 100 : 0 },
    failed:      { value: failed.toLocaleString(),      pct: total > 0 ? (failed / total) * 100 : 0 },
    errors:      { value: error.toLocaleString(),       pct: total > 0 ? (error / total) * 100 : 0 },
  };

  const pieData = [
    { name: "Success", value: success },
    { name: "Failed",  value: failed  },
    { name: "Error",   value: error   },
  ].filter((d) => d.value > 0);

  const recentFailed = (rows as {
    table_name: string; dqmethod: string; col: string;
    dqevalcount: number; run_timestamp: string; status: string;
  }[]).filter((r) => r.status === "Failed").slice(0, 10);

  return (
    <div className="flex flex-col gap-[22px] w-full" style={{ animation: "fadein .4s ease" }}>
      {/* Header */}
      <div className="mb-0">
        <h1 className="text-[26px] font-bold text-white m-0">Data Quality Dashboard</h1>
        <p className="text-xs mt-1" style={{ color: "#64748B" }}>
          Last refreshed: {new Date().toLocaleString()}
        </p>
      </div>

      {/* Filter bar */}
      <div className="glass flex items-end gap-5 flex-wrap" style={{ padding: "16px 20px" }}>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-medium" style={{ color: "#94A3B8" }}>Run ID</label>
          <select
            className="input-base min-w-[220px]"
            value={runId}
            onChange={(e) => setRunId(e.target.value)}
          >
            <option value="">All Runs</option>
            {(runs as { run_id: string; started_at: string; total: number }[]).map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {r.run_id.slice(0, 8)}… — {new Date(r.started_at).toLocaleDateString()} ({r.total} checks)
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-medium" style={{ color: "#94A3B8" }}>From</label>
          <input
            type="datetime-local"
            className="input-base"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-medium" style={{ color: "#94A3B8" }}>To</label>
          <input
            type="datetime-local"
            className="input-base"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
          />
        </div>
        <button
          className="btn-secondary"
          style={{ marginBottom: 1 }}
          onClick={() => { setRunId(""); setDateFrom(""); setDateTo(""); }}
        >
          Clear Filters
        </button>
        <div className="ml-auto">
          <button className="btn-secondary" onClick={handleRefresh}>
            <span
              className="inline-block transition-transform duration-500"
              style={{ transform: spinning ? "rotate(360deg)" : undefined }}
            >
              ↻
            </span>{" "}
            Refresh
          </button>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        {KPI_CONFIGS.map((cfg) => {
          const v = kpiValues[cfg.key];
          return (
            <KpiCard
              key={cfg.key}
              label={cfg.label}
              value={v.value}
              color={cfg.color}
              glow={cfg.glow}
              icon={cfg.icon}
              trend={v.trend}
              pct={v.pct}
            />
          );
        })}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="glass">
          <div style={{ padding: "16px 20px 6px" }}>
            <div className="text-[15px] font-bold text-white">Results by Eval Method</div>
            <div className="text-xs mt-0.5" style={{ color: "var(--t3)" }}>
              Success / Failed / Error breakdown per method
            </div>
          </div>
          <div style={{ height: 340, width: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={summary?.by_method ?? []}
                layout="vertical"
                margin={{ top: 8, right: 24, left: 90, bottom: 8 }}
              >
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "#94A3B8" }}
                  axisLine={{ stroke: "#334155" }}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="dqmethod"
                  tick={{ fontSize: 11, fill: "#cbd5e1" }}
                  axisLine={{ stroke: "#334155" }}
                  tickLine={false}
                  tickFormatter={(v: string) => v.replace("Eval", "")}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    background: "var(--tooltip-bg)",
                    border: "1px solid var(--border)",
                    color: "var(--t1)",
                  }}
                />
                <Legend
                  wrapperStyle={{ fontSize: 12, paddingTop: 8, color: "#94A3B8" }}
                  verticalAlign="top"
                  iconType="circle"
                />
                <Bar dataKey="Success" stackId="t" fill="#10B981" cursor="pointer" onClick={(data: { dqmethod?: string }) => { if (data.dqmethod) navigate(`/results?method=${data.dqmethod}`); }} />
                <Bar dataKey="Failed"  stackId="t" fill="#EF4444" cursor="pointer" onClick={(data: { dqmethod?: string }) => { if (data.dqmethod) navigate(`/results?method=${data.dqmethod}`); }} />
                <Bar dataKey="Error"   stackId="t" fill="#D97706" radius={[0, 4, 4, 0]} cursor="pointer" onClick={(data: { dqmethod?: string }) => { if (data.dqmethod) navigate(`/results?method=${data.dqmethod}`); }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass">
          <div style={{ padding: "16px 20px 6px" }}>
            <div className="text-[15px] font-bold text-white">Overall Distribution</div>
            <div className="text-xs mt-0.5" style={{ color: "var(--t3)" }}>
              Aggregate outcome across all checks
            </div>
          </div>
          <div style={{ height: 340, width: "100%" }} className="flex items-center justify-center">
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="46%"
                    innerRadius="22%"
                    outerRadius="72%"
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    labelLine={false}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      background: "var(--tooltip-bg)",
                      border: "1px solid var(--border)",
                      color: "var(--t1)",
                    }}
                  />
                  <Legend
                    verticalAlign="bottom"
                    iconType="circle"
                    wrapperStyle={{ fontSize: 12, color: "#94A3B8" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm" style={{ color: "var(--t2)" }}>No data yet.</p>
            )}
          </div>
        </div>
      </div>

      {/* Table Health Matrix */}
      <div className="glass overflow-hidden">
        <div
          className="flex items-center justify-between flex-wrap gap-2.5"
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div>
            <div className="text-[15px] font-bold text-white">Table Health Matrix</div>
            <div className="text-xs mt-0.5" style={{ color: "var(--t3)" }}>
              Per-table status across all evaluation methods
            </div>
          </div>
          <div className="flex gap-4 flex-wrap">
            {[
              { label: "Pass", cls: "bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,.5)]" },
              { label: "Fail", cls: "bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,.5)]" },
              { label: "Warning", cls: "bg-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,.5)]" },
              { label: "Not Run", cls: "bg-[#334155]" },
            ].map((l) => (
              <span key={l.label} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--t2)" }}>
                <span className={`w-2.5 h-2.5 rounded-full ${l.cls}`} />
                {l.label}
              </span>
            ))}
          </div>
        </div>
        <div className="overflow-auto" style={{ maxHeight: 420 }}>
          <TableHealthMatrix data={rows} />
        </div>
      </div>

      {/* Recent Failures */}
      <div className="glass overflow-hidden">
        <div
          className="flex items-center gap-2.5"
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border)",
          }}
        >
          <div className="text-[15px] font-bold text-white">Recent Failures</div>
          {recentFailed.length > 0 && (
            <span
              className="text-[11px] font-bold text-white px-2.5 py-0.5 rounded-full"
              style={{
                background: "var(--failed)",
                boxShadow: "0 0 10px rgba(239,68,68,.4)",
              }}
            >
              {recentFailed.length}
            </span>
          )}
        </div>
        {recentFailed.length === 0 ? (
          <p className="text-sm p-5" style={{ color: "var(--t2)" }}>No recent failures. ✓</p>
        ) : (
          <table className="w-full text-[13px]" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr>
                {["Table", "Method", "Column", "Failed Count", "Timestamp", "Status"].map((h) => (
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
                      ...(h === "Failed Count" ? { textAlign: "right" } : {}),
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recentFailed.map((r, i) => (
                <tr
                  key={i}
                  className="transition-colors duration-200"
                  style={{ borderTop: "1px solid var(--border)" }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(239,68,68,.04)";
                    e.currentTarget.style.boxShadow = "inset 3px 0 0 var(--failed)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "";
                    e.currentTarget.style.boxShadow = "";
                  }}
                >
                  <td className="p-3 text-white">{r.table_name}</td>
                  <td className="p-3"><span className="badge-method">{r.dqmethod}</span></td>
                  <td className="p-3 font-mono" style={{ color: "#a5b4fc" }}>{r.col || "—"}</td>
                  <td className="p-3 text-right font-bold" style={{ color: "var(--failed)" }}>
                    {r.dqevalcount?.toLocaleString() ?? "—"}
                  </td>
                  <td className="p-3" style={{ color: "var(--t2)" }}>
                    {r.run_timestamp ? new Date(r.run_timestamp).toLocaleString() : "—"}
                  </td>
                  <td className="p-3"><span className="pill pill-fail">Failed</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}