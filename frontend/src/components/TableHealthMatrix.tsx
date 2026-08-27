import { useNavigate } from "react-router-dom";

const METHODS = [
  "DupEval", "EmptyEval", "UniqueEval", "DtypeEval",
  "RangeEval", "StringFormatEval", "CategoricalValuesEval",
  "StatisticalDistributionEval", "DataFreshnessEval",
  "ReferentialIntegrityEval", "RowCountEval", "CustomEval",
  "SchemaValidationEval", "UnicodeValidationEval",
  "DateRangeEval", "MojibakeEval",
];

const STATUS_DOT: Record<string, { bg: string; shadow: string; label: string }> = {
  Success: { bg: "#10B981", shadow: "0 0 8px rgba(16,185,129,.4)", label: "✓ Passed" },
  Failed:  { bg: "#EF4444", shadow: "0 0 8px rgba(239,68,68,.4)",  label: "✗ Failed" },
  Error:   { bg: "#F59E0B", shadow: "0 0 8px rgba(245,158,11,.4)", label: "⚠ Warning" },
};

interface Row {
  table_name: string;
  dqmethod: string;
  status: string;
}

export default function TableHealthMatrix({ data }: { data: Row[] }) {
  const navigate = useNavigate();
  const tables = [...new Set(data.map((r) => r.table_name))].sort();
  const index: Record<string, Record<string, string>> = {};
  data.forEach((r) => {
    if (!index[r.table_name]) index[r.table_name] = {};
    if (
      !index[r.table_name][r.dqmethod] ||
      r.status === "Failed" ||
      r.status === "Error"
    ) {
      index[r.table_name][r.dqmethod] = r.status;
    }
  });

  if (tables.length === 0) {
    return <p className="text-sm p-5" style={{ color: "var(--t2)" }}>No results yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]" style={{ borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th
              className="text-left p-3 font-semibold text-white sticky left-0 z-[3]"
              style={{ background: "var(--table-header-bg)", fontSize: 11, textTransform: "uppercase", letterSpacing: ".06em" }}
            >
              Table
            </th>
            {METHODS.map((m) => (
              <th
                key={m}
                className="p-3 text-center whitespace-nowrap sticky top-0 z-[2]"
                style={{
                  background: "var(--table-header-bg)",
                  color: "var(--t2)",
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: ".06em",
                  fontWeight: 600,
                }}
              >
                {m.replace("Eval", "")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tables.map((t) => (
            <tr
              key={t}
              className="transition-colors"
              onMouseEnter={(e) => {
                e.currentTarget.querySelectorAll("td").forEach((td) => {
                  (td as HTMLElement).style.background = "var(--table-hover-bg)";
                });
                const tname = e.currentTarget.querySelector(".tname") as HTMLElement;
                if (tname) tname.style.background = "var(--table-hover-bg)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.querySelectorAll("td").forEach((td) => {
                  (td as HTMLElement).style.background = "";
                });
                const tname = e.currentTarget.querySelector(".tname") as HTMLElement;
                if (tname) tname.style.background = "var(--table-header-bg)";
              }}
            >
              <td
                className="tname p-3 font-semibold text-white sticky left-0 z-[1] cursor-pointer hover:underline"
                style={{ background: "var(--table-header-bg)" }}
                onClick={() => navigate(`/results?table=${t}`)}
                title={`View results for ${t}`}
              >
                {t}
              </td>
              {METHODS.map((m) => {
                const s = index[t]?.[m];
                const dot = s ? STATUS_DOT[s] : null;
                const tip = `${t} · ${m} · ${dot?.label ?? "— Not Run"}`;
                return (
                  <td key={m} className="p-3 text-center">
                    <span
                      className="inline-block w-3.5 h-3.5 rounded-full cursor-pointer relative group"
                      title={tip}
                      style={{
                        background: dot?.bg ?? "#334155",
                        boxShadow: dot?.shadow ?? "none",
                      }}
                      onClick={() => navigate(`/results?table=${t}&method=${m}`)}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
