import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Database, Upload, X, FileUp, Loader2 } from "lucide-react";
import { API_BASE } from "../../services/api";
import {
  modalBackdropVariants,
  modalContainerVariants,
} from "../../lib/motion";
import { useToast } from "../../context/ToastContext";

interface Props {
  onClose: () => void;
  onUploadComplete?: () => void;
}

export default function DatabaseUploader({ onClose, onUploadComplete }: Props) {
  const [uploading, setUploading] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);
  const toast = useToast();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const uploadFile = async (file: File) => {
    if (
      !file.name.endsWith(".db") &&
      !file.name.endsWith(".sqlite") &&
      !file.name.endsWith(".sqlite3")
    ) {
      toast.error("Please select a valid SQLite database file (.db, .sqlite)");
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok && data.status === "success") {
        toast.success("SQLite database attached successfully!");
        setTimeout(() => {
          onClose();
          onUploadComplete?.();
        }, 800);
      } else {
        toast.error(data.message || "Upload failed. Please check the file.");
      }
    } catch {
      toast.error("Network error uploading database.");
    } finally {
      setUploading(false);
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <motion.div
          key="uploader-backdrop"
          variants={modalBackdropVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          onClick={onClose}
          className="fixed inset-0 bg-black/75 backdrop-blur-sm"
        />

        <motion.div
          key="uploader-container"
          variants={modalContainerVariants}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="relative w-full max-w-lg rounded-2xl bg-[#121215] border border-white/10 shadow-2xl shadow-black/90 overflow-hidden z-10"
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-5 border-b border-white/[0.08]">
            <div className="flex items-center gap-3">
              <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
                <Database size={20} />
              </div>
              <div>
                <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
                  Upload SQLite Database
                </h2>
                <p className="text-xs text-zinc-400">
                  Attach local .db, .sqlite, or .sqlite3 file
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Dropzone */}
          <div className="p-6">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragOver(true);
              }}
              onDragLeave={() => setIsDragOver(false)}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-2xl p-10 flex flex-col items-center justify-center text-center transition-all ${
                isDragOver
                  ? "border-indigo-500 bg-indigo-500/10 scale-[1.01]"
                  : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]"
              }`}
            >
              <div className="w-14 h-14 rounded-2xl bg-white/[0.04] border border-white/10 flex items-center justify-center mb-3.5 text-zinc-200 shadow-sm">
                {uploading ? (
                  <Loader2 size={26} className="animate-spin text-indigo-400" />
                ) : (
                  <FileUp size={26} className="text-indigo-400" />
                )}
              </div>

              <h3 className="text-sm sm:text-base font-semibold text-zinc-100 mb-1.5">
                {uploading
                  ? "Parsing schema and catalog..."
                  : "Drop your SQLite file here"}
              </h3>
              <p className="text-xs sm:text-sm text-zinc-400 max-w-xs mb-5 leading-normal">
                Supported formats: .db, .sqlite, and .sqlite3
              </p>

              <label className="relative inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-white/[0.08] hover:bg-white/[0.12] text-sm font-semibold text-white transition-colors cursor-pointer border border-white/10 shadow-sm">
                <span>Browse Files</span>
                <input
                  type="file"
                  accept=".db,.sqlite,.sqlite3"
                  onChange={handleFileInput}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
