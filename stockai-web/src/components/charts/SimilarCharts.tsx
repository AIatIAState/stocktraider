import {
    Accordion, AccordionDetails,
    AccordionSummary, Button, Card, CardContent,
    Container,
    Paper,
    Table, TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography
} from "@mui/material"
import {fetchStockPatterns, type StockPattern} from "../../services/StockPatternService"
import {useEffect, useState} from "react";
import type { Bar } from "../../services/api.ts";
import {HistoricalPattern} from "./HistoricalPattern.tsx";
import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import {GradientCircularProgress} from "../GradientCircularProgress.tsx";
import { formatSymbol } from "../../utils/formatSymbol";
import ExpandMoreRoundedIcon from "@mui/icons-material/ExpandMoreRounded";

interface SimilarChartsProps {
    symbol: string
    bars: Bar[]
}
function getDateFromYYYYMMDD(yyyymmdd: string): Date {
    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}

function getStartDate(bars: Bar[], trendLength: number){
    const endTrendDate = getDateFromYYYYMMDD(bars[bars.length - 1].date.toString())
    const startTrendDate = new Date()
    startTrendDate.setDate(endTrendDate.getDate() - trendLength)
    return startTrendDate
}
async function getPatterns(symbol:string, trendLength: number, setLoading: (data: boolean) => void) {
    setLoading(true)
    const response = await fetchStockPatterns(symbol, "daily", trendLength)
    const patterns: StockPattern[] = response['results']
    const recentPatterns: StockPattern[] = []
    patterns.forEach((pattern) => {
        const tenYearsAgo = new Date()
        tenYearsAgo.setDate(tenYearsAgo.getDate() - 365 * 10)
        if(getDateFromYYYYMMDD(pattern.starting_date.toString()) >= tenYearsAgo){
            recentPatterns.push(pattern)
        }
    })
    setLoading(false)
    return recentPatterns
}

function SimilarCharts(props: SimilarChartsProps){
    const [ patterns, setPatterns ] = useState<StockPattern[]>(null as unknown as StockPattern[])
    const [ loading, setLoading ] = useState(false)
    const [ patternPageIndex, setPatternPageIndex ] = useState(0)
    const patternsPerPage = 10
    const trendLength = 7
    useEffect(() => {
        if(props.symbol === ""){
            return
        }
        getPatterns(props.symbol, trendLength, setLoading).then((response) => setPatterns(response))
    }, [props.symbol])
    if(props.symbol=== ""){
        return <></>
    }


    const displaySymbol = formatSymbol(props.symbol)
    if(patterns === null && !loading){
        return <></>
    }
    if (loading) {
        return (
            <Card sx={{ borderRadius: 3 }}>
                <CardContent>
                    <Stack direction="row" alignItems="center" spacing={2}>
                        <Typography variant="h4">Historical Trend Analysis</Typography>
                        <GradientCircularProgress />
                    </Stack>
                </CardContent>
            </Card>
        );
    }
    else if(patterns != null && patterns.length === 0){
        return <Card sx={{ borderRadius: 3 }}>
            <CardContent>
                <Stack direction="row" alignItems="center" spacing={2}>
                    <Typography variant="h4">Historical Trend Analysis</Typography>
                    <Typography variant={'h6'}>This week's prices of {displaySymbol} stock is not mathematically aligned with historical data.</Typography>
                </Stack>
            </CardContent>
        </Card>
    }
    return <>
        {
            <Accordion
                disableGutters
                elevation={0}
                sx={{
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: '12px !important',
                    '&::before': { display: 'none' },
                }}
            >
                <AccordionSummary
                    expandIcon={<ExpandMoreRoundedIcon sx={{ color: 'text.secondary' }} />}
                    sx={{ px: 3, py: 1 }}
                >
                    <Stack direction="row" alignItems="center" spacing={2} flexWrap="wrap">
                        <Typography variant="h4">Historical Trend Analysis</Typography>
                        <Typography variant="h6" color="text.secondary">
                            View the most similar week segments of {displaySymbol}
                        </Typography>
                    </Stack>
                        </AccordionSummary>
                <AccordionDetails sx={{ px: 3, pb: 3 }}>
                    <Container maxWidth="xl" sx={{ py: 4, pb: 8 }}>
                        <Box sx={{ display: "flex", justifyContent: "flex-end", p: 2 }}>
                            <Stack direction="row" style={{paddingBottom:'16px'}}>
                                <Button value="previous" disabled={patternPageIndex === 0} onClick={() => setPatternPageIndex(patternPageIndex - 1)}>Previous</Button>
                                <Button value="next" disabled={patternPageIndex === Math.ceil(props.bars.length / patternsPerPage) - 1} onClick={() => setPatternPageIndex(patternPageIndex + 1)}>Next</Button>
                            </Stack>
                        </Box>
                        <TableContainer component={Paper}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <Box
                                            sx={{
                                                display: "grid",
                                                gridTemplateColumns: "2fr 3fr 3fr 1fr",
                                                gap: 2
                                            }}
                                            style={{paddingTop:'16px'}}
                                            alignItems={'end'}
                                        >
                                            <TableCell><Typography variant={'h6'}>Similar Week</Typography></TableCell>
                                            <TableCell><Typography variant={'h6'}>Similar Trend</Typography></TableCell>
                                            <TableCell><Typography variant={'h6'}>Proceeding Week</Typography></TableCell>
                                            <TableCell><Typography variant={'h6'}>Similarity</Typography></TableCell>
                                        </Box>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {patterns.slice(patternPageIndex * patternsPerPage, (patternPageIndex + 1) * patternsPerPage).map((pattern) => (
                                        <TableRow>
                                            <HistoricalPattern trendLength={trendLength} bars={props.bars} currentTrendStartDate={getStartDate(props.bars, trendLength)} historicalTrendStartDate={getDateFromYYYYMMDD(pattern.starting_date.toString())} similarityScore={pattern.similarity_score}/>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Container>
                </AccordionDetails>
                    </Accordion>}
    </>
}

export default SimilarCharts
