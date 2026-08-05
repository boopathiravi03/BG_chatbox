import { ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";

interface Props {
  graph: {
    nodes: any[];
    edges: any[];
  };
}

export default function RelationshipGraph({ graph }: Props) {
  const nodes = useMemo(
    () =>
      graph.nodes.map((n, index) => ({
        id: n.id,
        data: { label: n.label },
        position: {
          x: (index % 3) * 250,
          y: Math.floor(index / 3) * 150,
        },
      })),
    [graph.nodes]
  );

  const edges = useMemo(
    () =>
      graph.edges.map((e, index) => ({
        id: String(index),
        source: e.from,
        target: e.to,
        animated: true,
      })),
    [graph.edges]
  );

  return (
    <div className="h-[500px] rounded-xl overflow-hidden border border-zinc-700 dark:bg-[#111] bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
      />
    </div>
  );
}
