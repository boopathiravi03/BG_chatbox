import { useEffect, useRef } from "react";
import mermaid from "mermaid";

interface Props {
  chart: string;
}

export default function MermaidChart({ chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
    });

    const render = async () => {
      if (!ref.current) return;

      const id = "diagram-" + Date.now();

      try {
        const { svg } = await mermaid.render(id, chart);
        ref.current.innerHTML = svg;
      } catch (err) {
        ref.current.innerHTML =
          "<p style='color:red'>Failed to render Mermaid diagram.</p>";
      }
    };

    render();
  }, [chart]);

  return (
    <div
      className="rounded-xl bg-zinc-900 border border-zinc-700 p-4 overflow-auto"
      ref={ref}
    />
  );
}
