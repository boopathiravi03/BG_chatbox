import { motion } from "framer-motion";
import React from "react";

interface AnimatedListProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}

export default function AnimatedList({
  children,
  className = "",
  delay = 0.05,
}: AnimatedListProps) {
  const childArray = React.Children.toArray(children);

  return (
    <div className={className}>
      {childArray.map((child, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{
            duration: 0.25,
            delay: index * delay,
            ease: [0.25, 0.1, 0.25, 1],
          }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}
