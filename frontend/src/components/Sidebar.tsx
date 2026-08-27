import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getSchemas } from "../api/client";
import { useSidebar } from "../context/SidebarContext";
import { useTheme } from "../context/ThemeContext";

const IconDashboard = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
  </svg>
);
const IconRules = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
  </svg>
);
const IconCatalog = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
  </svg>
);
const IconRun = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="5 3 19 12 5 21 5 3"/>
  </svg>
);
const IconResults = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
);

const IconSun = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
);
const IconMoon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
);

const links = [
  { to: "/dashboard", label: "Dashboard",          icon: IconDashboard },
  { to: "/rules",     label: "Rule Manager",       icon: IconRules },
  { to: "/catalog",   label: "Validation Catalog", icon: IconCatalog },
  { to: "/run",       label: "Run Pipeline",       icon: IconRun },
  { to: "/results",   label: "Results Viewer",     icon: IconResults },
];

export default function Sidebar() {
  const { collapsed, setCollapsed, mobileOpen, setMobileOpen } = useSidebar();
  const { theme, toggleTheme } = useTheme();

  const { data: schemas, isError, isFetching } = useQuery({
    queryKey: ["connection-health"],
    queryFn: getSchemas,
    staleTime: 60_000,
    refetchInterval: 60_000,
    retry: 1,
    refetchOnWindowFocus: false,
  });

  const connected = !isError && schemas !== undefined;

  const sidebarContent = (
    <>
      {/* Brand */}
      <div className="flex items-center gap-3" style={{ padding: "6px 6px 4px" }}>
        <div
          className="flex items-center justify-center font-extrabold text-[15px] text-white shrink-0"
          style={{
            width: 40, height: 40, borderRadius: 12,
            background: "var(--grad)",
            boxShadow: "0 6px 18px rgba(99,102,241,.4)",
          }}
        >
          DQ
        </div>
        {!collapsed && (
          <div>
            <div className="font-bold text-[16px] leading-tight" style={{ color: theme === "dark" ? "#fff" : "#1E293B" }}>DQ Eval</div>
            <div className="text-[11px] mt-0.5" style={{ color: "#64748B" }}>
              Data Quality Control Center
            </div>
          </div>
        )}
      </div>

      {/* Collapse toggle */}
      <button
        className="hidden lg:flex items-center justify-center w-7 h-7 rounded-lg mt-3 mb-1 mx-auto transition-colors"
        style={{
          background: theme === "dark" ? "rgba(255,255,255,.05)" : "rgba(0,0,0,.04)",
          border: theme === "dark" ? "1px solid var(--border)" : "1px solid #E2E8F0",
          color: "var(--t2)",
          cursor: "pointer",
        }}
        onClick={() => setCollapsed(!collapsed)}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {collapsed ? (
            <><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></>
          ) : (
            <><polyline points="11 17 6 12 11 7"/><line x1="6" y1="12" x2="18" y2="12"/></>
          )}
        </svg>
      </button>

      {/* Nav */}
      <nav className="flex-1 flex flex-col gap-1 mt-1.5">
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            title={l.label}
            aria-label={l.label}
            className={({ isActive }) =>
              `flex items-center ${collapsed ? "justify-center" : "gap-3"} h-[44px] px-3 rounded-[10px] text-[14px] font-medium relative transition-all duration-200 ${
                isActive
                  ? `${theme === "dark" ? "text-white" : "text-slate-900"} font-semibold`
                  : `${theme === "dark" ? "text-[#94A3B8] hover:bg-white/5 hover:text-white" : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"}`
              }`
            }
            style={({ isActive }) =>
              isActive
                ? { background: theme === "dark"
                    ? "linear-gradient(135deg, rgba(59,130,246,.18), rgba(139,92,246,.18))"
                    : "linear-gradient(135deg, rgba(59,130,246,.08), rgba(139,92,246,.08))" }
                : {}
            }
            onClick={() => setMobileOpen(false)}
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span
                    className="absolute left-0 top-[9px] bottom-[9px] w-[3px] rounded-[3px]"
                    style={{ background: "var(--grad)" }}
                  />
                )}
                <span className="w-5 flex items-center justify-center shrink-0"><l.icon /></span>
                {!collapsed && <span>{l.label}</span>}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Theme toggle */}
      <button
        className={`flex items-center ${collapsed ? "justify-center" : "gap-2.5"} w-full h-[38px] px-3 rounded-[10px] text-[13px] font-medium transition-colors mb-2`}
        style={{
          background: theme === "dark" ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.03)",
          border: theme === "dark" ? "1px solid var(--border)" : "1px solid #E2E8F0",
          color: theme === "dark" ? "var(--t2)" : "#475569",
          cursor: "pointer",
        }}
        onClick={toggleTheme}
        title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      >
        {theme === "dark" ? <IconSun /> : <IconMoon />}
        {!collapsed && <span>{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
      </button>

      {/* Footer */}
      <div style={{ borderTop: theme === "dark" ? "1px solid var(--border)" : "1px solid #E2E8F0", paddingTop: 14, marginTop: 8 }}>
        <div className={`flex items-center gap-2 text-[13px] font-semibold ${collapsed ? "justify-center" : ""}`} style={{ color: "var(--success)" }}>
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{
              background: isFetching
                ? "#F59E0B"
                : connected ? "var(--success)" : "var(--failed)",
              animation: connected && !isFetching ? "pulse-glow 2s infinite" : undefined,
            }}
          />
          {!collapsed && (
            isFetching ? (
              <span style={{ color: "#F59E0B" }}>Checking…</span>
            ) : connected ? (
              "Connected"
            ) : (
              <span style={{ color: "var(--failed)" }}>Disconnected</span>
            )
          )}
        </div>
        {!collapsed && (
          <>
            <div className="text-[11px] mt-[5px] pl-4" style={{ color: "#475569" }}>
              {connected && schemas?.[0] ? `schema: ${schemas[0]} · ` : ""}
              Azure PostgreSQL · v1.0
            </div>
            {isError && (
              <div className="text-[11px] pl-4 mt-1" style={{ color: "var(--failed)" }}>Check backend</div>
            )}
          </>
        )}
      </div>
    </>
  );

  return (
    <>
      {/* Mobile hamburger button */}
      <button
        className="lg:hidden fixed top-4 left-4 z-[60] flex items-center justify-center w-10 h-10 rounded-xl"
        style={{ background: "rgba(15,23,42,.9)", border: "1px solid var(--border)", color: "#fff", cursor: "pointer" }}
        onClick={() => setMobileOpen(!mobileOpen)}
        aria-label="Toggle menu"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          {mobileOpen ? (
            <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>
          ) : (
            <><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></>
          )}
        </svg>
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-[49] bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          h-screen flex flex-col shrink-0 transition-all duration-300
          fixed lg:relative z-[50]
          ${mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"}
        `}
        style={{
          width: collapsed ? 72 : 260,
          background: theme === "dark"
            ? "linear-gradient(180deg, #0F172A, #020617)"
            : "linear-gradient(180deg, #FFFFFF, #F1F5F9)",
          borderRight: theme === "dark" ? "1px solid var(--border)" : "1px solid #E2E8F0",
          padding: collapsed ? "20px 8px" : "20px 14px",
        }}
      >
        {sidebarContent}
      </aside>
    </>
  );
}

