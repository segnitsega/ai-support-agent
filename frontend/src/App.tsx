import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { AdminPage } from './components/AdminPage'
import { ChatPage } from './components/ChatPage'
import { DashboardPage } from './components/DashboardPage'
import { Layout } from './components/Layout'
import './App.css'

/** Keep Chat mounted across nav so messages / ticket polling survive. */
function AppRoutes() {
  const { pathname } = useLocation()
  const onChat = pathname === '/'

  return (
    <>
      <div hidden={!onChat}>
        <ChatPage />
      </div>
      <Routes>
        <Route path="/" element={null} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <AppRoutes />
      </Layout>
    </BrowserRouter>
  )
}
