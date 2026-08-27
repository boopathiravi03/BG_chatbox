import { useState } from "react";

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

export default function InsertForm({ title, message, fields, onSubmit, onCancel }: InsertFormProps) {
  const [values, setValues] = useState<Record<string, string>>({});

  const handleChange = (name: string, value: string) => {
    setValues((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(values);
  };

  return (
    <form onSubmit={handleSubmit} className="mt-4 rounded-xl border border-blue-500/30 bg-blue-500/10 p-4">
      <div className="flex items-center gap-2 text-blue-400 font-semibold">
        👤 {title}
      </div>
      <p className="mt-2 text-sm text-gray-300">{message}</p>

      <div className="mt-4 space-y-3">
        {fields.map((field) => (
          <div key={field.name}>
            <label className="block text-xs font-medium text-gray-400 mb-1">
              {field.label}
              {field.required && <span className="text-red-400 ml-1">*</span>}
            </label>
            <input
              type={field.type || "text"}
              required={field.required}
              value={values[field.name] || ""}
              onChange={(e) => handleChange(field.name, e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-[#1b1b1f] border border-white/10 text-sm text-white placeholder:text-gray-500 outline-none focus:border-blue-500"
              placeholder={field.label}
            />
          </div>
        ))}
      </div>

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
        >
          Continue →
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg bg-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-600"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
