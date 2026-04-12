interface Props {
  page: number
  pageSize: number
  total: number
  onPage: (p: number) => void
}

export default function Pagination({ page, pageSize, total, onPage }: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center justify-between mt-3 text-sm text-gray-600">
      <span>
        {from}–{to} of {total}
      </span>
      <div className="flex gap-1">
        <button
          onClick={() => onPage(1)}
          disabled={page === 1}
          className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
        >
          «
        </button>
        <button
          onClick={() => onPage(page - 1)}
          disabled={page === 1}
          className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
        >
          ‹
        </button>
        <span className="px-3 py-1 rounded border border-indigo-300 bg-indigo-50 text-indigo-700 font-medium">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
        >
          ›
        </button>
        <button
          onClick={() => onPage(totalPages)}
          disabled={page >= totalPages}
          className="px-2 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100"
        >
          »
        </button>
      </div>
    </div>
  )
}
