import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";

const TableNode = ({ data }: { data: { label?: string; columns?: string[] } }) => {
  if (!data || typeof data !== "object" || !data.label || String(data.label).trim() === "") {
    return null;
  }

  const label = String(data.label);
  const columns = Array.isArray(data.columns) ? data.columns : [];

  return (
    <div
      className="dark:bg-[#1a1a1a] bg-white dark:text-white text-gray-900 rounded-lg shadow-lg border dark:border-zinc-700 border-gray-200 min-w-[160px] overflow-hidden"
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-500 !w-3 !h-3" />
      <div className="px-3 py-2 bg-blue-600 dark:bg-blue-600 text-white font-semibold text-sm border-b dark:border-zinc-700 border-gray-200">
        {label}
      </div>
      {columns.length > 0 && (
        <div className="px-3 py-1.5 space-y-0.5">
          {columns.slice(0, 6).map((col, i) => (
            <div key={i} className="text-xs dark:text-gray-400 text-gray-600 truncate">
              • {col}
            </div>
          ))}
          {columns.length > 6 && (
            <div className="text-[10px] dark:text-gray-500 text-gray-400">+{columns.length - 6} more</div>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500 !w-3 !h-3" />
    </div>
  );
};

const nodeTypes = {
  tableNode: TableNode,
};

interface GraphNode {
  id: string | number;
  label: string;
  columns?: string[];
}

interface Props {
  graph: {
    nodes: GraphNode[];
    edges: { from: string | number; to: string | number }[];
  };
}

export default function RelationshipGraph({ graph }: Props) {
  const validNodes = (graph.nodes || []).filter(
    (node) => node && node.label && node.label.trim() !== "" && node.id && String(node.id).trim() !== ""
  );

  const validNodeIds = new Set(validNodes.map((n) => String(n.id)));
  const validEdges = (graph.edges || []).filter(
    (edge) => validNodeIds.has(String(edge.from)) && validNodeIds.has(String(edge.to))
  );

  const nodes = validNodes.map((node, index) => ({
    id: String(node.id),
    type: "tableNode",
    position: {
      x: (index % 3) * 220,
      y: Math.floor(index / 3) * 160,
    },
    data: {
      label: node.label,
      columns: node.columns,
    },
  }));

  const edges = validEdges.map((edge, index) => ({
    id: `edge-${index}`,
    source: String(edge.from),
    target: String(edge.to),
    type: "smoothstep",
    animated: true,
    style: { stroke: "#3b82f6", strokeWidth: 2 },
    markerEnd: {
      type: MarkerType.ArrowClosed,
      width: 20,
      height: 20,
    },
  }));

  console.log("React Flow Nodes:", nodes);
  console.log("React Flow Edges:", edges);

  if (nodes.length === 0) {
    return (
      <div style={{ height: "500px", width: "100%" }} className="flex items-center justify-center">
        <div className="text-center px-4">
          <p className="text-sm dark:text-gray-400 text-gray-600 mb-2">No relationships found.</p>
          <p className="text-xs dark:text-gray-500 text-gray-500">
            Upload a database containing foreign keys.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: "500px", width: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
