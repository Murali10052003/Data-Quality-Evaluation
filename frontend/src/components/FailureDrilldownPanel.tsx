import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getFailedRows, exportUrl } from "../api/client";

const PAGE_SIZE = 100;

interface Props {
  row: Record<string, unknown>;
  onClose: () => void;
}

export default function FailureDrilldownPanel({ row, onClose }: Props) {
  const runId     = row.run_id as string;
  const tableName = row.table_name as string;
  const method    = row.dqmethod as string;
  const col       = row.col as string;
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["failed-rows", runId, tableName, method, col, page],
    queryFn: () =>
      getFailedRows({ run_id: runId, table: tableName, method, col, page, page_size: PAGE_SIZE }),
    enabled: !!runId && !!tableName,
  });

  const rows: { failed_row?: Record<string, unknown> }[] = data?.rows ?? [];
  const total: number = data?.total ?? 0;
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div
      className="fixed right-0 top-0 h-full flex flex-col z-50 overflow-y-auto"
      style={{
        width: 480,
        maxWidth: "92vw",
        background: "rgba(15,23,42,.9)",
        backdropFilter: "blur(18px)",
        borderLeft: "1px solid var(--border)",
        boxShadow: "-20px 0 60px rgba(0,0,0,.6)",
        padding: 24,
      }}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-[18px]">
        <div className="text-[15px] font-bold text-white">Failure Detail</div>
        <button className="btn-secondary" onClick={onClose}>✕</button>
      </div>

      {/* Export button */}
      <a
        href={exportUrl(runId, tableName, method)}
        className="btn-primary w-full justify-center mb-[18px]"
      >
        ⬇ Export Failed Rows
      </a>

      {/* Summary */}
      <div className="text-xs mb-4" style={{ color: "var(--t2)" }}>
        {total.toLocaleString()} total failed row(s) · showing page {page}/{totalPages || 1}
      </div>

      {/* KV cards */}
      {[
        { k: "Table", v: tableName },
        { k: "Method", v: method },
        { k: "Column", v: col },
        { k: "Failed Rows", v: String(total), color: "var(--failed)" },
      ].map(({ k, v, color }) => (
        <div
          key={k}
          className="rounded-[10px] p-3 mb-2.5"
          style={{
            background: "rgba(255,255,255,.03)",
            border: "1px solid var(--border)",
          }}
        >
          <div
            className="text-[11px] uppercase tracking-wider"
            style={{ color: "var(--t3)" }}
          >
            {k}
          </div>
          <div
            className="text-sm font-mono mt-1"
            style={{ color: color ?? "#fff" }}
          >
            {v}
          </div>
        </div>
      ))}

      {/* Body */}
      <div className="flex-1 mt-3 space-y-3">
        {isLoading && (
          <p className="text-sm animate-pulse" style={{ color: "var(--t2)" }}>Loading…</p>
        )}
        {!isLoading && rows.length === 0 && (
          <p className="text-sm" style={{ color: "var(--t2)" }}>No failed rows found for this check.</p>
        )}
        {rows.map((rec, i) => (
          <div
            key={i}
            className="rounded-[10px] p-3"
            style={{
              background: "rgba(255,255,255,.03)",
              border: "1px solid var(--border)",
            }}
          >
            <p className="text-xs font-mono mb-2" style={{ color: "var(--t3)" }}>
              row {(page - 1) * PAGE_SIZE + i + 1}
            </p>
            {Object.entries(rec.failed_row ?? {}).map(([k, v]) => (
              <div
                key={k}
                className="flex gap-2 text-xs py-0.5"
                style={{ borderBottom: "1px solid var(--border)" }}
              >
                <span className="font-medium w-28 shrink-0" style={{ color: "var(--cyan)" }}>{k}</span>
                <span
                  className="font-mono break-all"
                  style={{
                    color: v === null ? "var(--failed)" : "var(--t1)",
                    fontStyle: v === null ? "italic" : undefined,
                  }}
                >
                  {v === null ? "null" : String(v)}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div
          className="flex items-center justify-between mt-4 pt-3"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          <button
            className="btn-secondary text-xs"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            ← Prev
          </button>
          <span className="text-xs" style={{ color: "var(--t2)" }}>
            Page {page} of {totalPages}
          </span>
          <button
            className="btn-secondary text-xs"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
