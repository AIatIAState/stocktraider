import {fetchStockHistory, fetchStockSymbols} from "../services/StockHistoryService.tsx";
import {type ReactElement, useState} from "react";
import Box from "@mui/material/Box";
import { Button, Card, CardContent, Stack, TextField, Typography} from "@mui/material";
import type {Bar, SymbolInfo} from "../services/api.ts";
import Grid from "@mui/material/Grid";
import {GradientCircularProgress} from "./GradientCircularProgress.tsx";
import { formatSymbol } from "../utils/formatSymbol";


export interface StockSearchProps {
    setBars: (data: Bar[]) => void
    setSymbol: (data: string) => void
}
export default function StockSearch(props: StockSearchProps) {
    const [symbolData, setSymbolData] = useState<SymbolInfo[]>([])
    const [searchValue, setSearchValue] = useState<string>("")
    const [loading, setLoading] = useState<boolean>(false)

    function getAutocompleteSymbols(symbolList: SymbolInfo[]) {
        if (searchValue == "" && symbolData.length === 0){
            return <Stack spacing={1}>
                <br/>
                <Typography color="text.secondary">Search for a ticker to view its data.</Typography>
                <br/>
            </Stack>
        }
        if (searchValue == ""){
            return <></>
        }
        const symbolSelectElements : ReactElement[] = []
        symbolList.forEach((symbol) => {symbolSelectElements.push(
            <Button
                key={symbol.symbol}
                variant={'outlined'}
                onClick={() => {
                    getSymbolData(symbol.symbol)
                    setSearchValue("")
                }}
                sx={{ justifyContent: 'space-between' }}
            >
                <Box width={'120px'} sx={{ textAlign: 'left' }}>
                    <Typography>{formatSymbol(symbol.symbol)}</Typography>
                    <Typography variant="caption" color="text.secondary">
                        {(symbol.exchange || 'N/A').toUpperCase()} | {symbol.asset_type ?? 'asset'}
                    </Typography>
                </Box>
            </Button>
        )})
        return <>
            <Typography color="text.primary">Matched Tickers</Typography>
            <br/>
            <Grid container spacing={4}>
                {symbolSelectElements}
             </Grid>
            <br/>
            </>
    }

    async function updateAutocompleteSymbols(searchValue: string){
        // @ts-ignore
        setSymbolData((await fetchStockSymbols(searchValue, 12))['results'])
    }
    async function getSymbolData(symbol: string) {
        setLoading(true)
        setSearchValue("")
        props.setBars([])
        props.setSymbol("")
        const response = await fetchStockHistory(symbol, "daily")
        props.setBars(response.results)
        props.setSymbol(response.results[0].symbol)
        setLoading(false)

    }



    return (
        <>
            <Card>
                <CardContent>
                    <Stack spacing={2}>
                        <Stack direction={{ xs: 'column', md: 'row' }} spacing={2} alignItems="flex-end">
                            <TextField
                                label="Symbol search"
                                value={searchValue}
                                placeholder="AAPL, TSLA, SPY"
                                fullWidth
                                onChange={async (e) => {
                                    setSearchValue(e.target.value)
                                    if(e.target.value == '') {
                                        return
                                    }
                                    await updateAutocompleteSymbols(e.target.value)
                                }}
                            />
                        </Stack>
                    </Stack>
                </CardContent>
            </Card>
            {loading && <Box alignSelf={'center'}><GradientCircularProgress/></Box>}
            <Card style={{paddingLeft: '16px', paddingRight: '16px'}}>
                {getAutocompleteSymbols(symbolData)}
            </Card>
        </>

    );
}
