interface Props {
  explanation: string;
}

export default function ExplanationCard({ explanation }: Props) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900">
      <div className="px-4 py-2 border-b border-gray-200 dark:border-zinc-700">
        <h3 className="text-sm font-semibold text-blue-600 dark:text-blue-400">
          AI Explanation
        </h3>
      </div>

      <div className="p-4 text-gray-700 dark:text-zinc-300 leading-7">
        {explanation}
      </div>
    </div>
  );
}
