import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { getToken, setToken } from './api'
import Boot from './Boot'
import Layout from './Layout'
import AttemptPage from './pages/Attempt'
import Dashboard from './pages/Dashboard'
import Home from './pages/Home'
import TokenGate from './TokenGate'

export default function App() {
  const [booted, setBooted] = useState(false)
  const [token, setTok] = useState<string | null>(getToken())

  // Qualquer 401 da API derruba o token guardado e volta para a tela de token.
  useEffect(() => {
    const onUnauthorized = () => { setToken(null); setTok(null) }
    window.addEventListener('studies:unauthorized', onUnauthorized)
    return () => window.removeEventListener('studies:unauthorized', onUnauthorized)
  }, [])

  if (!booted) return <Boot onReady={() => setBooted(true)} />
  if (!token) return <TokenGate onSave={(t) => { setToken(t); setTok(t) }} />
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout onLogout={() => { setToken(null); setTok(null) }} />}>
          <Route index element={<Home />} />
          <Route path="attempts/:id" element={<AttemptPage />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
