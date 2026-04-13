import { Route, Routes } from 'react-router-dom'
import DataSearchPage from './pages/DataSearchPage'
import HomePage from './pages/HomePage'
import Dashboard from './pages/Dashboard'
import AdminPage from './pages/AdminPage'
import AboutPage from './pages/AboutPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/data" element={<DataSearchPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/about" element={<AboutPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route path="/supersecretbackdoor" element={<AdminPage />} />
    </Routes>
  )
}

export default App
