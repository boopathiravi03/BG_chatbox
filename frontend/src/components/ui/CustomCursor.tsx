import { useEffect, useState, useRef } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";

export default function CustomCursor() {
  const [hovered, setHovered] = useState(false);
  const [visible, setVisible] = useState(false);
  const cursorX = useMotionValue(-100);
  const cursorY = useMotionValue(-100);

  const springConfig = { damping: 28, stiffness: 350, mass: 0.1 };
  const ringX = useSpring(cursorX, springConfig);
  const ringY = useSpring(cursorY, springConfig);

  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const isTouch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
    const isFinePointer = window.matchMedia("(pointer: fine)").matches;

    if (prefersReducedMotion || isTouch || !isFinePointer) {
      return;
    }

    document.body.classList.add("custom-cursor-enabled");

    const handlePointerMove = (e: PointerEvent) => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(() => {
        cursorX.set(e.clientX);
        cursorY.set(e.clientY);
        if (!visible) setVisible(true);
      });
    };

    const handlePointerLeave = () => setVisible(false);
    const handlePointerEnter = () => setVisible(true);

    const handleTargetEnter = (e: MouseEvent) => {
      const target = (e.target as HTMLElement)?.closest?.(
        "a, button, [role='button'], input, textarea, select, [data-cursor-hover], tr, .clickable",
      );
      if (target) {
        setHovered(true);
      }
    };

    const handleTargetLeave = (e: MouseEvent) => {
      const target = (e.target as HTMLElement)?.closest?.(
        "a, button, [role='button'], input, textarea, select, [data-cursor-hover], tr, .clickable",
      );
      if (target) {
        setHovered(false);
      }
    };

    window.addEventListener("pointermove", handlePointerMove, {
      passive: true,
    });
    document.addEventListener("mouseleave", handlePointerLeave);
    document.addEventListener("mouseenter", handlePointerEnter);
    document.addEventListener("mouseover", handleTargetEnter);
    document.addEventListener("mouseout", handleTargetLeave);

    return () => {
      document.body.classList.remove("custom-cursor-enabled");
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      window.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("mouseleave", handlePointerLeave);
      document.removeEventListener("mouseenter", handlePointerEnter);
      document.removeEventListener("mouseover", handleTargetEnter);
      document.removeEventListener("mouseout", handleTargetLeave);
    };
  }, [visible, cursorX, cursorY]);

  // Don't render anything if on server or touch device
  if (typeof window !== "undefined") {
    const isTouch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
    const isFinePointer = window.matchMedia?.("(pointer: fine)").matches;
    if (isTouch || !isFinePointer) return null;
  }

  return (
    <div className="pointer-events-none fixed inset-0 z-[9998] overflow-hidden">
      <motion.div
        className={`cursor-ring${hovered ? " hover" : ""}`}
        style={{
          x: ringX,
          y: ringY,
          opacity: visible ? 1 : 0,
        }}
      />
    </div>
  );
}
