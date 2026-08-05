export default function ModelSelector() {
  return (
    <div className="flex items-center gap-3">
      <select className="dark:bg-[#1a1a1a] bg-white border border-white/10 rounded-xl px-4 py-2 text-sm outline-none focus:border-blue-500 dark:text-white text-black">
        <option>SQLite</option>
        <option>PostgreSQL</option>
        <option>MySQL</option>
      </select>
      <div className="dark:bg-white/5 bg-gray-200 px-4 py-2 rounded-full border border-white/10 dark:text-white text-black">
        BG AI
      </div>
    </div>
  );
}
