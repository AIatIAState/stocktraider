import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import AppTheme from './themes/AppTheme.tsx'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppTheme>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AppTheme>
  </StrictMode>,
)
