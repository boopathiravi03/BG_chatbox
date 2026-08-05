import { Database } from "lucide-react";

export default function Hero() {
  return (
    <div className="text-center mb-12 text-black dark:text-white">

      <div className="inline-flex items-center gap-3 bg-blue-600/20 border border-blue-500/30 rounded-full px-5 py-2 mb-8">

        <Database size={18} className="text-blue-400"/>

        <span className="text-blue-300 font-medium">

          BG AI Database Assistant

        </span>

      </div>

      <h1 className="text-6xl font-extrabold tracking-tight leading-tight">
        Talk to your{" "}
        <span className="bg-gradient-to-r from-cyan-400 via-blue-500 to-indigo-500 bg-clip-text text-transparent">
          Database
        </span>
      </h1>

      <p className="mt-6 max-w-2xl text-lg text-gray-700 dark:text-gray-400">
        Query SQL databases using natural language, generate charts,
        visualize schemas, and discover insights instantly with AI.
      </p>

    </div>
  );
}
