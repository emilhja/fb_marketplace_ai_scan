interface Props { score: number | null }

const COLORS: Record<number, string> = {
  0: 'bg-gray-100 text-gray-500',
  1: 'bg-red-100 text-red-700',
  2: 'bg-orange-100 text-orange-700',
  3: 'bg-yellow-100 text-yellow-700',
  4: 'bg-lime-100 text-lime-700',
  5: 'bg-green-100 text-green-800',
}

export default function ScoreBadge({ score }: Props) {
  if (score === null || score === undefined) return <span className="text-gray-400 text-xs">—</span>
  const cls = COLORS[score] ?? 'bg-gray-100 text-gray-500'
  return (
    <span className={`inline-flex items-center justify-center w-7 h-7 rounded-full text-sm font-bold ${cls}`}>
      {score}
    </span>
  )
}
