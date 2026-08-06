import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
} from "@xyflow/react";

import "@xyflow/react/dist/style.css";


const TableNode = ({ data }: any) => {
  return (
    <div
      style={{
        padding: "10px 20px",
        border: "1px solid #555",
        borderRadius: "8px",
        background: "white",
        color: "black",
        fontWeight: "bold",
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
      />

      {data.label}

      <Handle
        type="source"
        position={Position.Bottom}
      />
    </div>
  );
};


const nodeTypes = {
  tableNode: TableNode,
};


interface Props {
  graph: {
    nodes: any[];
    edges: any[];
  };
}


export default function RelationshipGraph({ graph }: Props) {

  const nodes = graph.nodes.map((node, index) => ({
    id: String(node.id),
    type: "tableNode",
    position: {
      x: (index % 2) * 250,
      y: Math.floor(index / 2) * 150,
    },
    data: {
      label: node.label,
    },
  }));


  const edges = graph.edges.map((edge, index) => ({
    id: `edge-${index}`,
    source: String(edge.from),
    target: String(edge.to),
    sourceHandle: null,
    targetHandle: null,
  }));


  return (
    <div style={{ height: "500px", width: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
