import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { postWhatIf, type WhatIfResponse } from '../services/api'

function DeltaChip({ delta }: { delta: number }) {
  const pct = (delta * 100).toFixed(2)
  const color = delta > 0 ? 'success' : delta < 0 ? 'error' : 'default'
  const label = delta >= 0 ? `+${pct}%` : `${pct}%`
  return <Chip label={label} color={color} size="small" />
}

function ResultTable({ response }: { response: WhatIfResponse }) {
  return (
    <Stack spacing={1.5} mt={1}>
      <Typography variant="subtitle2" color="text.secondary">
        {response.scenario_summary}
      </Typography>
      {response.predictions.map((p) => (
        <Box
          key={p.ticker}
          sx={{
            p: 1.5,
            borderRadius: 1,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
            <Typography variant="body2" fontWeight={600}>
              {p.ticker}
            </Typography>
            <DeltaChip delta={p.delta} />
            <Tooltip title={`Confidence: ${(p.confidence * 100).toFixed(0)}%`}>
              <Typography variant="caption" color="text.disabled">
                {(p.confidence * 100).toFixed(0)}% conf.
              </Typography>
            </Tooltip>
          </Stack>
          <Typography variant="caption" color="text.secondary">
            {p.narrative}
          </Typography>
        </Box>
      ))}
      <Typography variant="caption" color="text.disabled" mt={1}>
        {response.disclaimer}
      </Typography>
    </Stack>
  )
}

export default function WhatIfCard() {
  const [scenario, setScenario] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<WhatIfResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit() {
    if (!scenario.trim()) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const response = await postWhatIf({ scenario: scenario.trim() })
      setResult(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>
          What If? Scenario Explorer
        </Typography>
        <Typography variant="body2" color="text.secondary" mb={2}>
          Describe a hypothetical geopolitical event and see its predicted impact on key stocks.
        </Typography>
        <Stack direction="row" spacing={1} alignItems="flex-start">
          <TextField
            fullWidth
            size="small"
            placeholder='e.g. "US imposes 25% tariffs on Chinese semiconductors"'
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSubmit()}
            disabled={loading}
          />
          <Button
            variant="contained"
            size="small"
            onClick={handleSubmit}
            disabled={loading || !scenario.trim()}
            sx={{ whiteSpace: 'nowrap', minWidth: 80 }}
          >
            {loading ? <CircularProgress size={16} color="inherit" /> : 'Analyze'}
          </Button>
        </Stack>
        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}
        {result && <ResultTable response={result} />}
      </CardContent>
    </Card>
  )
}
