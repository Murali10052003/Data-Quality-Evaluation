import { Fragment, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getSchemas,
  getTables,
  getColumns,
  getRules,
  createRule,
  patchRule,
  deleteRule,
} from "../api/client";
import DynamicConfigForm from "../components/DynamicConfigForm";
import { useToast } from "../context/ToastContext";

const DQ_METHODS = [
  "DupEval", "EmptyEval", "UniqueEval", "DtypeEval",
  "StringFormatEval", "RangeEval", "CategoricalValuesEval",
  "StatisticalDistributionEval", "DataFreshnessEval",
  "ReferentialIntegrityEval", "RowCountEval", "CustomEval",
  "SchemaValidationEval", "UnicodeValidationEval",
  "DateRangeEval", "MojibakeEval",
];

type Rule = {
  control_id: number;
  schema_name: string;
  table_name: string;
  dqmethod: string;
  is_active: boolean;
  config: Record<string, unknown>;
};

export default function RuleManager() {
  const qc = useQueryClient();
  const { toast } = useToast();
  const [spinning, setSpinning] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const [filterSchema, setFilterSchema] = useState("");
  const [filterTable,  setFilterTable]  = useState("");
  const [filterActive, setFilterActive] = useState<"" | "true" | "false">("");

  const [expandedId, setExpandedId] = useState<number | null>(null);

  const [showForm,    setShowForm]    = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [fSchema,     setFSchema]     = useState("public");
  const [fTable,      setFTable]      = useState("");
  const [fMethod,     setFMethod]     = useState("EmptyEval");
  const [fConfig,     setFConfig]     = useState<Record<string, unknown>>({});
  const [validationError, setValidationError] = useState("");

  const { data: schemas = [] } = useQuery({
    queryKey: ["schemas"],
    queryFn: getSchemas,
  });

  const { data: rawTables = [] } = useQuery({
    queryKey: ["tables", fSchema],
    queryFn: () => getTables(fSchema),
    enabled: !!fSchema,
  });
  const tables = (rawTables as string[]).filter(
    (t) => t !== "dq_control" && t !== "dq_results"
  );

  const { data: columns = [] } = useQuery({
    queryKey: ["columns", fSchema, fTable],
    queryFn: () => getColumns(fSchema, fTable),
    enabled: !!fTable,
  });

  const { data: rawRules = [], isLoading, isError } = useQuery({
    queryKey: ["rules", filterSchema, filterTable],
    queryFn: () => getRules(filterSchema, filterTable),
  });

  const { data: allRulesForDropdown = [] } = useQuery({
    queryKey: ["rules", filterSchema, ""],
    queryFn: () => getRules(filterSchema, ""),
  });

  const rules = (rawRules as Rule[]).filter((r) => {
    if (filterActive === "true")  return r.is_active;
    if (filterActive === "false") return !r.is_active;
    return true;
  });

  const createMut = useMutation({
    mutationFn: createRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      setShowForm(false);
      setShowPreview(false);
      setFConfig({});
      setValidationError("");
      toast("Rule created successfully");
    },
    onError: () => {
      toast("Failed to create rule", "error");
    },
  });

  const patchMut = useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      patchRule(id, active),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      toast("Rule updated");
    },
  });

  const deleteMut = useMutation({
    mutationFn: deleteRule,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["rules"] });
      toast("Rule deleted");
    },
  });

  const handleRefresh = () => {
    setSpinning(true);
    qc.invalidateQueries({ queryKey: ["rules"] });
    setTimeout(() => setSpinning(false), 600);
  };

  const handleBulkToggle = async (active: boolean) => {
    const ids = [...selectedIds];
    await Promise.all(ids.map((id) => patchRule(id, active)));
    qc.invalidateQueries({ queryKey: ["rules"] });
    setSelectedIds(new Set());
    toast(`${ids.length} rule(s) ${active ? "enabled" : "disabled"}`);
  };

  const handleBulkDelete = async () => {
    if (!confirm(`Delete ${selectedIds.size} selected rule(s)?`)) return;
    const ids = [...selectedIds];
    await Promise.all(ids.map((id) => deleteRule(id)));
    qc.invalidateQueries({ queryKey: ["rules"] });
    setSelectedIds(new Set());
    toast(`${ids.length} rule(s) deleted`);
  };

  const toggleSelection = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === rules.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(rules.map((r) => r.control_id)));
    }
  };

  const validateConfig = (method: string, config: Record<string, unknown>): string => {
    const cols = config.columns;
    const col = config.column as string;

    if (["DupEval", "EmptyEval", "UniqueEval", "UnicodeValidationEval"].includes(method)) {
      if (!Array.isArray(cols) || cols.length === 0)
        return "Please select at least one column.";
    }
    if (["RangeEval", "StringFormatEval", "CategoricalValuesEval", "DataFreshnessEval", "StatisticalDistributionEval", "DateRangeEval", "MojibakeEval"].includes(method)) {
      if (!col) return "Please select a column.";
    }
    if (method === "DateRangeEval") {
      if (!config.min_date) return "Please specify a minimum date.";
      if (!config.max_date) return "Please specify a maximum date.";
    }
    if (method === "RangeEval") {
      if (config.min === undefined || config.min === "") return "Please specify a minimum value.";
      if (config.max === undefined || config.max === "") return "Please specify a maximum value.";
    }
    if (method === "StringFormatEval") {
      if (!config.pattern) return "Please provide a regex pattern.";
    }
    if (method === "CategoricalValuesEval") {
      const vals = config.allowed_values;
      if (!Array.isArray(vals) || vals.length === 0) return "Please provide at least one allowed value.";
    }
    if (method === "DataFreshnessEval") {
      if (!config.freshness_threshold) return "Please provide a freshness threshold (e.g. -2h).";
    }
    if (method === "ReferentialIntegrityEval") {
      if (!col) return "Please select a column.";
      if (!config.reference_df) return "Please specify a reference table.";
      if (!config.reference_column) return "Please specify a reference column.";
    }
    if (method === "CustomEval") {
      if (!config.func) return "Please provide a lambda function.";
    }
    if (method === "RowCountEval") {
      if (config.min === undefined && config.max === undefined) return "Please specify at least min or max row count.";
    }
    if (method === "DtypeEval") {
      const colMap = config.columns as Record<string, string> | undefined;
      if (!colMap || Object.values(colMap).filter(Boolean).length === 0)
        return "Please assign a dtype to at least one column.";
    }
    if (method === "SchemaValidationEval") {
      const schemaMap = config.expected_schema as Record<string, string> | undefined;
      if (!schemaMap || Object.values(schemaMap).filter(Boolean).length === 0)
        return "Please assign an expected type to at least one column.";
    }
    if (method === "StatisticalDistributionEval") {
      const mode = (config.mode as string) || "feature_drift";
      if (mode === "feature_drift") {
        const stats = config.reference_stats as Record<string, number> | undefined;
        if (!stats || stats.mean === undefined || stats.std === undefined)
          return "Please provide reference mean and std values.";
      }
    }
    return "";
  };

  return (
    <div className="space-y-[22px] w-full" style={{ animation: "fadein .4s ease" }}>
      {/* Command bar */}
      <div
        className="glass flex items-center justify-between gap-4 flex-wrap"
        style={{ padding: "0 20px", minHeight: 56 }}
      >
        <div className="text-2xl font-bold text-white">Rule Manager</div>
        <div className="flex items-center gap-2.5">
          <button className="btn-primary" onClick={() => { setShowForm((v) => !v); setShowPreview(false); }}>
            {showForm ? "Cancel" : "+ New Rule"}
          </button>
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

      {/* Create rule slide */}
      <div
        className="transition-all duration-400"
        style={{
          maxHeight: showForm ? "85vh" : 0,
          overflowY: showForm ? "auto" : "hidden",
          opacity: showForm ? 1 : 0,
          marginBottom: showForm ? 22 : 0,
        }}
      >
        <div className="glass relative" style={{ padding: 20 }}>
          {/* Left accent */}
          <div className="absolute left-0 top-0 bottom-0 w-1 rounded" style={{ background: "var(--grad)" }} />

          <div className="text-[15px] font-bold text-white mb-4">Create New Rule</div>

          <div className="grid grid-cols-3 gap-3.5">
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Schema</label>
              <select
                className="input-base w-full"
                value={fSchema}
                onChange={(e) => { setFSchema(e.target.value); setFTable(""); }}
              >
                {schemas.map((s) => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Table</label>
              <select
                className="input-base w-full"
                value={fTable}
                onChange={(e) => setFTable(e.target.value)}
              >
                <option value="">Select…</option>
                {tables.map((t) => <option key={t}>{t}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Method</label>
              <select
                className="input-base w-full"
                value={fMethod}
                onChange={(e) => { setFMethod(e.target.value); setFConfig({}); }}
              >
                {DQ_METHODS.map((m) => <option key={m}>{m}</option>)}
              </select>
            </div>
          </div>

          {/* Column chips */}
          {fTable && (columns as { column_name: string; data_type: string }[]).length > 0 && (
            <div className="mt-4">
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--t2)" }}>Available columns</label>
              <div className="flex flex-wrap gap-2 mt-1.5">
                {(columns as { column_name: string; data_type: string }[]).map((c) => (
                  <span
                    key={c.column_name}
                    className="font-mono text-xs py-1 px-2.5 rounded-lg"
                    style={{
                      background: "rgba(255,255,255,.04)",
                      border: "1px solid var(--border)",
                      color: "#a5b4fc",
                    }}
                  >
                    {c.column_name}
                    <span className="ml-1" style={{ color: "var(--t3)" }}>({c.data_type})</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          <DynamicConfigForm
            method={fMethod}
            columns={columns as { column_name: string; data_type: string }[]}
            onChange={setFConfig}
          />

          {/* JSON preview */}
          {showPreview && (
            <pre
              className="mt-4 rounded-[10px] p-3.5 font-mono text-xs overflow-x-auto"
              style={{
                background: "#0A0A0F",
                border: "1px solid var(--border)",
                lineHeight: 1.6,
                color: "#86efac",
              }}
            >
              {JSON.stringify(
                { schema_name: fSchema, table_name: fTable, dqmethod: fMethod, config: fConfig, is_active: true },
                null,
                2
              )}
            </pre>
          )}

          {(validationError || createMut.isError) && (
            <div
              className="mt-3 rounded-[10px] p-2.5 text-[13px]"
              style={{
                background: "rgba(239,68,68,.08)",
                border: "1px solid rgba(239,68,68,.3)",
                color: "#fca5a5",
              }}
            >
              {validationError || "Failed to create rule. Check the config and try again."}
            </div>
          )}

          <div className="flex gap-2.5 items-center mt-4">
            <button
              className="btn-primary"
              disabled={!fTable || createMut.isPending}
              onClick={() => {
                // Validate config completeness based on method
                const err = validateConfig(fMethod, fConfig);
                if (!fTable) {
                  setValidationError("Please select a table.");
                  return;
                }
                if (err) {
                  setValidationError(err);
                  return;
                }
                setValidationError("");
                createMut.mutate({
                  schema_name: fSchema,
                  table_name: fTable,
                  dqmethod: fMethod,
                  config: fConfig,
                  is_active: true,
                });
              }}
            >
              {createMut.isPending ? "Saving…" : "Save Rule"}
            </button>
            <button className="btn-secondary" onClick={() => setShowPreview((v) => !v)}>
              {"{ } "}{showPreview ? "Hide" : "Preview JSON"}
            </button>
            <button
              className="text-[13px] font-semibold px-2.5 py-2 transition-colors"
              style={{ background: "transparent", border: "none", color: "var(--t2)", cursor: "pointer" }}
              onClick={() => setShowForm(false)}
              onMouseEnter={(e) => { (e.target as HTMLElement).style.color = "#fff"; }}
              onMouseLeave={(e) => { (e.target as HTMLElement).style.color = "var(--t2)"; }}
            >
              Cancel
            </button>
          </div>
        </div>
      </div>

      {/* Filters + Bulk actions */}
      <div className="glass" style={{ padding: "16px 20px" }}>
        <div className="flex gap-3 flex-wrap items-center">
          <select className="input-base" value={filterSchema} onChange={(e) => setFilterSchema(e.target.value)}>
            <option value="">All Schemas</option>
            {schemas.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select className="input-base" value={filterTable} onChange={(e) => setFilterTable(e.target.value)}>
            <option value="">All Tables</option>
            {[...new Set((allRulesForDropdown as Rule[]).map((r) => r.table_name))].sort().map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <select className="input-base" value={filterActive} onChange={(e) => setFilterActive(e.target.value as "" | "true" | "false")}>
            <option value="">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
          <span className="text-[13px]" style={{ color: "var(--t2)" }}>
            {rules.length} rule{rules.length !== 1 ? "s" : ""}
          </span>
          {selectedIds.size > 0 && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs font-semibold" style={{ color: "var(--blue)" }}>
                {selectedIds.size} selected
              </span>
              <button
                className="btn-secondary text-xs"
                style={{ padding: "4px 10px", fontSize: 12 }}
                onClick={() => handleBulkToggle(true)}
              >
                Enable
              </button>
              <button
                className="btn-secondary text-xs"
                style={{ padding: "4px 10px", fontSize: 12 }}
                onClick={() => handleBulkToggle(false)}
              >
                Disable
              </button>
              <button
                className="text-xs font-semibold px-2.5 py-1 rounded-lg transition-colors"
                style={{ background: "rgba(220,38,38,.1)", border: "1px solid rgba(220,38,38,.3)", color: "#fca5a5", cursor: "pointer" }}
                onClick={handleBulkDelete}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Rules table */}
      <div className="glass overflow-hidden">
        {isLoading ? (
          <p className="text-sm p-5 animate-pulse" style={{ color: "var(--t2)" }}>Loading rules…</p>
        ) : isError ? (
          <p className="text-sm p-5" style={{ color: "var(--failed)" }}>Failed to load rules. Is the backend running?</p>
        ) : (
          <table className="w-full text-[13px]" style={{ borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th
                  className="text-left p-3"
                  style={{ background: "rgba(255,255,255,.03)", width: 40 }}
                >
                  <input
                    type="checkbox"
                    className="accent-indigo-500"
                    checked={rules.length > 0 && selectedIds.size === rules.length}
                    onChange={toggleAll}
                  />
                </th>
                {["", "Schema", "Table", "Method", "Active", "Actions"].map((h) => (
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
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <Fragment key={r.control_id}>
                  <tr
                    className="cursor-pointer transition-colors"
                    style={{ borderTop: "1px solid var(--border)" }}
                    onClick={() =>
                      setExpandedId(expandedId === r.control_id ? null : r.control_id)
                    }
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background = "rgba(255,255,255,.03)";
                      e.currentTarget.style.boxShadow = "inset 3px 0 0 var(--blue)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "";
                      e.currentTarget.style.boxShadow = "";
                    }}
                  >
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        className="accent-indigo-500"
                        checked={selectedIds.has(r.control_id)}
                        onChange={() => toggleSelection(r.control_id)}
                      />
                    </td>
                    <td className="p-3 text-xs select-none" style={{ color: "var(--t3)" }}>
                      <span
                        className="inline-block transition-transform duration-300"
                        style={{ transform: expandedId === r.control_id ? "rotate(90deg)" : undefined }}
                      >
                        ▶
                      </span>
                    </td>
                    <td className="p-3" style={{ color: "var(--t1)" }}>{r.schema_name}</td>
                    <td className="p-3 font-mono" style={{ color: "var(--t1)" }}>{r.table_name}</td>
                    <td className="p-3"><span className="badge-method">{r.dqmethod}</span></td>
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <span
                        className="inline-block relative cursor-pointer transition-all duration-300"
                        style={{
                          width: 42, height: 24, borderRadius: 999,
                          background: r.is_active ? "var(--grad)" : "#334155",
                          boxShadow: r.is_active ? "0 0 10px rgba(99,102,241,.4)" : "none",
                        }}
                        onClick={() => patchMut.mutate({ id: r.control_id, active: !r.is_active })}
                      >
                        <span
                          className="absolute rounded-full transition-all duration-300"
                          style={{
                            top: 3, width: 18, height: 18,
                            left: r.is_active ? 21 : 3,
                            background: r.is_active ? "#fff" : "#cbd5e1",
                          }}
                        />
                      </span>
                    </td>
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <span
                        className="text-xs font-semibold cursor-pointer"
                        style={{ color: "var(--failed)" }}
                        onClick={() => {
                          if (confirm("Delete this rule?"))
                            deleteMut.mutate(r.control_id);
                        }}
                        onMouseEnter={(e) => { (e.target as HTMLElement).style.textDecoration = "underline"; }}
                        onMouseLeave={(e) => { (e.target as HTMLElement).style.textDecoration = ""; }}
                      >
                        Delete
                      </span>
                    </td>
                  </tr>
                  {expandedId === r.control_id && (
                    <tr>
                      <td colSpan={7} style={{ borderTop: "1px solid var(--border)" }}>
                        <pre
                          className="m-3 rounded-[10px] p-3.5 font-mono text-xs overflow-x-auto"
                          style={{
                            background: "#0A0A0F",
                            border: "1px solid var(--border)",
                            lineHeight: 1.6,
                            color: "#a5b4fc",
                          }}
                        >
                          <span style={{ color: "#c4b5fd" }}>{"{"}</span>{"\n"}
                          {Object.entries(r.config ?? {}).map(([k, v], idx, arr) => (
                            <span key={k}>
                              {"  "}<span style={{ color: "#c4b5fd" }}>"{k}"</span>:{" "}
                              <span style={{ color: typeof v === "string" ? "#86efac" : "#fcd34d" }}>
                                {JSON.stringify(v)}
                              </span>
                              {idx < arr.length - 1 ? "," : ""}{"\n"}
                            </span>
                          ))}
                          <span style={{ color: "#c4b5fd" }}>{"}"}</span>
                        </pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {rules.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-5 text-center text-sm" style={{ color: "var(--t2)" }}>
                    No rules found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
