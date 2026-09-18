import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Sparkles } from "lucide-react";

const statusPhases = [
  "Preparing your request...",
  "Analyzing database structure...",
  "Formulating SQL & querying data...",
  "Generating your response...",
];

export default function Thinking() {
  const [phaseIndex, setPhaseIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setPhaseIndex((prev) => (prev + 1) % statusPhases.length);
    }, 2200);
    return () => clearInterval(interval);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-3.5 py-3 px-4.5 rounded-2xl bg-white/[0.03] border border-white/[0.08] max-w-sm shadow-md"
    >
      {/* Subtle pulsing AI indicator */}
      <div className="relative flex items-center justify-center w-7 h-7 rounded-xl bg-indigo-500/15 text-indigo-400">
        <Sparkles size={15} className="animate-pulse" />
      </div>

      <div className="flex-1 min-w-0">
        <AnimatePresence mode="wait">
          <motion.p
            key={statusPhases[phaseIndex]}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -3 }}
            transition={{ duration: 0.25 }}
            className="text-sm text-zinc-200 font-medium truncate"
          >
            {statusPhases[phaseIndex]}
          </motion.p>
        </AnimatePresence>
      </div>

      {/* 3 micro bouncing dots */}
      <div className="flex items-center gap-1.5">
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" />
      </div>
    </motion.div>
  );
}
