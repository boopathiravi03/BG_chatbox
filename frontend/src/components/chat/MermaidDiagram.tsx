import { useEffect, useRef } from "react";
import mermaid from "mermaid";

interface Props {
  diagram?: string | null;
}

export default function MermaidDiagram({ diagram }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !diagram) return;

    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
    });

    const id = "mermaid-" + Date.now();

    mermaid.render(id, diagram).then((result) => {
      if (ref.current) {
        ref.current.innerHTML = result.svg;
      }
    }).catch(() => {
      if (ref.current) {
        ref.current.innerHTML = `<p class="text-red-400">Failed to render diagram.</p>`;
      }
    });
  }, [diagram]);

  if (!diagram) return null;

  return (
    <div
      className="mt-4 rounded-lg bg-zinc-900 border border-zinc-700 p-4 overflow-auto"
      ref={ref}
    />
  );
}
