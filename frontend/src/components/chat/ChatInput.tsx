import { Mic, SendHorizontal, Database, Sparkles } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { QUERY_SUGGESTIONS } from "../../data/suggestions";

interface ChatInputProps {
  onSend?: (message: string) => void;
  disabled?: boolean;
  initialMessage?: string;
}

export default function ChatInput({ onSend, disabled, initialMessage }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [filtered, setFiltered] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [listening, setListening] = useState(false);
  const inputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (initialMessage) {
      setMessage(initialMessage);
    }
  }, [initialMessage]);

  useEffect(() => {
    if (disabled) {
      setMessage("");
    }
  }, [disabled]);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (inputRef.current && !inputRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };

    document.addEventListener("click", close);

    return () => document.removeEventListener("click", close);
  }, []);

  const handleChange = (value: string) => {
    setMessage(value);

    if (!value.trim()) {
      setFiltered([]);
      setShowSuggestions(false);
      return;
    }

    const results = QUERY_SUGGESTIONS.filter((item) =>
      item.toLowerCase().includes(value.toLowerCase())
    );

    setFiltered(results.slice(0, 6));
    setShowSuggestions(results.length > 0);
  };

  const startListening = () => {
    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    console.log("Speech API:", SpeechRecognition);

    if (!SpeechRecognition) {
      alert("Speech Recognition is not supported.");
      return;
    }

    const recognition = new SpeechRecognition();

    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    console.log("Starting...");

    recognition.start();

    recognition.onstart = () => {
      console.log("Listening...");
      setListening(true);
    };

    recognition.onresult = (event: any) => {
      console.log("Result:", event.results);

      const text = event.results[0][0].transcript;

      console.log("Transcript:", text);

      setMessage(text);
    };

    recognition.onerror = (e: any) => {
      console.log("Speech Error:", e);
      setListening(false);
    };

    recognition.onend = () => {
      console.log("Speech End");
      setListening(false);
    };
  };

  const handleSend = () => {
    if (!message.trim() || !onSend || disabled) return;
    onSend(message.trim());
    setMessage("");
    setShowSuggestions(false);
    setFiltered([]);
  };

  return (
    <div className="w-full max-w-4xl relative" ref={inputRef}>
      <div className="rounded-2xl border border-white/10 dark:bg-[#1b1b1f] bg-white shadow-lg p-4">
        <textarea
          rows={2}
          placeholder="Ask anything about your database..."
          value={message}
          onChange={(e) => handleChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          className="w-full resize-none bg-transparent outline-none text-base dark:text-white text-black dark:placeholder:text-gray-500 placeholder:text-gray-400"
        />
        {listening && (
          <div className="flex items-center gap-3 mt-3">
            <span className="text-red-400 font-medium">
              🎤 Listening...
            </span>

            <div className="flex items-end gap-1 h-6">
              <span className="wave" />
              <span className="wave" />
              <span className="wave" />
              <span className="wave" />
              <span className="wave" />
            </div>
          </div>
        )}
        <div className="flex justify-between items-center mt-4">
          <div className="flex gap-3">
            <button className="px-4 py-2 rounded-full dark:bg-white/5 bg-gray-200 dark:hover:bg-white/10 hover:bg-gray-300 flex items-center gap-2 dark:text-white text-gray-900">
              <Database size={16} />
              SQLite
            </button>
            <button className="px-4 py-2 rounded-full dark:bg-white/5 bg-gray-200 dark:hover:bg-white/10 hover:bg-gray-300 flex items-center gap-2 dark:text-white text-gray-900">
              <Sparkles size={16} />
              BG AI
            </button>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={startListening}
              className={`relative flex items-center justify-center w-12 h-12 rounded-full transition-all duration-300 ${
                listening
                  ? "bg-red-600 animate-pulse shadow-lg shadow-red-500/50"
                  : "dark:bg-zinc-700 bg-gray-300 dark:hover:bg-zinc-600 hover:bg-gray-400"
              }`}
            >
              <Mic size={20} className="text-white" />

              {listening && (
                <span className="absolute inset-0 rounded-full border-2 border-red-400 animate-ping" />
              )}
            </button>
            <button
              onClick={handleSend}
              disabled={disabled || !message.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl px-5 py-2 flex items-center gap-2 text-white"
            >
              Ask BG AI
              <SendHorizontal size={18} />
            </button>
          </div>
        </div>
      </div>

      {showSuggestions && (
        <div className="absolute left-0 right-0 bottom-16 dark:bg-[#18181b] bg-white border dark:border-zinc-700 border-gray-200 rounded-xl shadow-xl overflow-hidden z-50">
          {filtered.map((item) => (
            <button
              key={item}
              onClick={() => {
                setMessage(item);
                setShowSuggestions(false);
              }}
              className="w-full text-left px-4 py-3 dark:hover:bg-zinc-800 hover:bg-gray-100 transition text-sm dark:text-gray-300 text-gray-700"
            >
              {item}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
