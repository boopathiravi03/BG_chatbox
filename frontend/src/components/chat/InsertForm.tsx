import { useState } from "react";
import { UserPlus, ArrowRight } from "lucide-react";

interface Field {
  name: string;
  label: string;
  type: string;
  required: boolean;
}

interface InsertFormProps {
  title: string;
  message: string;
  fields: Field[];
  onSubmit: (values: Record<string, string>) => void;
  onCancel?: () => void;
}

export default function InsertForm({
  title,
  message,
  fields,
  onSubmit,
  onCancel,
}: InsertFormProps) {
  const [values, setValues] = useState<Record<string, string>>({});

  const handleChange = (name: string, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(values);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-4 rounded-2xl border border-white/[0.08] bg-[#0e0e11] p-5 sm:p-6 shadow-md"
    >
      <div className="flex items-center gap-2 text-indigo-400 font-bold text-sm sm:text-base">
        <UserPlus size={17} />
        <span>{title}</span>
      </div>
      <p className="mt-1.5 text-xs sm:text-sm text-zinc-300 leading-relaxed">
        {message}
      </p>

      <div className="mt-4 space-y-3.5">
        {fields.map((field) => (
          <div key={field.name}>
            <label className="block text-xs sm:text-sm font-semibold text-zinc-300 mb-1.5">
              {field.label}
              {field.required && <span className="text-rose-400 ml-1">*</span>}
            </label>
            <input
              type={field.type || "text"}
              required={field.required}
              value={values[field.name] || ""}
              onChange={(e) => handleChange(field.name, e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-sm text-zinc-100 placeholder:text-zinc-500 outline-none focus:border-indigo-500/60 transition-colors"
              placeholder={field.label}
            />
          </div>
        ))}
      </div>

      <div className="mt-5 flex items-center gap-2.5">
        <button
          type="submit"
          className="flex items-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white transition-all shadow-md shadow-indigo-600/20"
        >
          <span>Continue</span>
          <ArrowRight size={15} />
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.06] px-4 py-2.5 text-sm font-medium text-zinc-300 transition-colors"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
