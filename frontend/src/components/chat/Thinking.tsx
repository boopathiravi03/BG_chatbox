import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";

const loadingMessages = [
  "Analyzing database...",
  "Generating SQL...",
  "Processing results...",
  "Fetching data...",
];

export default function Thinking() {
  const [msg, setMsg] = useState(loadingMessages[0]);

  useEffect(() => {
    const interval = setInterval(() => {
      setMsg((prev) => {
        const idx = loadingMessages.indexOf(prev);
        return loadingMessages[(idx + 1) % loadingMessages.length];
      });
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex gap-2 items-center py-4">
      <Loader2 size={16} className="animate-spin text-blue-500" />
      <span className="text-sm dark:text-gray-400 text-gray-600">{msg}</span>
    </div>
  );
}
