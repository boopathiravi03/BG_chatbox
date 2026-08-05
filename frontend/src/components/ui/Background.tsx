export default function Background() {
  return (
    <>
      <div className="fixed inset-0 -z-20 bg-[#0B1120]" />

      <div
        className="fixed inset-0 -z-10"
        style={{
          background:
            "radial-gradient(circle at top, rgba(37,99,235,0.25), transparent 55%)",
        }}
      />

      <div className="fixed top-40 left-1/2 h-[500px] w-[500px] -translate-x-1/2 rounded-full bg-blue-500/20 blur-[140px] -z-10" />

      <div className="fixed bottom-0 left-0 right-0 h-72 bg-gradient-to-t from-[#09090B] to-transparent -z-10" />
    </>
  );
}
