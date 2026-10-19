import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Play, Sparkles } from "lucide-react";

interface BrandIntroProps {
  onComplete?: () => void;
}

/**
 * Resolves the intro video URL safely across Web (dev/prod) and packaged Electron.
 */
function resolveVideoSrc(): string {
  if (typeof window !== "undefined" && window.electronAPI?.getIntroVideoPath) {
    try {
      const desktopPath = window.electronAPI.getIntroVideoPath();
      if (desktopPath) return desktopPath;
    } catch {
      // ignore
    }
  }

  try {
    return new URL("bg-ai-intro.mp4", window.location.href).href;
  } catch {
    return "./bg-ai-intro.mp4";
  }
}

/**
 * Resolves the logo / poster image URL safely across all execution environments.
 */
function resolveLogoSrc(): string {
  try {
    return new URL("bg-logo-wide.png", window.location.href).href;
  } catch {
    return "./bg-logo-wide.png";
  }
}

function resolveIconSrc(): string {
  try {
    return new URL("bg-logo.png", window.location.href).href;
  } catch {
    return "./bg-logo.png";
  }
}

export default function BrandIntro({ onComplete }: BrandIntroProps) {
  // Check if intro has already played during this session or if reduced motion is requested
  const [show, setShow] = useState<boolean>(() => {
    try {
      if (
        typeof window !== "undefined" &&
        sessionStorage.getItem("bgai_intro_played") === "true"
      ) {
        return false;
      }
      const prefersReducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)",
      ).matches;
      return !prefersReducedMotion;
    } catch {
      return true;
    }
  });

  const [hasError, setHasError] = useState<boolean>(false);
  const [autoplayBlocked, setAutoplayBlocked] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(0);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const safetyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fallbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dismissedRef = useRef<boolean>(false);

  const videoSrc = resolveVideoSrc();
  const logoSrc = resolveLogoSrc();
  const iconSrc = resolveIconSrc();

  const handleDismiss = useCallback(() => {
    if (dismissedRef.current) return;
    dismissedRef.current = true;

    try {
      sessionStorage.setItem("bgai_intro_played", "true");
    } catch {
      // ignore
    }

    if (safetyTimerRef.current) {
      clearTimeout(safetyTimerRef.current);
      safetyTimerRef.current = null;
    }
    if (fallbackTimerRef.current) {
      clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }

    setShow(false);
    onComplete?.();
  }, [onComplete]);

  // Graceful fallback if video fails to load or play
  const handleVideoError = useCallback(() => {
    console.warn(
      "[BG AI Intro] Video asset unavailable or playback failed. Showing static brand splash.",
    );
    setHasError(true);

    // Keep clean static logo visible for 1.8 seconds, then transition to login
    fallbackTimerRef.current = setTimeout(() => {
      handleDismiss();
    }, 1800);
  }, [handleDismiss]);

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

    // Safety fallback: if video doesn't end within 6.0s, dismiss gracefully
    safetyTimerRef.current = setTimeout(() => {
      handleDismiss();
    }, 6000);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (safetyTimerRef.current) {
        clearTimeout(safetyTimerRef.current);
      }
      if (fallbackTimerRef.current) {
        clearTimeout(fallbackTimerRef.current);
      }
    };
  }, [show, handleDismiss, onComplete]);

  // Attempt autoplay immediately upon mount
  useEffect(() => {
    if (!show || hasError || !videoRef.current) return;

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
          console.warn("[BG AI Intro] Autoplay restricted:", err);
          setAutoplayBlocked(true);
        });
    }
  }, [show, hasError]);

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
        .catch(() => handleVideoError());
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
              duration: 0.6,
              ease: [0.16, 1, 0.3, 1],
            },
          }}
          className="fixed inset-0 z-[99999] w-screen h-screen bg-[#09090b] flex items-center justify-center select-none overflow-hidden"
          style={{ willChange: "opacity" }}
        >
          {hasError ? (
            /* Clean Static Brand Splash Fallback */
            <div className="relative w-full h-full flex flex-col items-center justify-center bg-[#09090b] px-6 text-center">
              <div className="absolute inset-0 bg-radial-gradient from-indigo-950/20 via-transparent to-transparent pointer-events-none" />

              <motion.div
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ duration: 0.5, ease: "easeOut" }}
                className="relative z-10 flex flex-col items-center"
              >
                <div className="w-24 h-24 mb-6 rounded-3xl bg-zinc-900/80 border border-indigo-500/30 flex items-center justify-center shadow-2xl shadow-indigo-500/20 backdrop-blur-xl">
                  <img
                    src={iconSrc}
                    alt="BG AI"
                    className="w-16 h-16 object-contain drop-shadow-[0_0_15px_rgba(99,102,241,0.5)]"
                    onError={(e) => {
                      (e.target as HTMLElement).style.display = "none";
                    }}
                  />
                </div>

                <h1 className="text-3xl font-extrabold tracking-tight text-white mb-2 flex items-center gap-2">
                  <span>BG AI</span>
                  <span className="text-indigo-400 text-xs font-mono px-2 py-0.5 rounded-full bg-indigo-500/10 border border-indigo-500/20">
                    PLATFORM
                  </span>
                </h1>
                <p className="text-sm font-medium text-zinc-400 max-w-sm">
                  AI-Powered Conversational Database Intelligence
                </p>

                {/* Subtle loading indicator */}
                <div className="mt-8 flex items-center gap-2 text-xs font-mono text-indigo-300">
                  <Sparkles size={14} className="animate-pulse" />
                  <span>Preparing Desktop Workspace...</span>
                </div>
              </motion.div>

              {/* Skip button in fallback mode */}
              <div className="absolute bottom-6 right-6 z-30">
                <button
                  onClick={handleDismiss}
                  className="px-4 py-2 rounded-full text-xs font-mono font-medium tracking-wider text-white/90 hover:text-white bg-black/40 hover:bg-black/70 border border-white/15 backdrop-blur-md transition-all cursor-pointer flex items-center gap-2 shadow-lg"
                  title="Continue to BG AI (Esc)"
                >
                  <span>Continue</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/10 font-mono text-white/70">
                    Esc
                  </span>
                </button>
              </div>

              {/* Linear progress bar */}
              <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-white/10 z-30 overflow-hidden">
                <motion.div
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ duration: 1.8, ease: "linear" }}
                  className="h-full bg-gradient-to-r from-indigo-500 via-indigo-400 to-white"
                />
              </div>
            </div>
          ) : (
            /* True Fullscreen Video Player */
            <div className="relative w-full h-full flex items-center justify-center overflow-hidden bg-[#09090b]">
              <video
                ref={videoRef}
                playsInline
                muted
                autoPlay
                preload="auto"
                poster={logoSrc}
                onTimeUpdate={handleTimeUpdate}
                onEnded={handleDismiss}
                onError={handleVideoError}
                className="w-full h-full object-cover"
              >
                <source src={videoSrc} type="video/mp4" />
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
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
