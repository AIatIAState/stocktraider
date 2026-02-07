
import AppAppBar from '../components/AppAppBar'
import AppTheme from '../themes/AppTheme'
import { useState} from 'react'
import { type Bar } from '../services/api'

export default function AdminPage(props: { disableCustomTheme?: boolean }) {
  return (
    <AppTheme {...props}>
      <AppAppBar />
    </AppTheme>
  )
}
