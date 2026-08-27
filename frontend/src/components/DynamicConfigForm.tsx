import { useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { validateLambda } from "../api/client";

interface Column {
  column_name: string;
  data_type: string;
}

interface Props {
  method: string;
  columns: Column[];
  onChange: (cfg: Record<string, unknown>) => void;
}

export default function DynamicConfigForm({ method, columns, onChange }: Props) {
  const [cfg, setCfg] = useState<Record<string, unknown>>({});
  const [lambdaStatus, setLambdaStatus] = useState<{
    valid: boolean;
    error: string | null;
  } | null>(null);
  const minDateRef = useRef<HTMLInputElement>(null);
  const maxDateRef = useRef<HTMLInputElement>(null);

  const cols = columns.map((c) => c.column_name);

  // Convert ISO yyyy-mm-dd to dd-mm-yyyy for display
  const formatToDisplay = (iso: string) => {
    const parts = iso.split("-");
    return parts.length === 3 ? `${parts[2]}-${parts[1]}-${parts[0]}` : iso;
  };

  const upd = (next: Record<string, unknown>) => {
    // strip internal keys before passing to parent
    const { _scope, ...clean } = next;
    setCfg(next);
    onChange(clean);
  };

  // ── DupEval / EmptyEval / UniqueEval ────────────────────────────────────────
  if (["DupEval", "EmptyEval", "UniqueEval"].includes(method)) {
    return (
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Columns to check
        </label>
        <div className="flex flex-wrap gap-3">
          {cols.map((c) => (
            <label key={c} className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="checkbox"
                className="accent-teal-600"
                checked={Array.isArray(cfg.columns) && (cfg.columns as string[]).includes(c)}
                onChange={(e) => {
                  const prev: string[] = Array.isArray(cfg.columns)
                    ? (cfg.columns as string[])
                    : [];
                  const next = e.target.checked
                    ? [...prev, c]
                    : prev.filter((x) => x !== c);
                  upd({ ...cfg, columns: next });
                }}
              />
              {c}
            </label>
          ))}
        </div>
      </div>
    );
  }

  // ── RangeEval ───────────────────────────────────────────────────────────────
  if (method === "RangeEval") {
    return (
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Column</label>
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Min</label>
          <input
            type="number"
            className="input-base w-full"
            value={(cfg.min as number) ?? ""}
            onChange={(e) => upd({ ...cfg, min: Number(e.target.value) })}
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Max</label>
          <input
            type="number"
            className="input-base w-full"
            value={(cfg.max as number) ?? ""}
            onChange={(e) => upd({ ...cfg, max: Number(e.target.value) })}
          />
        </div>
      </div>
    );
  }

  // ── StringFormatEval ────────────────────────────────────────────────────────
  if (method === "StringFormatEval") {
    const PRESETS = [
      { label: "Email",    value: "^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$" },
      { label: "Phone",    value: "^\\+?[0-9][\\d\\-\\s().]{6,18}$" },
      { label: "URL",      value: "^https?://[^\\s]+" },
      { label: "Date",     value: "^\\d{4}-\\d{2}-\\d{2}$" },
      { label: "UUID",     value: "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$" },
      { label: "AlphaNum", value: "^[A-Za-z0-9]+$" },
    ];
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Column</label>
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Presets</p>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => upd({ ...cfg, pattern: p.value })}
                className="px-2 py-1 bg-slate-100 text-xs rounded border border-slate-200
                           hover:bg-teal-50 hover:border-teal-300 transition-colors"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Regex pattern</label>
          <input
            className="input-base w-full font-mono text-xs"
            placeholder="^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
            value={(cfg.pattern as string) ?? ""}
            onChange={(e) => upd({ ...cfg, pattern: e.target.value })}
          />
        </div>
      </div>
    );
  }

  // ── CategoricalValuesEval ───────────────────────────────────────────────────
  if (method === "CategoricalValuesEval") {
    return (
      <div className="space-y-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Column</label>
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">
            Allowed values (comma-separated)
          </label>
          <input
            className="input-base w-full"
            placeholder="HR,Finance,Engineering"
            onChange={(e) =>
              upd({
                ...cfg,
                allowed_values: e.target.value
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>
      </div>
    );
  }

  // ── DataFreshnessEval ───────────────────────────────────────────────────────
  if (method === "DataFreshnessEval") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Column</label>
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">
            Threshold (e.g. -2h, -1d)
          </label>
          <input
            className="input-base w-full font-mono"
            placeholder="-2h"
            value={(cfg.freshness_threshold as string) ?? ""}
            onChange={(e) =>
              upd({ ...cfg, freshness_threshold: e.target.value })
            }
          />
        </div>
      </div>
    );
  }

  // ── RowCountEval ────────────────────────────────────────────────────────────
  if (method === "RowCountEval") {
    return (
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Min rows</label>
          <input
            type="number"
            className="input-base w-full"
            value={(cfg.min as number) ?? ""}
            onChange={(e) => upd({ ...cfg, min: Number(e.target.value) })}
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">Max rows</label>
          <input
            type="number"
            className="input-base w-full"
            value={(cfg.max as number) ?? ""}
            onChange={(e) => upd({ ...cfg, max: Number(e.target.value) })}
          />
        </div>
      </div>
    );
  }

  // ── StatisticalDistributionEval ─────────────────────────────────────────────
  if (method === "StatisticalDistributionEval") {
    const mode = (cfg.mode as string) || "feature_drift";
    // Ensure mode is always in the config (default isn't written until user interacts)
    if (!cfg.mode) {
      Promise.resolve().then(() => upd({ ...cfg, mode: "feature_drift" }));
    }
    return (
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">Column</label>
            <select
              className="input-base w-full"
              value={(cfg.column as string) ?? ""}
              onChange={(e) => upd({ ...cfg, mode, column: e.target.value })}
            >
              <option value="">Select…</option>
              {cols.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">Mode</label>
            <select
              className="input-base w-full"
              value={mode}
              onChange={(e) => upd({ ...cfg, mode: e.target.value })}
            >
              <option value="feature_drift">feature_drift</option>
              <option value="label_balance">label_balance</option>
            </select>
          </div>
        </div>
        {mode === "feature_drift" && (
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Mean</label>
              <input
                type="number"
                className="input-base w-full"
                onChange={(e) =>
                  upd({
                    ...cfg,
                    reference_stats: {
                      ...((cfg.reference_stats as object) ?? {}),
                      mean: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Std</label>
              <input
                type="number"
                className="input-base w-full"
                onChange={(e) =>
                  upd({
                    ...cfg,
                    reference_stats: {
                      ...((cfg.reference_stats as object) ?? {}),
                      std: Number(e.target.value),
                    },
                  })
                }
              />
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">
                Tolerance (0–1)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                className="input-base w-full"
                onChange={(e) =>
                  upd({ ...cfg, tolerance: Number(e.target.value) })
                }
              />
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── DtypeEval / SchemaValidationEval ────────────────────────────────────────
  if (method === "DtypeEval" || method === "SchemaValidationEval") {
    const configKey = method === "DtypeEval" ? "columns" : "expected_schema";
    const colMap = (cfg[configKey] as Record<string, string>) ?? {};
    return (
      <div className="space-y-2">
        <label className="text-xs text-slate-500 block">
          Column → Expected dtype
        </label>
        <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
          {cols.map((c) => (
            <div key={c} className="flex items-center gap-3">
              <span className="text-sm font-mono text-slate-700 w-32 shrink-0">
                {c}
              </span>
              <select
                className="input-base flex-1"
                value={colMap[c] ?? ""}
                onChange={(e) =>
                  upd({
                    ...cfg,
                    [configKey]: { ...colMap, [c]: e.target.value },
                  })
                }
              >
                <option value="">—</option>
                <option value="int">int</option>
                <option value="str">str</option>
                <option value="object">object</option>
                <option value="float">float</option>
                <option value="bool">bool</option>
                <option value="datetime">datetime</option>
              </select>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // ── ReferentialIntegrityEval ────────────────────────────────────────────────
  if (method === "ReferentialIntegrityEval") {
    return (
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="text-xs text-slate-500 block mb-1">Column</label>
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">
            Reference table
          </label>
          <input
            className="input-base w-full"
            placeholder="users"
            value={(cfg.reference_df as string) ?? ""}
            onChange={(e) => upd({ ...cfg, reference_df: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-slate-500 block mb-1">
            Reference column
          </label>
          <input
            className="input-base w-full"
            placeholder="id"
            value={(cfg.reference_column as string) ?? ""}
            onChange={(e) =>
              upd({ ...cfg, reference_column: e.target.value })
            }
          />
        </div>
      </div>
    );
  }

  // ── UnicodeValidationEval ───────────────────────────────────────────────────
  if (method === "UnicodeValidationEval") {
    return (
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Columns to validate for unicode
        </label>
        <div className="flex flex-wrap gap-3">
          {cols.map((c) => (
            <label key={c} className="flex items-center gap-1.5 text-sm cursor-pointer">
              <input
                type="checkbox"
                className="accent-teal-600"
                checked={Array.isArray(cfg.columns) && (cfg.columns as string[]).includes(c)}
                onChange={(e) => {
                  const prev: string[] = Array.isArray(cfg.columns)
                    ? (cfg.columns as string[])
                    : [];
                  const next = e.target.checked
                    ? [...prev, c]
                    : prev.filter((x) => x !== c);
                  upd({ ...cfg, columns: next });
                }}
              />
              {c}
            </label>
          ))}
        </div>
      </div>
    );
  }

  // ── CustomEval ──────────────────────────────────────────────────────────────
  if (method === "CustomEval") {
    const scope = (cfg._scope as string) ?? "column";
    const TEMPLATES = [
      "lambda x: x >= 0",
      "lambda x: x is not None",
      "lambda x: 0 <= x <= 120",
      "lambda row: row['age'] >= 18 and row['country'] == 'US'",
    ];

    return (
      <div className="space-y-3">
        {/* Scope */}
        <div className="flex gap-4">
          {["column", "row"].map((s) => (
            <label
              key={s}
              className="flex items-center gap-1.5 text-sm cursor-pointer"
            >
              <input
                type="radio"
                className="accent-teal-600"
                checked={scope === s}
                onChange={() => upd({ ...cfg, _scope: s })}
              />
              {s}-level
            </label>
          ))}
        </div>

        {/* Column selector (column-level only) */}
        {scope === "column" && (
          <select
            className="input-base w-full"
            value={(cfg.column as string) ?? ""}
            onChange={(e) => upd({ ...cfg, column: e.target.value })}
          >
            <option value="">Select column…</option>
            {cols.map((c) => <option key={c}>{c}</option>)}
          </select>
        )}

        {/* Preset templates */}
        <div>
          <p className="text-xs text-slate-500 mb-1">Preset templates</p>
          <div className="flex flex-wrap gap-2">
            {TEMPLATES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => upd({ ...cfg, func: t })}
                className="px-2 py-1 bg-slate-100 text-xs rounded border border-slate-200
                           hover:bg-teal-50 hover:border-teal-300 font-mono transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Monaco editor */}
        <div className="border border-slate-200 rounded-md overflow-hidden">
          <Editor
            height="80px"
            defaultLanguage="python"
            value={(cfg.func as string) ?? ""}
            options={{
              minimap: { enabled: false },
              lineNumbers: "off",
              fontSize: 13,
              scrollBeyondLastLine: false,
            }}
            onChange={(v) => upd({ ...cfg, func: v ?? "" })}
          />
        </div>

        {/* Validate button */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={async () => {
              const result = await validateLambda((cfg.func as string) ?? "");
              setLambdaStatus(result);
            }}
            className="btn-secondary text-xs py-1.5"
          >
            Validate Syntax
          </button>
          {lambdaStatus && (
            <span
              className={`text-xs font-medium ${
                lambdaStatus.valid ? "text-green-600" : "text-red-600"
              }`}
            >
              {lambdaStatus.valid ? "✓ Syntax OK" : `✗ ${lambdaStatus.error}`}
            </span>
          )}
        </div>
      </div>
    );
  }

  // ── DateRangeEval ───────────────────────────────────────────────────────────
  if (method === "DateRangeEval") {
    return (
      <div className="space-y-3">
        <label className="text-sm font-medium text-slate-700 block mb-1">
          Column containing dates
        </label>
        <select
          className="input-base w-full"
          value={(cfg.column as string) ?? ""}
          onChange={(e) => upd({ ...cfg, column: e.target.value })}
        >
          <option value="">Select column…</option>
          {cols.map((c) => <option key={c}>{c}</option>)}
        </select>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-500 block mb-1">From date</label>
            <div className="relative">
              <span
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 cursor-pointer z-10"
                onClick={() => minDateRef.current?.showPicker()}
              >📅</span>
              <input
                type="text"
                inputMode="numeric"
                placeholder="dd-mm-yyyy"
                className="input-base w-full pl-8 cursor-text"
                value={(cfg.min_date as string) ? formatToDisplay(cfg.min_date as string) : ""}
                onChange={(e) => {
                  const raw = e.target.value.replace(/[^\d]/g, "");
                  let display = raw;
                  if (raw.length > 2) display = raw.slice(0, 2) + "-" + raw.slice(2);
                  if (raw.length > 4) display = raw.slice(0, 2) + "-" + raw.slice(2, 4) + "-" + raw.slice(4, 8);
                  e.target.value = display;
                  if (raw.length === 8) {
                    const iso = `${raw.slice(4, 8)}-${raw.slice(2, 4)}-${raw.slice(0, 2)}`;
                    upd({ ...cfg, min_date: iso });
                  } else if (raw.length === 0) {
                    upd({ ...cfg, min_date: "" });
                  }
                }}
              />
              <input
                ref={minDateRef}
                type="date"
                className="absolute inset-0 opacity-0 pointer-events-none"
                tabIndex={-1}
                value={(cfg.min_date as string) ?? ""}
                onChange={(e) => upd({ ...cfg, min_date: e.target.value })}
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-500 block mb-1">To date</label>
            <div className="relative">
              <span
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 cursor-pointer z-10"
                onClick={() => maxDateRef.current?.showPicker()}
              >📅</span>
              <input
                type="text"
                inputMode="numeric"
                placeholder="dd-mm-yyyy"
                className="input-base w-full pl-8 cursor-text"
                value={(cfg.max_date as string) ? formatToDisplay(cfg.max_date as string) : ""}
                onChange={(e) => {
                  const raw = e.target.value.replace(/[^\d]/g, "");
                  let display = raw;
                  if (raw.length > 2) display = raw.slice(0, 2) + "-" + raw.slice(2);
                  if (raw.length > 4) display = raw.slice(0, 2) + "-" + raw.slice(2, 4) + "-" + raw.slice(4, 8);
                  e.target.value = display;
                  if (raw.length === 8) {
                    const iso = `${raw.slice(4, 8)}-${raw.slice(2, 4)}-${raw.slice(0, 2)}`;
                    upd({ ...cfg, max_date: iso });
                  } else if (raw.length === 0) {
                    upd({ ...cfg, max_date: "" });
                  }
                }}
              />
              <input
                ref={maxDateRef}
                type="date"
                className="absolute inset-0 opacity-0 pointer-events-none"
                tabIndex={-1}
                value={(cfg.max_date as string) ?? ""}
                onChange={(e) => upd({ ...cfg, max_date: e.target.value })}
              />
            </div>
          </div>
        </div>
        <p className="text-xs text-slate-400">
          Rows with dates outside this range (or unparseable dates) will be flagged.
        </p>
      </div>
    );
  }

  // ── MojibakeEval ────────────────────────────────────────────────────────────
  if (method === "MojibakeEval") {
    return (
      <div>
        <label className="text-sm font-medium text-slate-700 block mb-2">
          Column to check for mojibake
        </label>
        <select
          className="input-base w-full"
          value={(cfg.column as string) ?? ""}
          onChange={(e) => upd({ ...cfg, column: e.target.value })}
        >
          <option value="">Select column…</option>
          {cols.map((c) => <option key={c}>{c}</option>)}
        </select>
      </div>
    );
  }

  return (
    <p className="text-sm text-slate-400 italic">
      Select a DQ method to configure it.
    </p>
  );
}
