import { useEffect, useRef } from "react";

interface Props {
  chart: string;
}

export default function MermaidChart({ chart }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;

    import("mermaid").then(({ default: mermaid }) => {
      if (!isMounted || !ref.current) return;
      mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
      });

      const id = "diagram-" + Date.now();
      return mermaid.render(id, chart).then(({ svg }) => {
        if (isMounted && ref.current) {
          ref.current.innerHTML = svg;
        }
      });
    }).catch(() => {
      if (isMounted && ref.current) {
        ref.current.innerHTML =
          "<p style='color:red'>Failed to render Mermaid diagram.</p>";
      }
    });

    return () => {
      isMounted = false;
    };
  }, [chart]);

  return (
    <div
      className="rounded-xl bg-zinc-900 border border-zinc-700 p-4 overflow-auto"
      ref={ref}
    />
  );
}
