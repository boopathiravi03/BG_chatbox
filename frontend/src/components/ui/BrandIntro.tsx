import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Sparkles } from "lucide-react";

export default function BrandIntro({
  onComplete,
}: {
  onComplete?: () => void;
}) {
  const [show, setShow] = useState(false);

  useEffect(() => {
    // Check if already seen in current browser session
    const seen = sessionStorage.getItem("bgai_intro_seen");
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (seen || prefersReducedMotion) {
      onComplete?.();
      return;
    }

    setShow(true);

    const timer = setTimeout(() => {
      handleDismiss();
    }, 1800);

    return () => clearTimeout(timer);
  }, []);

  const handleDismiss = () => {
    sessionStorage.setItem("bgai_intro_seen", "true");
    setShow(false);
    onComplete?.();
  };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          key="brand-intro"
          initial={{ opacity: 1 }}
          exit={{
            opacity: 0,
            transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] },
          }}
          className="fixed inset-0 z-[10000] flex flex-col items-center justify-center bg-[#09090b] text-white select-none"
        >
          {/* Subtle central radial highlight */}
          <div
            className="absolute inset-0 pointer-events-none opacity-40"
            style={{
              backgroundImage:
                "radial-gradient(circle at 50% 50%, rgba(99, 102, 241, 0.15), transparent 60%)",
            }}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            className="relative flex flex-col items-center text-center z-10 px-6"
          >
            <div className="relative mb-5 flex items-center justify-center h-14 w-14 rounded-2xl bg-white/[0.04] border border-white/10 shadow-2xl shadow-indigo-500/10">
              <Database size={24} className="text-indigo-400" />
              <Sparkles
                size={12}
                className="absolute top-2 right-2 text-indigo-300"
              />
            </div>

            <motion.h1
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.15, duration: 0.4 }}
              className="text-2xl font-semibold tracking-tight text-zinc-100 flex items-center gap-2"
            >
              BG <span className="text-indigo-400">AI</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.3, duration: 0.4 }}
              className="mt-2 text-xs text-zinc-400 font-normal tracking-wide"
            >
              Your data. Your questions. Intelligent answers.
            </motion.p>
          </motion.div>

          <button
            onClick={handleDismiss}
            className="absolute bottom-8 text-[11px] text-zinc-500 hover:text-zinc-300 tracking-wider uppercase transition-colors"
          >
            Press any key or click to skip
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
