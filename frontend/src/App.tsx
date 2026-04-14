import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import ListingsPage from './pages/ListingsPage'
import NotificationsPage from './pages/NotificationsPage'
import PriceHistoryPage from './pages/PriceHistoryPage'

const TABS: { path: string; label: string; emoji: string }[] = [
  { path: '/listings', label: 'Listings + AI', emoji: '🔍' },
  { path: '/price-history', label: 'Price History', emoji: '📈' },
  { path: '/notifications', label: 'Notifications', emoji: '🔔' },
]

export default function App() {
  const [wideScreenMode, setWideScreenMode] = useState(
    () => window.localStorage.getItem('wide-screen-mode') === 'true'
  )

  useEffect(() => {
    window.localStorage.setItem('wide-screen-mode', String(wideScreenMode))
  }, [wideScreenMode])

  const shellWidthClass = wideScreenMode ? 'w-full' : 'max-w-screen-2xl'

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-10">
          <div className={`${shellWidthClass} mx-auto px-4 sm:px-6 flex items-center justify-between gap-4 h-14`}>
            <div className="flex items-center gap-6 min-w-0">
              <span className="font-bold text-gray-800 text-base tracking-tight whitespace-nowrap">
                FB Marketplace Dashboard
              </span>
              <nav className="flex gap-1 overflow-x-auto">
                {TABS.map(t => (
                  <NavLink
                    key={t.path}
                    to={t.path}
                    className={({ isActive }) => `px-4 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
                      isActive
                        ? 'bg-indigo-600 text-white shadow-sm'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    {t.emoji} {t.label}
                  </NavLink>
                ))}
              </nav>
            </div>
            <button
              type="button"
              onClick={() => setWideScreenMode(current => !current)}
              className={`shrink-0 rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                wideScreenMode
                  ? 'border-indigo-600 bg-indigo-600 text-white hover:bg-indigo-500'
                  : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              Wide Screen Mode
            </button>
          </div>
        </header>

        {/* Page content */}
        <main className={`${shellWidthClass} mx-auto px-4 sm:px-6 py-6`}>
          <Routes>
            <Route path="/listings" element={<ListingsPage />} />
            <Route path="/price-history" element={<PriceHistoryPage />} />
            <Route path="/notifications" element={<NotificationsPage />} />
            <Route path="*" element={<Navigate to="/listings" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
