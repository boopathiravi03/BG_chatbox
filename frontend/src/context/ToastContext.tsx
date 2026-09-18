import React, { createContext, useContext, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

export type ToastType = "success" | "error" | "info";

export interface ToastItem {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, type, message }]);

      setTimeout(() => {
        removeToast(id);
      }, 4000);
    },
    [removeToast],
  );

  const success = useCallback(
    (msg: string) => showToast(msg, "success"),
    [showToast],
  );
  const error = useCallback(
    (msg: string) => showToast(msg, "error"),
    [showToast],
  );
  const info = useCallback(
    (msg: string) => showToast(msg, "info"),
    [showToast],
  );

  return (
    <ToastContext.Provider value={{ showToast, success, error, info }}>
      {children}
      <div className="fixed bottom-5 right-5 z-[10000] flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4">
        <AnimatePresence>
          {toasts.map((t) => (
            <motion.div
              key={t.id}
              initial={{ opacity: 0, y: 16, scale: 0.94 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.94, y: 10 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="pointer-events-auto flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl bg-[#141417]/95 border border-white/10 shadow-xl shadow-black/50 backdrop-blur-md text-xs font-medium text-zinc-200"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {t.type === "success" && (
                  <CheckCircle2
                    size={16}
                    className="text-emerald-400 shrink-0"
                  />
                )}
                {t.type === "error" && (
                  <AlertCircle size={16} className="text-rose-400 shrink-0" />
                )}
                {t.type === "info" && (
                  <Info size={16} className="text-indigo-400 shrink-0" />
                )}
                <span className="truncate">{t.message}</span>
              </div>
              <button
                onClick={() => removeToast(t.id)}
                className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-white/5 transition-colors shrink-0"
              >
                <X size={13} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    return {
      showToast: (m: string) => console.log(m),
      success: (m: string) => console.log(m),
      error: (m: string) => console.error(m),
      info: (m: string) => console.log(m),
    };
  }
  return context;
}
