import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Unplug,
  AlertTriangle,
  Loader2,
  X,
  Database,
  Check,
} from "lucide-react";
import {
  modalBackdropVariants,
  modalContainerVariants,
} from "../../lib/motion";

interface DisconnectConfirmationModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => Promise<void> | void;
  dbType?: string | null;
  dbName?: string | null;
}

export default function DisconnectConfirmationModal({
  isOpen,
  onClose,
  onConfirm,
  dbType,
  dbName,
}: DisconnectConfirmationModalProps) {
  const [disconnecting, setDisconnecting] = useState(false);
  const [disconnected, setDisconnected] = useState(false);

  const getEngineName = () => {
    switch (dbType) {
      case "sqlite":
        return "SQLite Database";
      case "mysql":
        return "MySQL Database";
      case "postgres":
        return "PostgreSQL Database";
      default:
        return "Active Database";
    }
  };

  const handleConfirm = async () => {
    setDisconnecting(true);
    try {
      await onConfirm();
      setDisconnected(true);
      setTimeout(() => {
        setDisconnecting(false);
        setDisconnected(false);
        onClose();
      }, 700);
    } catch (err) {
      console.error(err);
      setDisconnecting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Glass Backdrop */}
        <motion.div
          key="disconnect-backdrop"
          variants={modalBackdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={disconnecting ? undefined : onClose}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
        />

        {/* Modal Dialog */}
        <motion.div
          key="disconnect-dialog"
          variants={modalContainerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="relative w-full max-w-md rounded-2xl bg-[#121216] border border-rose-500/20 shadow-2xl shadow-rose-950/20 overflow-hidden z-10"
        >
          {/* Subtle Top Hazard Glow Gradient */}
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-rose-500 to-transparent" />

          {/* Close button */}
          {!disconnecting && (
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1.5 rounded-xl text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
              title="Cancel (Esc)"
            >
              <X size={18} />
            </button>
          )}

          <div className="p-6 sm:p-7 text-center">
            {/* Animated Warning / Disconnect Icon */}
            <div className="relative mx-auto w-16 h-16 mb-4 flex items-center justify-center">
              <motion.div
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", damping: 15 }}
                className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/25 flex items-center justify-center text-rose-400 shadow-lg shadow-rose-500/10"
              >
                {disconnected ? (
                  <Check size={28} className="text-emerald-400" />
                ) : disconnecting ? (
                  <motion.div
                    animate={{ rotate: 180 }}
                    transition={{
                      repeat: Infinity,
                      duration: 1,
                      ease: "linear",
                    }}
                  >
                    <Loader2 size={26} className="text-rose-400" />
                  </motion.div>
                ) : (
                  <motion.div
                    animate={{ rotate: [-4, 4, -4] }}
                    transition={{
                      repeat: Infinity,
                      duration: 2.5,
                      ease: "easeInOut",
                    }}
                  >
                    <Unplug size={28} className="text-rose-400" />
                  </motion.div>
                )}
              </motion.div>
            </div>

            {/* Title & Description */}
            <h3 className="text-lg font-bold text-white tracking-tight mb-2">
              {disconnected
                ? "Database Disconnected"
                : disconnecting
                  ? "Uncoupling Database Session..."
                  : "Disconnect Database?"}
            </h3>

            <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed mb-5">
              {disconnected ? (
                "Your session has returned to default workspace state."
              ) : disconnecting ? (
                "Flushing cached schemas and closing connection pools..."
              ) : (
                <>
                  Your current connection to{" "}
                  <span className="text-zinc-200 font-semibold">
                    {getEngineName()}
                  </span>{" "}
                  will be safely removed from this session. You can reconnect
                  anytime.
                </>
              )}
            </p>

            {/* Current Connection Summary Card */}
            {!disconnecting && !disconnected && (
              <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.08] flex items-center justify-between text-left mb-6">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 flex items-center justify-center shrink-0">
                    <Database size={16} />
                  </div>
                  <div className="truncate">
                    <p className="text-xs font-semibold text-zinc-200 truncate">
                      {dbName || getEngineName()}
                    </p>
                    <p className="text-[11px] text-zinc-500 font-mono">
                      Active query session
                    </p>
                  </div>
                </div>

                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 shrink-0">
                  Online
                </span>
              </div>
            )}

            {/* Safe Notice */}
            {!disconnecting && !disconnected && (
              <div className="flex items-start gap-2 text-left p-3 rounded-xl bg-amber-500/[0.06] border border-amber-500/15 mb-6 text-amber-300/90 text-[11px] leading-normal">
                <AlertTriangle
                  size={15}
                  className="text-amber-400 shrink-0 mt-0.5"
                />
                <span>
                  Note: Disconnecting only ends this AI session. Your underlying
                  files and remote database tables remain completely safe and
                  untouched.
                </span>
              </div>
            )}

            {/* Action Buttons */}
            {!disconnecting && !disconnected && (
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 py-2.5 px-4 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/10 text-xs sm:text-sm font-semibold text-zinc-300 hover:text-white transition-all cursor-pointer"
                >
                  Keep Connected
                </button>

                <button
                  type="button"
                  onClick={handleConfirm}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-rose-600 hover:bg-rose-500 text-xs sm:text-sm font-semibold text-white shadow-lg shadow-rose-900/30 transition-all cursor-pointer group"
                >
                  <Unplug
                    size={15}
                    className="group-hover:rotate-[-12deg] transition-transform"
                  />
                  <span>Disconnect</span>
                </button>
              </div>
            )}

            {(disconnecting || disconnected) && (
              <div className="py-2 flex items-center justify-center">
                <div className="w-full bg-white/[0.05] h-1.5 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-rose-500"
                    initial={{ width: "0%" }}
                    animate={{ width: disconnected ? "100%" : "85%" }}
                    transition={{ duration: 0.6 }}
                  />
                </div>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
