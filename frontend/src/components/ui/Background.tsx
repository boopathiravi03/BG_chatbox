export default function Background() {
  return (
    <>
      {/* Base deep obsidian fill */}
      <div className="fixed inset-0 -z-20 bg-[#09090b]" />

      {/* Subtle top ambient gradient (Linear style) */}
      <div
        className="fixed inset-0 -z-10 pointer-events-none opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(99, 102, 241, 0.08), transparent 70%), radial-gradient(ellipse 60% 40% at 90% 100%, rgba(30, 27, 75, 0.06), transparent 70%)",
        }}
      />

      {/* Subtle micro-dot grid for depth */}
      <div
        className="fixed inset-0 -z-10 opacity-[0.025] pointer-events-none"
        style={{
          backgroundImage:
            "radial-gradient(rgba(255, 255, 255, 0.8) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
    </>
  );
}
