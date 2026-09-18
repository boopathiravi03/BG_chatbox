import { motion } from "framer-motion";
import React from "react";

interface StatusLoaderProps {
  statusText?: string;
  subtext?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export default function StatusLoader({
  statusText = "Processing request...",
  subtext,
  size = "md",
  className = "",
}: StatusLoaderProps) {
  const sizeMap = {
    sm: "h-4 w-4",
    md: "h-6 w-6",
    lg: "h-8 w-8",
  };

  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <div className={`relative ${sizeMap[size]}`}>
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-indigo-500/20"
          animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.2, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-transparent border-t-indigo-400 border-r-indigo-400"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
        />
      </div>
      <div className="flex flex-col">
        <motion.span
          key={statusText}
          initial={{ opacity: 0, y: 3 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-sm font-medium text-zinc-200"
        >
          {statusText}
        </motion.span>
        {subtext && <span className="text-xs text-zinc-500">{subtext}</span>}
      </div>
    </div>
  );
}
