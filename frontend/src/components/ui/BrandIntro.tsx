import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play } from "lucide-react";

interface BrandIntroProps {
  onComplete?: () => void;
}

export default function BrandIntro({ onComplete }: BrandIntroProps) {
  // Always play on every page load unless reduced motion is requested
  const [show, setShow] = useState<boolean>(() => {
    try {
      const prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      return !prefersReducedMotion;
    } catch {
      return true;
    }
  });

  const [autoplayBlocked, setAutoplayBlocked] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const safetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dismissedRef = useRef<boolean>(false);

  const handleDismiss = useCallback(() => {
    if (dismissedRef.current) return;
    dismissedRef.current = true;

    if (safetyTimerRef.current) {
      clearTimeout(safetyTimerRef.current);
      safetyTimerRef.current = null;
    }

    setShow(false);
    onComplete?.();
  }, [onComplete]);

  useEffect(() => {
    if (!show) {
      onComplete?.();
      return;
    }

    // Keyboard shortcuts (Escape, Space, Enter) to skip immediately
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" || e.key === " " || e.key === "Enter") {
        handleDismiss();
      }
    };
    window.addEventListener("keydown", handleKeyDown);

    // Safety fallback: if video doesn't end within 6.5s, dismiss gracefully
    safetyTimerRef.current = setTimeout(() => {
      handleDismiss();
    }, 6500);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (safetyTimerRef.current) {
        clearTimeout(safetyTimerRef.current);
      }
    };
  }, [show, handleDismiss, onComplete]);

  // Attempt autoplay immediately upon mount
  useEffect(() => {
    if (!show || !videoRef.current) return;

    const video = videoRef.current;
    video.muted = true;
    video.playsInline = true;
    video.currentTime = 0;

    const playPromise = video.play();
    if (playPromise !== undefined) {
      playPromise
        .then(() => {
          setAutoplayBlocked(false);
        })
        .catch((err) => {
          console.warn("Autoplay restricted by browser policy:", err);
          setAutoplayBlocked(true);
        });
    }
  }, [show]);

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const duration = videoRef.current.duration || 5.04;
    const current = videoRef.current.currentTime;
    setProgress(Math.min(100, (current / duration) * 100));
  };

  const handleManualPlay = () => {
    if (videoRef.current) {
      videoRef.current
        .play()
        .then(() => setAutoplayBlocked(false))
        .catch(() => handleDismiss());
    } else {
      handleDismiss();
    }
  };

  return (
    <AnimatePresence mode="wait">
      {show && (
        <motion.div
          key="brand-intro-fullscreen-overlay"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
          exit={{
            opacity: 0,
            transition: {
              duration: 0.55,
              ease: [0.16, 1, 0.3, 1],
            },
          }}
          className="fixed inset-0 z-[99999] w-screen h-screen bg-[#545c63] flex items-center justify-center select-none overflow-hidden"
          style={{ willChange: "opacity" }}
        >
          {/* True Fullscreen Video Player */}
          <div className="relative w-full h-full flex items-center justify-center overflow-hidden">
            <video
              ref={videoRef}
              playsInline
              muted
              autoPlay
              preload="auto"
              onTimeUpdate={handleTimeUpdate}
              onEnded={handleDismiss}
              onError={() => {
                console.warn("Video failed to load, bypassing intro.");
                handleDismiss();
              }}
              className="w-full h-full object-cover"
            >
              <source src="/bg-ai-intro.mp4" type="video/mp4" />
              <source src="/intro.mp4" type="video/mp4" />
            </video>

            {/* Autoplay Blocked Fallback Modal */}
            {autoplayBlocked && (
              <div
                onClick={handleManualPlay}
                className="absolute inset-0 bg-black/75 backdrop-blur-md flex flex-col items-center justify-center gap-4 p-6 cursor-pointer z-40"
              >
                <div className="w-16 h-16 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center shadow-xl shadow-indigo-600/50 transition-transform hover:scale-105">
                  <Play size={28} className="ml-1" />
                </div>
                <p className="text-base font-bold text-white tracking-wide">
                  Click Anywhere to Play Intro
                </p>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDismiss();
                  }}
                  className="text-xs font-medium text-zinc-300 hover:text-white underline underline-offset-4 mt-2"
                >
                  Or skip directly to application →
                </button>
              </div>
            )}

            {/* Bottom-Right Skip Intro Button */}
            <div className="absolute bottom-6 right-6 z-30">
              <button
                onClick={handleDismiss}
                className="px-4 py-2 rounded-full text-xs font-mono font-medium tracking-wider text-white/90 hover:text-white bg-black/40 hover:bg-black/70 border border-white/15 backdrop-blur-md transition-all cursor-pointer flex items-center gap-2 shadow-lg"
                title="Skip intro animation (Esc)"
              >
                <span>Skip Intro</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 font-mono text-white/70">
                  Esc
                </span>
              </button>
            </div>

            {/* Full-Width Bottom Linear Progress Bar */}
            <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-white/10 z-30 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-indigo-500 via-indigo-400 to-white transition-all duration-100 ease-linear"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
