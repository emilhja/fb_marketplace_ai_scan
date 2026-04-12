import { useState } from 'react'
import ListingsPage from './pages/ListingsPage'
import NotificationsPage from './pages/NotificationsPage'
import PriceHistoryPage from './pages/PriceHistoryPage'

type Tab = 'listings' | 'price_history' | 'notifications'

const TABS: { id: Tab; label: string; emoji: string }[] = [
  { id: 'listings', label: 'Listings + AI', emoji: '🔍' },
  { id: 'price_history', label: 'Price History', emoji: '📈' },
  { id: 'notifications', label: 'Notifications', emoji: '🔔' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('listings')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 flex items-center gap-6 h-14">
          <span className="font-bold text-gray-800 text-base tracking-tight whitespace-nowrap">
            FB Marketplace Dashboard
          </span>
          <nav className="flex gap-1">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  tab === t.id
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {t.emoji} {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 py-6">
        <h1 className="text-lg font-semibold text-gray-800 mb-4">
          {TABS.find(t => t.id === tab)?.label}
        </h1>
        {tab === 'listings' && <ListingsPage />}
        {tab === 'price_history' && <PriceHistoryPage />}
        {tab === 'notifications' && <NotificationsPage />}
      </main>
    </div>
  )
}
