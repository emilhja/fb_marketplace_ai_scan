import { useEffect, useState } from 'react'
import {
  fetchNotifications,
  type NotificationEventRow,
  type NotificationParams,
  type PagedResponse,
} from '../api'
import Pagination from '../components/Pagination'

function fmtDate(s: string) {
  return new Date(s).toLocaleString('sv-SE', { timeZone: 'Europe/Stockholm' })
}

export default function NotificationsPage() {
  const [data, setData] = useState<PagedResponse<NotificationEventRow> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const [listingId, setListingId] = useState<'' | number>('')
  const [channel, setChannel] = useState('')
  const [status, setStatus] = useState('')
  const [sentFrom, setSentFrom] = useState('')
  const [sentTo, setSentTo] = useState('')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  useEffect(() => {
    let cancelled = false
    async function loadNotifications() {
      setLoading(true)
      setError(null)
      const params: NotificationParams = {
        page,
        page_size: PAGE_SIZE,
        listing_id: listingId === '' ? undefined : listingId,
        channel: channel || undefined,
        status: status || undefined,
        sent_from: sentFrom || undefined,
        sent_to: sentTo || undefined,
        sort_dir: sortDir,
      }
      try {
        const nextData = await fetchNotifications(params)
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

    void loadNotifications()
    return () => { cancelled = true }
  }, [page, listingId, channel, status, sentFrom, sentTo, sortDir])

  const STATUS_COLORS: Record<string, string> = {
    sent: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
    skipped: 'bg-gray-100 text-gray-600',
  }

  return (
    <div>
      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
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
            <label className="block text-xs font-medium text-gray-500 mb-1">Channel</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="e.g. telegram"
              value={channel}
              onChange={e => { setChannel(e.target.value); setPage(1) }}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="e.g. sent"
              value={status}
              onChange={e => { setStatus(e.target.value); setPage(1) }}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Sent from</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={sentFrom} onChange={e => { setSentFrom(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Sent to</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={sentTo} onChange={e => { setSentTo(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Sort</label>
            <select className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={sortDir} onChange={e => { setSortDir(e.target.value as 'asc' | 'desc'); setPage(1) }}>
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
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Status</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Listing</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Channel</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">User</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Sent at</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Link</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map(row => (
              <>
                <tr
                  key={row.id}
                  className="border-b border-gray-100 hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  onClick={() => setExpandedId(expandedId === row.id ? null : row.id)}
                >
                  <td className="px-3 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[row.status] ?? 'bg-blue-100 text-blue-700'}`}>
                      {row.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-medium text-gray-800 max-w-xs truncate">{row.listing_title || `#${row.listing_id}`}</td>
                  <td className="px-3 py-2 text-gray-600">{row.channel}</td>
                  <td className="px-3 py-2 text-gray-600">{row.user_name}</td>
                  <td className="px-3 py-2 text-gray-500 text-xs whitespace-nowrap">{fmtDate(row.sent_at)}</td>
                  <td className="px-3 py-2">
                    {row.canonical_post_url ? (
                      <a href={row.canonical_post_url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()} className="text-indigo-600 hover:underline text-xs">FB ↗</a>
                    ) : '—'}
                  </td>
                </tr>
                {expandedId === row.id && row.details && (
                  <tr key={`${row.id}-detail`} className="bg-indigo-50/50 border-b border-indigo-100">
                    <td colSpan={6} className="px-4 py-3">
                      <p className="text-xs font-semibold text-gray-500 mb-1">Details (JSON)</p>
                      <pre className="text-xs text-gray-700 bg-white border border-gray-200 rounded p-2 overflow-x-auto max-h-40">{JSON.stringify(row.details, null, 2)}</pre>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No notification events found.</td></tr>
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
