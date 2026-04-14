import { useEffect, useState } from 'react'
import {
  fetchPriceHistory,
  type PagedResponse,
  type PriceHistoryParams,
  type PriceHistoryRow,
} from '../api'
import Pagination from '../components/Pagination'

function fmtDate(s: string) {
  return new Date(s).toLocaleString('sv-SE', { timeZone: 'Europe/Stockholm' })
}

function fmtChange(value: number | null) {
  if (value === null) return '—'
  if (value === 0) return '0'
  return value > 0 ? `+${value}` : String(value)
}

export default function PriceHistoryPage() {
  const [data, setData] = useState<PagedResponse<PriceHistoryRow> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [listingId, setListingId] = useState<'' | number>('')
  const [observedFrom, setObservedFrom] = useState('')
  const [observedTo, setObservedTo] = useState('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  useEffect(() => {
    let cancelled = false
    async function loadPriceHistory() {
      setLoading(true)
      setError(null)
      const params: PriceHistoryParams = {
        page,
        page_size: PAGE_SIZE,
        listing_id: listingId === '' ? undefined : listingId,
        observed_from: observedFrom || undefined,
        observed_to: observedTo || undefined,
        sort_dir: sortDir,
      }
      try {
        const nextData = await fetchPriceHistory(params)
        if (!cancelled) {
          setData(nextData)
        }
      } catch (e) {
        if (!cancelled) {
          setError(String(e))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void loadPriceHistory()
    return () => { cancelled = true }
  }, [page, listingId, observedFrom, observedTo, sortDir])

  return (
    <div>
      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Listing ID</label>
            <input
              type="number"
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="All"
              value={listingId}
              onChange={e => { setListingId(e.target.value === '' ? '' : Number(e.target.value)); setPage(1) }}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Observed from</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={observedFrom} onChange={e => { setObservedFrom(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Observed to</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={observedTo} onChange={e => { setObservedTo(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Sort</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={sortDir}
              onChange={e => { setSortDir(e.target.value as 'asc' | 'desc'); setPage(1) }}
            >
              <option value="desc">Newest first</option>
              <option value="asc">Oldest first</option>
            </select>
          </div>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500 mb-2">Loading…</p>}
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">ID</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Listing</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Price</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Previous price</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Changed by</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Observed at</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Link</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map(row => (
              <tr key={row.id} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="px-3 py-2 text-gray-400 text-xs">{row.id}</td>
                <td className="px-3 py-2">
                  <span className="font-medium text-gray-800 line-clamp-1">{row.listing_title || `#${row.listing_id}`}</span>
                </td>
                <td className="px-3 py-2 font-mono text-gray-700 whitespace-nowrap">{row.price}</td>
                <td className="px-3 py-2 font-mono text-gray-500 whitespace-nowrap">{row.previous_price || '—'}</td>
                <td className="px-3 py-2 font-mono whitespace-nowrap">
                  <span className={row.changed_by === null ? 'text-gray-400' : row.changed_by > 0 ? 'text-red-600' : row.changed_by < 0 ? 'text-emerald-600' : 'text-gray-500'}>
                    {fmtChange(row.changed_by)}
                  </span>
                </td>
                <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">{fmtDate(row.observed_at)}</td>
                <td className="px-3 py-2">
                  {row.canonical_post_url ? (
                    <a href={row.canonical_post_url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline text-xs">FB ↗</a>
                  ) : '—'}
                </td>
              </tr>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400">No price history records found.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && (
        <Pagination page={data.page} pageSize={data.page_size} total={data.total} onPage={setPage} />
      )}
    </div>
  )
}
