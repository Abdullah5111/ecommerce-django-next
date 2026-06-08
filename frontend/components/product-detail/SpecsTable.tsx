export default function SpecsTable({ specs }: { specs: Record<string, string> }) {
  const entries = Object.entries(specs || {});
  if (entries.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border border-zinc-200 rounded">
        <tbody>
          {entries.map(([key, value], i) => (
            <tr
              key={key}
              className={i % 2 === 0 ? "bg-zinc-50" : "bg-white"}
            >
              <th
                scope="row"
                className="text-left font-medium text-zinc-700 px-4 py-3 w-1/3 border-b border-zinc-200 align-top"
              >
                {key}
              </th>
              <td className="px-4 py-3 text-zinc-800 border-b border-zinc-200 align-top">
                {value}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
