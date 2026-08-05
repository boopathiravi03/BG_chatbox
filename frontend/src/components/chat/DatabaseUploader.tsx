import { useState } from "react";
import { Database, Upload, X } from "lucide-react";

interface Props {
  onClose: () => void;
  onUploadComplete?: () => void;
}

export default function DatabaseUploader({ onClose, onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setMessage("");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("http://127.0.0.1:8001/upload", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        setMessage("✅ Database uploaded successfully");
        setTimeout(() => {
          onClose();
          onUploadComplete?.();
        }, 1500);
      } else {
        setMessage(`❌ Error: ${data.message || "Upload failed"}`);
      }
    } catch (error) {
      setMessage("❌ Error uploading database");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[#1a1a1a] border border-white/10 rounded-2xl p-6 w-full max-w-md">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <Database size={20} />
            Upload Database
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-white">
            <X size={20} />
          </button>
        </div>

        <div className="border-2 border-dashed border-white/10 rounded-xl p-8 text-center hover:border-white/20 transition-colors">
          <Upload size={48} className="mx-auto mb-4 text-gray-400" />
          <p className="text-sm text-gray-400 mb-4">
            Drop your SQLite file here or click to browse
          </p>
          <label className="cursor-pointer">
            <input
              type="file"
              accept=".db,.sqlite,.sqlite3"
              onChange={handleUpload}
              className="hidden"
            />
            <span className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors">
              {uploading ? "Uploading..." : "Choose File"}
            </span>
          </label>
        </div>

        {message && (
          <p className="mt-4 text-sm text-center">{message}</p>
        )}
      </div>
    </div>
  );
}
