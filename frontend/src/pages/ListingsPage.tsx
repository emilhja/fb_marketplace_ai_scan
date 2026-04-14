import { Fragment, useEffect, useState } from 'react'
import {
  fetchListings,
  rerunListings,
  type ListingRow,
  type ListingsParams,
  type PagedResponse,
  updateListing,
} from '../api'
import Pagination from '../components/Pagination'
import ScoreBadge from '../components/ScoreBadge'
import SortTh from '../components/SortTh'

const LISTING_KINDS = ['gpu_only', 'complete_pc', 'other', 'unknown']

function fmtDate(s: string | null) {
  if (!s) return '—'
  return new Date(s).toLocaleString('sv-SE', { timeZone: 'Europe/Stockholm' })
}

function parseVramSortKey(vram: string | null) {
  if (!vram) return { amount: 0, uncertain: 1 }
  const match = vram.match(/(\d{1,2})\s*GB(\?)?$/i)
  if (!match) return { amount: 0, uncertain: 1 }
  return {
    amount: Number(match[1]),
    uncertain: match[2] ? 1 : 0,
  }
}

function sortListingsForDisplay(items: ListingRow[], sortBy: string, sortDir: 'asc' | 'desc') {
  if (sortBy !== 'vram') return items

  return [...items].sort((a, b) => {
    const left = parseVramSortKey(a.vram)
    const right = parseVramSortKey(b.vram)

    if (left.amount !== right.amount) {
      return sortDir === 'asc' ? left.amount - right.amount : right.amount - left.amount
    }
    if (left.uncertain !== right.uncertain) {
      return left.uncertain - right.uncertain
    }
    return new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime()
  })
}

export default function ListingsPage() {
  const [data, setData] = useState<PagedResponse<ListingRow> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [draftNotes, setDraftNotes] = useState<Record<number, string>>({})
  const [draftFeedback, setDraftFeedback] = useState<Record<number, 'up' | 'down' | null>>({})
  const [draftVramOverrides, setDraftVramOverrides] = useState<Record<number, string>>({})
  const [draftContactedSeller, setDraftContactedSeller] = useState<Record<number, boolean>>({})
  const [savingId, setSavingId] = useState<number | null>(null)
  const [editingVramId, setEditingVramId] = useState<number | null>(null)
  const [feedbackError, setFeedbackError] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [rerunning, setRerunning] = useState(false)
  const [rerunMessage, setRerunMessage] = useState<string | null>(null)

  // filters
  const [title, setTitle] = useState('')
  const [search, setSearch] = useState('')
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
  const visibleIds = data?.items.map(item => item.id) ?? []
  const selectedVisibleCount = visibleIds.filter(id => selectedIds.includes(id)).length
  const allVisibleSelected = visibleIds.length > 0 && selectedVisibleCount === visibleIds.length

  function buildParams(): ListingsParams {
    return {
      page,
      page_size: PAGE_SIZE,
      sort_by: sortBy,
      sort_dir: sortDir,
      title: title || undefined,
      search: search || undefined,
      score_min: scoreMin === '' ? undefined : scoreMin,
      score_max: scoreMax === '' ? undefined : scoreMax,
      listing_kind: listingKind || undefined,
      marketplace: marketplace || undefined,
      last_seen_from: lastSeenFrom || undefined,
      last_seen_to: lastSeenTo || undefined,
      evaluated_from: evaluatedFrom || undefined,
      evaluated_to: evaluatedTo || undefined,
    }
  }

  function applyListings(nextData: PagedResponse<ListingRow>) {
    setData({
      ...nextData,
      items: sortListingsForDisplay(nextData.items, sortBy, sortDir),
    })
    setDraftNotes(prev => {
      const next = { ...prev }
      for (const item of nextData.items) {
        if (!(item.id in next)) next[item.id] = item.user_note ?? ''
      }
      return next
    })
    setDraftFeedback(prev => {
      const next = { ...prev }
      for (const item of nextData.items) {
        if (!(item.id in next)) next[item.id] = item.user_feedback
      }
      return next
    })
    setDraftVramOverrides(prev => {
      const next = { ...prev }
      for (const item of nextData.items) {
        if (!(item.id in next)) next[item.id] = item.vram_override ?? ''
      }
      return next
    })
    setDraftContactedSeller(prev => {
      const next = { ...prev }
      for (const item of nextData.items) {
        if (!(item.id in next)) next[item.id] = item.contacted_seller
      }
      return next
    })
  }

  async function loadListings() {
    setLoading(true)
    setError(null)
    const nextData = await fetchListings(buildParams())
    applyListings(nextData)
  }

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
      search: search || undefined,
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
      .then(nextData => {
        if (!cancelled) {
          setData({
            ...nextData,
            items: sortListingsForDisplay(nextData.items, sortBy, sortDir),
          })
          setDraftNotes(prev => {
            const next = { ...prev }
            for (const item of nextData.items) {
              if (!(item.id in next)) next[item.id] = item.user_note ?? ''
            }
            return next
          })
          setDraftFeedback(prev => {
            const next = { ...prev }
            for (const item of nextData.items) {
              if (!(item.id in next)) next[item.id] = item.user_feedback
            }
            return next
          })
          setDraftVramOverrides(prev => {
            const next = { ...prev }
            for (const item of nextData.items) {
              if (!(item.id in next)) next[item.id] = item.vram_override ?? ''
            }
            return next
          })
          setDraftContactedSeller(prev => {
            const next = { ...prev }
            for (const item of nextData.items) {
              if (!(item.id in next)) next[item.id] = item.contacted_seller
            }
            return next
          })
        }
      })
      .catch(e => {
        if (!cancelled) {
          setError(String(e))
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [page, sortBy, sortDir, title, search, scoreMin, scoreMax, listingKind, marketplace, lastSeenFrom, lastSeenTo, evaluatedFrom, evaluatedTo])

  function resetFilters() {
    setTitle(''); setSearch(''); setScoreMin(''); setScoreMax('')
    setListingKind(''); setMarketplace('')
    setLastSeenFrom(''); setLastSeenTo('')
    setEvaluatedFrom(''); setEvaluatedTo('')
    setPage(1)
  }

  async function saveListingUpdates(row: ListingRow, payload: { user_note?: string; user_feedback?: 'up' | 'down' | null; vram_override?: string | null; contacted_seller?: boolean }) {
    setSavingId(row.id)
    setFeedbackError(null)
    try {
      const updated = await updateListing(row.id, payload)
      setData(prev => prev ? {
        ...prev,
        items: prev.items.map(item => item.id === row.id ? updated : item),
      } : prev)
      setDraftNotes(prev => ({ ...prev, [row.id]: updated.user_note }))
      setDraftFeedback(prev => ({ ...prev, [row.id]: updated.user_feedback }))
      setDraftVramOverrides(prev => ({ ...prev, [row.id]: updated.vram_override ?? '' }))
      setDraftContactedSeller(prev => ({ ...prev, [row.id]: updated.contacted_seller }))
    } catch (e) {
      setFeedbackError(String(e))
    } finally {
      setSavingId(current => current === row.id ? null : current)
    }
  }

  function markSellerContacted(row: ListingRow) {
    void saveListingUpdates(row, {
      user_note: draftNotes[row.id] ?? row.user_note ?? '',
      user_feedback: draftFeedback[row.id] ?? row.user_feedback,
      vram_override: draftVramOverrides[row.id] ?? row.vram_override ?? null,
      contacted_seller: true,
    })
  }

  function startEditingVram(row: ListingRow) {
    setDraftVramOverrides(prev => ({ ...prev, [row.id]: row.vram_override ?? row.vram ?? '' }))
    setEditingVramId(row.id)
  }

  function cancelEditingVram(row: ListingRow) {
    setDraftVramOverrides(prev => ({ ...prev, [row.id]: row.vram_override ?? '' }))
    setEditingVramId(current => current === row.id ? null : current)
  }

  async function saveVramOverride(row: ListingRow) {
    await saveListingUpdates(row, {
      vram_override: (draftVramOverrides[row.id] ?? '').trim() || null,
    })
    setEditingVramId(current => current === row.id ? null : current)
  }

  function toggleFeedback(row: ListingRow, nextFeedback: 'up' | 'down') {
    setDraftFeedback(prev => {
      const current = prev[row.id] ?? row.user_feedback
      return { ...prev, [row.id]: current === nextFeedback ? null : nextFeedback }
    })
  }

  function toggleSelected(listingId: number) {
    setSelectedIds(prev => prev.includes(listingId) ? prev.filter(id => id !== listingId) : [...prev, listingId])
  }

  function toggleSelectVisible() {
    setSelectedIds(prev => {
      if (allVisibleSelected) {
        return prev.filter(id => !visibleIds.includes(id))
      }
      return Array.from(new Set([...prev, ...visibleIds]))
    })
  }

  async function handleRerunSelected() {
    if (selectedIds.length === 0) return
    setRerunning(true)
    setRerunMessage(null)
    setError(null)
    try {
      const result = await rerunListings(selectedIds)
      const queuedCount = result.results.filter(row => row.message === 'Sent to scraping_run').length
      const alreadyQueuedCount = result.results.filter(row => row.message === 'Already queued').length
      const failed = result.results.filter(row => !row.success)
      const summaryParts = [
        queuedCount > 0 ? `Sent ${queuedCount} listing${queuedCount === 1 ? '' : 's'} to scraping_run.` : null,
        alreadyQueuedCount > 0 ? `${alreadyQueuedCount} already queued.` : null,
        failed.length > 0 ? `Failed: ${failed.map(row => `#${row.listing_id} ${row.message}`).join('; ')}` : null,
      ].filter(Boolean)
      const summary = summaryParts.join(' ') || 'No listings were sent to scraping_run.'
      setRerunMessage(summary)
      setSelectedIds([])
      await loadListings()
    } catch (e) {
      setError(String(e))
    } finally {
      setRerunning(false)
    }
  }

  return (
    <div>
      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 mb-4 shadow-sm">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
          <div className="col-span-2 sm:col-span-3 lg:col-span-2">
            <label className="block text-xs font-medium text-gray-500 mb-1">Search (Title + Desc)</label>
            <input
              className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="Search everywhere..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1) }}
            />
          </div>

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
      {rerunMessage && <p className="text-sm text-emerald-700 mb-2">{rerunMessage}</p>}

      <div className="mb-3 flex flex-col gap-2 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-gray-600">
          {selectedIds.length === 0
            ? 'Select listings to queue scraping and AI rating.'
            : `${selectedIds.length} selected.`}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setSelectedIds([])}
            disabled={selectedIds.length === 0 || rerunning}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={() => void handleRerunSelected()}
            disabled={selectedIds.length === 0 || rerunning}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {rerunning ? 'Queueing…' : 'Rerun scraping + AI'}
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-3 py-2 text-left">
                <input
                  type="checkbox"
                  checked={allVisibleSelected}
                  aria-label="Select all visible listings"
                  onChange={toggleSelectVisible}
                  className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-400"
                />
              </th>
              <SortTh col="score" label="Score" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="title" label="Title" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="current_price" label="Price" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="listing_kind" label="Kind" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="availability" label="Status" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="location" label="Location" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="vram" label="VRAM" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="last_seen_at" label="Last seen" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="evaluated_at" label="Evaluated" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Contacted seller</th>
              <SortTh col="user_feedback" label="Feedback" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <SortTh col="user_note" label="Note" sortBy={sortBy} sortDir={sortDir} onSort={handleSort} />
              <th className="px-3 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">Link</th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map(row => (
              <Fragment key={row.id}>
                <tr
                  className="border-b border-gray-100 hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  onClick={() => setExpanded(expanded === row.id ? null : row.id)}
                >
                  <td className="px-3 py-2" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(row.id)}
                      aria-label={`Select listing ${row.id}`}
                      onChange={() => toggleSelected(row.id)}
                      className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-400"
                    />
                  </td>
                  <td className="px-3 py-2"><ScoreBadge score={row.ai?.score ?? null} /></td>
                  <td className="px-3 py-2 max-w-xs">
                    <div className="flex flex-col gap-1">
                      <span className="font-medium text-gray-900 line-clamp-2">{row.title}</span>
                      {row.is_tradera && (
                        <span className="inline-flex items-center self-start px-1.5 py-0.5 rounded text-[10px] font-bold bg-yellow-400 text-black uppercase tracking-tight">
                          Tradera
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap font-mono text-gray-700">{row.current_price}</td>
                  <td className="px-3 py-2">
                    {row.ai?.listing_kind ? (
                      <span className="inline-block px-2 py-0.5 rounded-full text-xs bg-purple-100 text-purple-700">
                        {row.ai.listing_kind}
                      </span>
                    ) : '—'}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                      row.availability === 'Till Salu' ? 'bg-green-100 text-green-700' :
                      row.availability === 'Såld' ? 'bg-orange-100 text-orange-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {row.availability}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-gray-600 max-w-[12rem] truncate">{row.location || '—'}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-600" onClick={e => e.stopPropagation()}>
                    {editingVramId === row.id ? (
                      <div className="flex items-center gap-1">
                        <input
                          value={draftVramOverrides[row.id] ?? ''}
                          onChange={e => setDraftVramOverrides(prev => ({ ...prev, [row.id]: e.target.value }))}
                          placeholder="e.g. 16 GB?"
                          className="w-20 rounded-md border border-gray-300 px-2 py-1 text-xs text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                        />
                        <button
                          type="button"
                          onClick={() => void saveVramOverride(row)}
                          disabled={savingId === row.id}
                          className="rounded-md border border-emerald-300 bg-emerald-50 px-1.5 py-1 text-[11px] text-emerald-700 hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
                          aria-label={`Save VRAM override for listing ${row.id}`}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => cancelEditingVram(row)}
                          disabled={savingId === row.id}
                          className="rounded-md border border-gray-300 bg-white px-1.5 py-1 text-[11px] text-gray-600 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
                          aria-label={`Cancel VRAM override editing for listing ${row.id}`}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <span>{row.vram || '—'}</span>
                        <button
                          type="button"
                          onClick={() => startEditingVram(row)}
                          className="inline-flex h-5 w-5 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 hover:border-indigo-300 hover:text-indigo-600"
                          aria-label={`Edit VRAM for listing ${row.id}`}
                          title="Edit VRAM"
                        >
                          <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5" aria-hidden="true">
                            <path d="M14.69 2.86a1.5 1.5 0 0 1 2.12 2.12l-8.36 8.36-3.16.53.53-3.16 8.87-8.85Zm-8.06 8.87-.2 1.19 1.19-.2 7.95-7.95-1-1-7.94 7.96Z" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">{fmtDate(row.last_seen_at)}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-gray-500 text-xs">{fmtDate(row.ai?.evaluated_at ?? null)}</td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {row.contacted_seller ? (
                      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                        Yes
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={e => {
                          e.stopPropagation()
                          markSellerContacted(row)
                        }}
                        disabled={savingId === row.id}
                        className="rounded-lg border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-800 hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {savingId === row.id ? 'Saving…' : 'Contacted?'}
                      </button>
                    )}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                      row.user_feedback === 'up'
                        ? 'bg-emerald-100 text-emerald-700'
                        : row.user_feedback === 'down'
                          ? 'bg-rose-100 text-rose-700'
                          : 'bg-gray-100 text-gray-500'
                    }`}>
                      {row.user_feedback === 'up' ? 'Thumbs up' : row.user_feedback === 'down' ? 'Thumbs down' : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 max-w-[14rem]">
                    <span className="block text-xs text-gray-600 truncate">{row.user_note || '—'}</span>
                  </td>
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
                    <td colSpan={14} className="px-4 py-4">
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                        <div>
                          <h3 className="font-semibold text-gray-700 mb-1">Listing</h3>
                          <dl className="space-y-1 text-gray-600">
                            <div><dt className="inline font-medium">ID: </dt><dd className="inline">{row.id}</dd></div>
                            <div><dt className="inline font-medium">Key: </dt><dd className="inline font-mono text-xs">{row.listing_key}</dd></div>
                             <div><dt className="inline font-medium">Marketplace: </dt><dd className="inline">{row.marketplace}</dd></div>
                            <div><dt className="inline font-medium">Availability: </dt><dd className="inline font-bold">{row.availability}</dd></div>
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
                      <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-start">
                        <div>
                          <p className="font-semibold text-gray-700 mb-1">Make a note</p>
                          <textarea
                            value={draftNotes[row.id] ?? row.user_note ?? ''}
                            onClick={e => e.stopPropagation()}
                            onChange={e => setDraftNotes(prev => ({ ...prev, [row.id]: e.target.value }))}
                            rows={4}
                            placeholder="Add your own comment for this listing..."
                            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                          />
                          <div className="mt-2 flex gap-2">
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation()
                                void saveListingUpdates(row, {
                                  user_note: draftNotes[row.id] ?? '',
                                  user_feedback: draftFeedback[row.id] ?? null,
                                  vram_override: (draftVramOverrides[row.id] ?? '').trim() || null,
                                  contacted_seller: draftContactedSeller[row.id] ?? row.contacted_seller,
                                })
                              }}
                              disabled={savingId === row.id}
                              className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {savingId === row.id ? 'Saving…' : 'Save'}
                            </button>
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation()
                                setDraftNotes(prev => ({ ...prev, [row.id]: row.user_note ?? '' }))
                                setDraftFeedback(prev => ({ ...prev, [row.id]: row.user_feedback }))
                                setDraftVramOverrides(prev => ({ ...prev, [row.id]: row.vram_override ?? '' }))
                                setDraftContactedSeller(prev => ({ ...prev, [row.id]: row.contacted_seller }))
                              }}
                              className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                            >
                              Reset
                            </button>
                          </div>
                        </div>
                        <div>
                          <p className="font-semibold text-gray-700 mb-1">Seller contact</p>
                          <label className="flex items-center gap-2 text-sm text-gray-700">
                            <input
                              type="checkbox"
                              checked={draftContactedSeller[row.id] ?? row.contacted_seller}
                              onClick={e => e.stopPropagation()}
                              onChange={e => setDraftContactedSeller(prev => ({ ...prev, [row.id]: e.target.checked }))}
                              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-400"
                            />
                            Contacted seller
                          </label>
                        </div>
                        <div>
                          <p className="font-semibold text-gray-700 mb-1">Teach the model</p>
                          <div className="flex gap-2">
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation()
                                toggleFeedback(row, 'up')
                              }}
                              className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                                (draftFeedback[row.id] ?? row.user_feedback) === 'up'
                                  ? 'border-emerald-300 bg-emerald-100 text-emerald-800'
                                  : 'border-gray-300 bg-white text-gray-700 hover:bg-emerald-50'
                              }`}
                            >
                              Thumbs up
                            </button>
                            <button
                              type="button"
                              onClick={e => {
                                e.stopPropagation()
                                toggleFeedback(row, 'down')
                              }}
                              className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                                (draftFeedback[row.id] ?? row.user_feedback) === 'down'
                                  ? 'border-rose-300 bg-rose-100 text-rose-800'
                                  : 'border-gray-300 bg-white text-gray-700 hover:bg-rose-50'
                              }`}
                            >
                              Thumbs down
                            </button>
                          </div>
                          <p className="mt-2 text-xs text-gray-500">
                            Click the same thumb again to clear it.
                          </p>
                          {feedbackError && (
                            <p className="mt-2 text-xs text-red-600">{feedbackError}</p>
                          )}
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
            {!loading && data?.items.length === 0 && (
              <tr><td colSpan={14} className="px-4 py-8 text-center text-gray-400">No listings match the current filters.</td></tr>
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
