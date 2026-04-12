interface Props {
  col: string
  label: string
  sortBy: string
  sortDir: 'asc' | 'desc'
  onSort: (col: string) => void
}

export default function SortTh({ col, label, sortBy, sortDir, onSort }: Props) {
  const active = sortBy === col
  return (
    <th
      onClick={() => onSort(col)}
      className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide cursor-pointer select-none whitespace-nowrap hover:bg-gray-100"
    >
      {label}
      {active ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ' ⇅'}
    </th>
  )
}
