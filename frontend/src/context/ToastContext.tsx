import { createContext, useContext, useState, useCallback, ReactNode } from "react";

type ToastType = "success" | "error" | "info";

interface Toast {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} });

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const toast = useCallback((message: string, type: ToastType = "success") => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3500);
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {/* Toast container */}
      <div className="fixed top-5 right-5 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="pointer-events-auto rounded-xl px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-md"
            style={{
              animation: "fadein .3s ease, fadeout .3s ease 3.2s forwards",
              background:
                t.type === "success"
                  ? "rgba(5,150,105,.15)"
                  : t.type === "error"
                  ? "rgba(220,38,38,.15)"
                  : "rgba(59,130,246,.15)",
              border: `1px solid ${
                t.type === "success"
                  ? "rgba(5,150,105,.4)"
                  : t.type === "error"
                  ? "rgba(220,38,38,.4)"
                  : "rgba(59,130,246,.4)"
              }`,
              color:
                t.type === "success"
                  ? "#6ee7b7"
                  : t.type === "error"
                  ? "#fca5a5"
                  : "#93c5fd",
              minWidth: 220,
              maxWidth: 360,
            }}
          >
            <span className="mr-2">
              {t.type === "success" ? "✓" : t.type === "error" ? "✗" : "ℹ"}
            </span>
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
