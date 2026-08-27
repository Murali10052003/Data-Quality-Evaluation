import { useDeferredValue, useState } from "react";

type ValidationRule = {
  method: string;
  name: string;
  category: string;
  description: string;
  validation: string;
  config: string[];
  result: string;
};

const RULES: ValidationRule[] = [
  {
    method: "DupEval",
    name: "Duplicate rows",
    category: "Integrity",
    description: "Finds repeated records using one or more selected columns as the comparison key.",
    validation: "Passes when no key combination occurs more than once. Every occurrence of a duplicate is reported.",
    config: ["columns: string[]"],
    result: "Advanced results include the duplicate rows.",
  },
  {
    method: "EmptyEval",
    name: "Empty and null values",
    category: "Completeness",
    description: "Checks selected columns for null, NaN, or blank-string values.",
    validation: "Passes when every selected field contains a value on every row.",
    config: ["columns: string[]"],
    result: "Advanced results include rows containing at least one empty value.",
  },
  {
    method: "UniqueEval",
    name: "Column uniqueness",
    category: "Integrity",
    description: "Ensures the values in a selected column can uniquely identify each row.",
    validation: "Passes when the selected value occurs only once. All rows sharing a duplicate value are reported.",
    config: ["columns: [string]"],
    result: "Advanced results include every row with a duplicated value.",
  },
  {
    method: "DtypeEval",
    name: "Data type",
    category: "Schema",
    description: "Checks whether column values can be interpreted as their configured data types.",
    validation: "Passes when values in every configured column convert to the expected type without coercion failures.",
    config: ["columns: { column: type }"],
    result: "Advanced results include rows with type conversion failures.",
  },
  {
    method: "StringFormatEval",
    name: "String format",
    category: "Validity",
    description: "Validates text against a regular expression, such as an email, UUID, date, or business identifier.",
    validation: "Passes when every value matches the pattern. Use ^ and $ anchors when the complete value must match.",
    config: ["column: string", "pattern: regex"],
    result: "Advanced results include rows whose value does not match.",
  },
  {
    method: "RangeEval",
    name: "Numeric range",
    category: "Statistics",
    description: "Checks that numeric values remain within inclusive lower and upper boundaries.",
    validation: "Passes when every value is greater than or equal to min and less than or equal to max.",
    config: ["column: string", "min: number", "max: number"],
    result: "Advanced results include out-of-range rows.",
  },
  {
    method: "CategoricalValuesEval",
    name: "Allowed categories",
    category: "Validity",
    description: "Restricts a column to an approved set of categorical or enumerated values.",
    validation: "Passes when every value appears in the allowed values list.",
    config: ["column: string", "allowed_values: value[]"],
    result: "Advanced results include rows containing unapproved values.",
  },
  {
    method: "StatisticalDistributionEval",
    name: "Statistical distribution",
    category: "Statistics",
    description: "Monitors numeric feature drift against reference mean and standard deviation, or checks label balance.",
    validation: "Feature drift compares current statistics with reference statistics and tolerance. Label balance checks class proportions.",
    config: ["column: string", "mode: feature_drift | label_balance", "reference_stats?: { mean, std }", "tolerance?: number"],
    result: "Returns current distribution or drift measurements and the pass decision.",
  },
  {
    method: "DataFreshnessEval",
    name: "Data freshness",
    category: "Timeliness",
    description: "Checks whether a dataset contains a recent record using the latest timestamp in a column.",
    validation: "Passes when the maximum timestamp is newer than the configured age threshold.",
    config: ["column: string", "freshness_threshold: duration"],
    result: "Returns the latest and cutoff timestamps; this is a dataset-level summary.",
  },
  {
    method: "ReferentialIntegrityEval",
    name: "Referential integrity",
    category: "Integrity",
    description: "Verifies that each foreign-key value exists in a selected column of a reference dataset.",
    validation: "Passes when every source value has a matching reference value.",
    config: ["column: string", "reference_df: dataset", "reference_column: string"],
    result: "Advanced results include source rows with missing references.",
  },
  {
    method: "RowCountEval",
    name: "Row count",
    category: "Volume",
    description: "Guards against unexpectedly small or large datasets by checking the total number of rows.",
    validation: "Passes when the row count is within the configured bounds. At least one bound is required.",
    config: ["min?: integer", "max?: integer"],
    result: "Returns the observed row count and configured bounds as a dataset-level summary.",
  },
  {
    method: "CustomEval",
    name: "Custom function",
    category: "Custom",
    description: "Applies user-defined Python validation logic to each value in a column or to each complete row.",
    validation: "Passes when the function returns true for every evaluated value or row.",
    config: ["func: callable", "column?: string"],
    result: "Advanced results include rows for which the custom function returns false.",
  },
  {
    method: "SchemaValidationEval",
    name: "Schema validation",
    category: "Schema",
    description: "Confirms that required columns exist and conform to their expected data types.",
    validation: "Passes when no configured column is missing and every configured type matches.",
    config: ["expected_schema: { column: type }"],
    result: "Reports missing columns and type mismatches.",
  },
  {
    method: "UnicodeValidationEval",
    name: "Unicode integrity",
    category: "Integrity",
    description: "Compares source and target text after Unicode normalization to detect corruption, replacement characters, and mojibake.",
    validation: "Passes when joined source and target values have matching normalized hashes and no encoding-corruption markers.",
    config: ["key_column: string", "columns: string[]", "target_df: dataset", "target_columns?: string[]", "normalization_form?: NFC | NFD | NFKC | NFKD"],
    result: "Advanced results identify mismatched joined rows without exposing raw values in hashes.",
  },
  {
    method: "DateRangeEval",
    name: "Date range",
    category: "Validity",
    description: "Verifies that date or datetime values in a column fall within a specified min/max date range.",
    validation: "Passes when every non-null date value is between the configured minimum and maximum dates inclusive.",
    config: ["column: string", "min_date: string", "max_date: string", "date_format?: string (default %Y-%m-%d)"],
    result: "Advanced results include rows with dates outside the range or unparseable values.",
  },
  {
    method: "MojibakeEval",
    name: "Mojibake detection",
    category: "Integrity",
    description: "Detects mojibake (garbled text from encoding mismatches) such as UTF-8 bytes misinterpreted as Latin-1 and Unicode replacement characters.",
    validation: "Passes when no cell in the column contains mojibake patterns or the Unicode replacement character U+FFFD.",
    config: ["column: string"],
    result: "Advanced results include rows containing detected mojibake characters.",
  },
];

const CATEGORIES = ["All", ...Array.from(new Set(RULES.map((rule) => rule.category)))];

const CAT_COLOR: Record<string, string> = {
  Integrity: "#F97316",
  Completeness: "#3B82F6",
  Schema: "#06B6D4",
  Validity: "#10B981",
  Statistics: "#F59E0B",
  Timeliness: "#FDE047",
  Volume: "#B08968",
  Custom: "#64748B",
};

export default function ValidationCatalog() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("All");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const visibleRules = RULES.filter((rule) => {
    const matchesCategory = category === "All" || rule.category === category;
    const searchable = `${rule.method} ${rule.name} ${rule.description} ${rule.config.join(" ")}`.toLowerCase();
    return matchesCategory && searchable.includes(deferredQuery);
  });

  return (
    <div className="space-y-5 w-full" style={{ animation: "fadein .4s ease" }}>
      {/* Header */}
      <div>
        <div className="text-xs mb-1.5" style={{ color: "var(--t3)" }}>Home / Reference / Validation Catalog</div>
        <h1
          className="text-[30px] font-extrabold text-white"
          style={{ letterSpacing: "-.5px" }}
        >
          Validation Catalog
        </h1>
        <p className="text-[13px] mt-2" style={{ color: "var(--t2)" }}>
          {RULES.length} methods · {CATEGORIES.length - 1} categories · comprehensive data quality reference
        </p>
      </div>

      {/* Search */}
      <div className="relative" style={{ margin: "20px 0" }}>
        <span className="absolute text-lg" style={{ left: 16, top: 15 }}>🔍</span>
        <input
          type="search"
          className="w-full text-[15px] text-white"
          style={{
            height: 52,
            paddingLeft: 44,
            background: "rgba(255,255,255,.04)",
            border: "1px solid var(--border)",
            borderRadius: 14,
            outline: "none",
            fontFamily: "inherit",
          }}
          placeholder="Search validation methods..."
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {/* Category pills */}
      <div className="flex flex-wrap gap-2.5" role="group" aria-label="Filter by category">
        {CATEGORIES.map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={category === item}
            onClick={() => setCategory(item)}
            className="text-[13px] font-medium cursor-pointer transition-all duration-200"
            style={
              category === item
                ? {
                    padding: "8px 16px",
                    borderRadius: 999,
                    background: "var(--grad)",
                    color: "#fff",
                    border: "none",
                    boxShadow: "0 4px 14px rgba(99,102,241,.4)",
                  }
                : {
                    padding: "8px 16px",
                    borderRadius: 999,
                    background: "rgba(255,255,255,.04)",
                    border: "1px solid var(--border)",
                    color: "var(--t2)",
                  }
            }
          >
            {item}
          </button>
        ))}
      </div>

      {/* Cards grid */}
      {visibleRules.length > 0 ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {visibleRules.map((rule) => (
            <div
              key={rule.method}
              className="glass transition-all duration-300 cursor-default"
              style={{ padding: 20 }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-6px)";
                e.currentTarget.style.borderColor = "var(--blue)";
                e.currentTarget.style.boxShadow = "0 16px 40px -12px rgba(59,130,246,.4)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "";
                e.currentTarget.style.borderColor = "";
                e.currentTarget.style.boxShadow = "";
              }}
            >
              <div className="flex justify-between items-start gap-2.5">
                <div>
                  <div className="text-[17px] font-bold text-white">{rule.name}</div>
                  <div className="font-mono text-xs mt-0.5" style={{ color: "var(--cyan)" }}>
                    {rule.method}
                  </div>
                </div>
                <span
                  className="text-[11px] font-semibold text-white py-1 px-2.5 rounded-lg whitespace-nowrap"
                  style={{ background: CAT_COLOR[rule.category] ?? "#64748B" }}
                >
                  {rule.category}
                </span>
              </div>

              <p className="text-[13px] leading-relaxed mt-3" style={{ color: "var(--t2)" }}>
                {rule.description}
              </p>

              <div className="text-xs mt-2.5" style={{ color: "var(--t3)" }}>
                Pass condition: <b style={{ color: "var(--success)" }}>{rule.validation}</b>
              </div>

              <div className="flex flex-wrap gap-2 mt-3">
                {rule.config.map((field) => (
                  <span
                    key={field}
                    className="font-mono text-xs py-1 px-2.5 rounded-lg"
                    style={{
                      background: "rgba(255,255,255,.04)",
                      border: "1px solid var(--border)",
                      color: "#a5b4fc",
                    }}
                  >
                    {field}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div
          className="text-center text-[13px] py-14"
          style={{
            border: "1.5px dashed rgba(255,255,255,.14)",
            borderRadius: 12,
            color: "var(--t3)",
          }}
        >
          <p className="font-medium text-white">No validations match this filter.</p>
          <button
            type="button"
            className="text-sm mt-2"
            style={{ color: "var(--blue)", background: "none", border: "none", cursor: "pointer" }}
            onClick={() => { setQuery(""); setCategory("All"); }}
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}