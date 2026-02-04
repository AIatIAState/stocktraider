import {
  Box,
  Card,
  CardContent,
  Container,
  Stack,
  Typography,
} from '@mui/material'
import { useState} from 'react'
import { type Bar } from '../services/api'
import AppTheme from '../themes/AppTheme'
import AppAppBar from '../components/AppAppBar'
import Footer from '../components/Footer'
import StockSearch from "../components/StockSearch.tsx";
import {StockCharts} from "../components/charts/StockCharts.tsx";
import {BarsTable} from "../components/BarsTable.tsx";
import SimilarCharts from "../components/charts/SimilarCharts.tsx";
import {ForecastCharts} from "../components/charts/ForecastCharts.tsx";



export default function DataSearchPage(props: { disableCustomTheme?: boolean }) {
  const [bars, setBars] = useState<Bar[]>([])
    const [ symbol, setSymbol ] = useState("")

  return (
    <AppTheme {...props}>
      <AppAppBar />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Typography variant="overline">
                  Market Data Explorer
                </Typography>
                <Typography variant="h3">Search tickers and inspect OHLCV history.</Typography>
                <Typography variant="body1" color="text.secondary">
                  Search for stock symbols and load historical price data directly from our database.
                </Typography>
              </Stack>
            </CardContent>
          </Card>
            <StockSearch setBars={setBars} setSymbol={setSymbol}/>
            <StockCharts bars={bars} symbol={symbol}/>
            <SimilarCharts bars={bars} symbol={symbol}/>
            <ForecastCharts symbol={symbol}/>
            <BarsTable bars={bars}/>
        </Box>
      </Container>
      <Footer />
    </AppTheme>
  )
}
