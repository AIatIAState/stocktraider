import { Route, Routes } from 'react-router-dom'
import DataSearchPage from './pages/DataSearchPage'
import HomePage from './pages/HomePage'
import Dashboard from './pages/Dashboard'

function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/data" element={<DataSearchPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
    </Routes>
  )
}

export default App
