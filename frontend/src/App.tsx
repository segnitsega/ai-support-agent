import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AdminPage } from './components/AdminPage'
import { ChatPage } from './components/ChatPage'
import { DashboardPage } from './components/DashboardPage'
import { Layout } from './components/Layout'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
