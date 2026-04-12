import { useEffect, useState } from 'react'
import {
  fetchListings,
  type ListingRow,
  type ListingsParams,
  type PagedResponse,
} from '../api'
import Pagination from '../components/Pagination'
import ScoreBadge from '../components/ScoreBadge'
import SortTh from '../components/SortTh'

const LISTING_KINDS = ['gpu_only', 'complete_pc', 'other', 'unknown']

function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleString('sv-SE', { timeZone: 'Europe/Stockholm' })
}

export default function ListingsPage() {
  const [data, setData] = useState<PagedResponse<ListingRow> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)

  // filters
  const [title, setTitle] = useState('')
  const [scoreMin, setScoreMin] = useState<'' | number>('')
  const [scoreMax, setScoreMax] = useState<'' | number>('')
  const [listingKind, setListingKind] = useState('')
  const [marketplace, setMarketplace] = useState('')
  const [lastSeenFrom, setLastSeenFrom] = useState('')
  const [lastSeenTo, setLastSeenTo] = useState('')
  const [evaluatedFrom, setEvaluatedFrom] = useState('')
  const [evaluatedTo, setEvaluatedTo] = useState('')
  // sort
  const [sortBy, setSortBy] = useState('last_seen_at')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  // pagination
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 50

  function handleSort(col: string) {
    if (col === sortBy) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortBy(col)
      setSortDir('desc')
    }
    setPage(1)
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const params: ListingsParams = {
      page,
      page_size: PAGE_SIZE,
      sort_by: sortBy,
      sort_dir: sortDir,
      title: title || undefined,
      score_min: scoreMin === '' ? undefined : scoreMin,
      score_max: scoreMax === '' ? undefined : scoreMax,
      listing_kind: listingKind || undefined,
      marketplace: marketplace || undefined,
      last_seen_from: lastSeenFrom || undefined,
      last_seen_to: lastSeenTo || undefined,
      evaluated_from: evaluatedFrom || undefined,
      evaluated_to: evaluatedTo || undefined,
    }
    fetchListings(params)
      .then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(String(e)); setLoading(false) } })
    return () => { cancelled = true }
  }, [page, sortBy, sortDir, title, scoreMin, scoreMax, listingKind, marketplace, lastSeenFrom, lastSeenTo, evaluatedFrom, evaluatedTo])

  function resetFilters() {
    setTitle(''); setScoreMin(''); setScoreMax('')
    setListingKind(''); setMarketplace('')
    setLastSeenFrom(''); setLastSeenTo('')
    setEvaluatedFrom(''); setEvaluatedTo('')
    setPage(1)
  }

  return (
    <div>
      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          <div className="col-span-2 sm:col-span-3 lg:col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Title search</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="e.g. RTX 5060"
              value={title}
              onChange={e => { setTitle(e.target.value); setPage(1) }}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Score min</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={scoreMin}
              onChange={e => { setScoreMin(e.target.value === '' ? '' : Number(e.target.value)); setPage(1) }}
            >
              <option value="">Any</option>
              {[0,1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Score max</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={scoreMax}
              onChange={e => { setScoreMax(e.target.value === '' ? '' : Number(e.target.value)); setPage(1) }}
            >
              <option value="">Any</option>
              {[0,1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Kind</label>
            <select
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={listingKind}
              onChange={e => { setListingKind(e.target.value); setPage(1) }}
            >
              <option value="">All</option>
              {LISTING_KINDS.map(k => <option key={k} value={k}>{k}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Marketplace</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="e.g. facebook"
              value={marketplace}
              onChange={e => { setMarketplace(e.target.value); setPage(1) }}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Last seen from</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={lastSeenFrom} onChange={e => { setLastSeenFrom(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Last seen to</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={lastSeenTo} onChange={e => { setLastSeenTo(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Evaluated from</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={evaluatedFrom} onChange={e => { setEvaluatedFrom(e.target.value); setPage(1) }} />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Evaluated to</label>
            <input type="datetime-local" className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              value={evaluatedTo} onChange={e => { setEvaluatedTo(e.target.value); setPage(1) }} />
          </div>

          <div className="flex items-end">
            <button onClick={resetFilters} className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 transition-colors">
              Reset
            </button>
          </div>
        </div>
      </div>

      {/* Status bar */}
      {loading && <p className="text-sm text-gray-500 mb-2">Loading…</p>}
      {error && <p className="text-sm text-red-600 mb-2">{error}</p>}

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <SortTh col="score" label="Score" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="title" label="Title" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="current_price" label="Price" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Kind</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Location</th>
              <SortTh col="last_seen_at" label="Last seen" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="evaluated_at" label="Evaluated" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Link</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map(row => (
              <>
                <tr
                  key={row.id}
                  className="border-b border-gray-100 hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                >
                  <td className="px-3 py-2"><ScoreBadge score={row.ai?.score ?? null} /></td>
                  <td className="px-3 py-2 max-w-xs">
                    <span className="font-medium text-gray-900 line-clamp-2">{row.title}</span>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap font-mono text-gray-700">{row.current_price}</td>
                  <td className="px-3 py-2">
                    {row.ai?.listing_kind ? (
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-700">
                        {row.ai.listing_kind}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2 text-gray-600 max-w-[12rem] truncate">{row.location || '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">{fmtDate(row.last_seen_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">{fmtDate(row.ai?.evaluated_at ?? null)}</td>
                  <td className="px-3 py-2">
                    <a
                      href={row.canonical_post_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={e => e.stopPropagation()}
                      className="text-indigo-600 hover:underline text-xs"
                    >
                      FB ↗
                    </a>
                  </td>
                </tr>
                {expanded === row.id && (
                  <tr key={`${row.id}-detail`} className="bg-indigo-50/60 border-b border-indigo-100">
                    <td colSpan={8} className="px-4 py-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <h3 className="font-semibold text-gray-700 mb-1">Listing</h3>
                          <dl className="space-y-1 text-gray-600">
                            <div><dt className="inline font-medium">ID: </dt><dd className="inline">{row.id}</dd></div>
                            <div><dt className="inline font-medium">Key: </dt><dd className="inline font-mono text-xs">{row.listing_key}</dd></div>
                            <div><dt className="inline font-medium">Marketplace: </dt><dd className="inline">{row.marketplace}</dd></div>
                            <div><dt className="inline font-medium">Original price: </dt><dd className="inline">{row.original_price || '—'}</dd></div>
                            <div><dt className="inline font-medium">Condition: </dt><dd className="inline">{row.skick || '—'}</dd></div>
                            <div><dt className="inline font-medium">First seen: </dt><dd className="inline">{fmtDate(row.first_seen_at)}</dd></div>
                          </dl>
                          {row.description && (
                            <div className="mt-2">
                              <p className="font-medium text-gray-700 mb-0.5">Description</p>
                              <p className="text-xs text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto border border-gray-200 rounded p-2 bg-white">{row.description}</p>
                            </div>
                          )}
                        </div>
                        {row.ai && (
                          <div>
                            <h3 className="font-semibold text-gray-700 mb-1">AI evaluation</h3>
                            <dl className="space-y-1 text-gray-600">
                              <div><dt className="inline font-medium">Model: </dt><dd className="inline text-xs">{row.ai.response_model || row.ai.model || '—'}</dd></div>
                              <div><dt className="inline font-medium">Conclusion: </dt><dd className="inline">{row.ai.conclusion || '—'}</dd></div>
                            </dl>
                            {row.ai.comment && (
                              <div className="mt-2">
                                <p className="font-medium text-gray-700 mb-0.5">Comment</p>
                                <p className="text-xs text-gray-600 whitespace-pre-wrap max-h-32 overflow-y-auto border border-gray-200 rounded p-2 bg-white">{row.ai.comment}</p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-gray-400">No listings match the current filters.</td></tr>
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
