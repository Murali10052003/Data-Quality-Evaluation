import { BrowserRouter, Route, Routes, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import RuleManager from "./pages/RuleManager";
import RunPipeline from "./pages/RunPipeline";
import ResultsViewer from "./pages/ResultsViewer";
import ValidationCatalog from "./pages/ValidationCatalog";
import { ToastProvider } from "./context/ToastContext";
import { ThemeProvider } from "./context/ThemeContext";
import { SidebarProvider } from "./context/SidebarContext";

export default function App() {
  return (
    <ThemeProvider>
      <ToastProvider>
        <SidebarProvider>
          <BrowserRouter>
            <div className="flex h-screen overflow-hidden relative z-[1]">
              <Sidebar />
              <main className="flex-1 min-w-0 h-screen overflow-y-auto" style={{ padding: "22px 28px 60px" }}>
                <Routes>
                  <Route path="/" element={<Navigate to="/dashboard" replace />} />
                  <Route path="/dashboard" element={<Dashboard />} />
                  <Route path="/rules" element={<RuleManager />} />
                  <Route path="/catalog" element={<ValidationCatalog />} />
                  <Route path="/run" element={<RunPipeline />} />
                  <Route path="/results" element={<ResultsViewer />} />
                </Routes>
              </main>
            </div>
          </BrowserRouter>
        </SidebarProvider>
      </ToastProvider>
    </ThemeProvider>
  );
}
