import { Box, Container } from '@mui/material'
import { useState } from 'react'
import { type Bar } from '../services/api'
import AppAppBar from '../components/AppAppBar'
import Footer from '../components/Footer'
import StockSearch from '../components/StockSearch.tsx'
import { StockCharts } from '../components/charts/StockCharts.tsx'
import { BarsTable } from '../components/BarsTable.tsx'
import SimilarCharts from '../components/charts/SimilarCharts.tsx'
import { ForecastCharts } from '../components/charts/ForecastCharts.tsx'
import PageHeader from '../components/PageHeader'
import { GradientText } from '../themes/styles'
import {StockConditions} from "../components/charts/StockConditions.tsx";

export default function DataSearchPage() {
  const [bars, setBars] = useState<Bar[]>([])
  const [symbol, setSymbol] = useState('')

  return (
    <>
      <AppAppBar />
      <PageHeader
        overline="Market Data Explorer"
        title={<>Search tickers and inspect <GradientText>OHLCV</GradientText> history.</>}
        description="Search for stock symbols and load historical price data directly from our database."
      />
      <Container maxWidth="lg" sx={{ py: { xs: 4, md: 6 } }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <StockSearch setBars={setBars} setSymbol={setSymbol} />
          <StockCharts bars={bars} symbol={symbol} />
          <StockConditions symbol={symbol}/>
          <SimilarCharts bars={bars} symbol={symbol} />
          <ForecastCharts symbol={symbol} />
          <BarsTable bars={bars} />
        </Box>
      </Container>
      <Footer />
    </>
  )
}
