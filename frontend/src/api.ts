// Thin fetch wrapper — all calls go through Vite proxy to http://127.0.0.1:8000

export interface PagedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ---------- Listings + latest AI ----------
export interface LatestAIEval {
  eval_id: number | null
  score: number | null
  conclusion: string | null
  comment: string | null
  listing_kind: string | null
  model: string | null
  response_model: string | null
  evaluated_at: string | null
}

export interface ListingRow {
  id: number
  listing_key: string
  marketplace: string
  marketplace_listing_id: string
  canonical_post_url: string
  title: string
  current_price: string
  original_price: string
  description: string
  location: string
  skick: string
  first_seen_at: string
  last_seen_at: string
  ai: LatestAIEval | null
}

export interface ListingsParams {
  page?: number
  page_size?: number
  title?: string
  score_min?: number | ''
  score_max?: number | ''
  listing_kind?: string
  marketplace?: string
  last_seen_from?: string
  last_seen_to?: string
  evaluated_from?: string
  evaluated_to?: string
  sort_by?: string
  sort_dir?: 'asc' | 'desc'
}

export async function fetchListings(params: ListingsParams): Promise<PagedResponse<ListingRow>> {
  const q = buildQuery(params as Record<string, unknown>)
  const res = await fetch(`/api/listings?${q}`)
  if (!res.ok) throw new Error(`listings: ${res.status}`)
  return res.json()
}

// ---------- Price history ----------
export interface PriceHistoryRow {
  id: number
  listing_id: number
  listing_title: string | null
  canonical_post_url: string | null
  price: string
  observed_at: string
}

export interface PriceHistoryParams {
  page?: number
  page_size?: number
  listing_id?: number | ''
  observed_from?: string
  observed_to?: string
  sort_dir?: 'asc' | 'desc'
}

export async function fetchPriceHistory(params: PriceHistoryParams): Promise<PagedResponse<PriceHistoryRow>> {
  const q = buildQuery(params as Record<string, unknown>)
  const res = await fetch(`/api/listing-price-history?${q}`)
  if (!res.ok) throw new Error(`price-history: ${res.status}`)
  return res.json()
}

// ---------- Notification events ----------
export interface NotificationEventRow {
  id: number
  listing_id: number
  listing_title: string | null
  canonical_post_url: string | null
  user_name: string
  channel: string
  status: string
  details: unknown | null
  sent_at: string
}

export interface NotificationParams {
  page?: number
  page_size?: number
  listing_id?: number | ''
  channel?: string
  status?: string
  sent_from?: string
  sent_to?: string
  sort_dir?: 'asc' | 'desc'
}

export async function fetchNotifications(params: NotificationParams): Promise<PagedResponse<NotificationEventRow>> {
  const q = buildQuery(params as Record<string, unknown>)
  const res = await fetch(`/api/notification-events?${q}`)
  if (!res.ok) throw new Error(`notifications: ${res.status}`)
  return res.json()
}

// ---------- Helpers ----------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildQuery(params: Record<string, any>): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') {
      p.set(k, String(v))
    }
  }
  return p.toString()
}
