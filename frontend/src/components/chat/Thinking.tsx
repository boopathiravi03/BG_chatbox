export default function Thinking() {
  return (
    <div className="flex gap-2 items-center py-4">
      <div className="size-2 rounded-full bg-blue-500 animate-bounce"/>

      <div
        className="size-2 rounded-full bg-blue-500 animate-bounce"
        style={{animationDelay:"150ms"}}
      />

      <div
        className="size-2 rounded-full bg-blue-500 animate-bounce"
        style={{animationDelay:"300ms"}}
      />

      <span className="ml-2 text-zinc-400">

        BG AI is thinking...

      </span>
    </div>
  );
}
