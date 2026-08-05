import { useEffect, useRef } from "react";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
});

export default function MermaidViewer({
  diagram,
}: {
  diagram?: { type: string; diagram: string };
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !diagram) return;
    mermaid.render(`mermaid-${Date.now()}`, diagram.diagram).then((result) => {
      if (ref.current) {
        ref.current.innerHTML = result.svg;
      }
    });
  }, [diagram]);

  if (!diagram || diagram.type !== "mermaid") return null;

  return (
    <div className="mt-4 rounded-xl bg-[#0d0d0d] border border-white/10 p-4">
      <p className="text-xs text-gray-500 mb-3 font-mono">ER Diagram</p>
      <div ref={ref} className="overflow-x-auto flex justify-center" />
    </div>
  );
}
