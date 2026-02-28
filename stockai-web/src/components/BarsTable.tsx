import {
    Box, Button, Card, CardContent, Divider, Paper, Stack, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, Typography
} from "@mui/material";
import type {Bar} from "../services/api.ts";
import {useState} from "react";
import { formatSymbol } from "../utils/formatSymbol";

interface BarsTableProps {
    bars: Bar[]
}

function formatDate(value: number) {
    const str = String(value)
    return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
}
function formatTime(value: number) {
    const str = String(value).padStart(6, '0')
    return `${str.slice(0, 2)}:${str.slice(2, 4)}`
}

export function BarsTable(props: BarsTableProps) {
    const [ barsPageIndex, setBarsPageIndex ] = useState(0)
    const barsPerPage = 25
    if(props.bars.length === 0){
        return <></>
    }
    const reversedBars = props.bars.slice().reverse()
    const symbol = formatSymbol(props.bars[0].symbol)
    let maxHigh = 0
    let minLow = 99999999999
    props.bars.forEach((bar) => {
        if(bar.high != null && bar.high > maxHigh){
            maxHigh = bar.high
        }
        if(bar.low != null && bar.low < minLow){
            minLow = bar.low
        }
    })

    return <Card>
        <CardContent>
            <Typography variant="h5" gutterBottom>
                Recent bars
            </Typography>
                <Stack spacing={2}>
                    <Stack direction={{xs: 'column', sm: 'row'}} spacing={2} alignItems="center">
                        <Box>
                            <Typography variant="body2" color="text.secondary">
                                Symbol
                            </Typography>
                            <Typography variant="h6">{symbol}</Typography>
                        </Box>
                        <Divider orientation="vertical" flexItem sx={{display: {xs: 'none', sm: 'block'}}}/>
                            <Stack direction={{xs: 'column', sm: 'row'}} spacing={2}>
                                <Box>
                                    <Typography variant="body2" color="text.secondary">
                                        Bars loaded
                                    </Typography>
                                    <Typography variant="h6">{props.bars.length}</Typography>
                                </Box>
                                <Box>
                                    <Typography variant="body2" color="text.secondary">
                                        Last close
                                    </Typography>
                                    <Typography variant="h6">{props.bars[props.bars.length - 1].close}</Typography>
                                </Box>
                                <Box>
                                    <Typography variant="body2" color="text.secondary">
                                        High / Low
                                    </Typography>
                                    <Typography variant="h6">
                                        {maxHigh.toFixed(2)} / {minLow.toFixed(2)}
                                    </Typography>
                                </Box>
                            </Stack>
                    </Stack>

                    <Stack
                        direction={{xs: 'column', sm: 'row'}}
                        spacing={2}
                        alignItems={{xs: 'flex-start', sm: 'center'}}
                        justifyContent="space-between"
                    >
                        <Typography variant="body2" color="text.secondary">
                            Showing {barsPageIndex + 1} of {Math.ceil(props.bars.length / barsPerPage)} pages
                        </Typography>
                        <Stack direction="row" spacing={1} alignItems="center">
                                <Button value="previous" disabled={barsPageIndex === 0} onClick={() => setBarsPageIndex(barsPageIndex - 1)}>Previous</Button>
                                <Button value="next" disabled={barsPageIndex === Math.ceil(props.bars.length / barsPerPage) - 1} onClick={() => setBarsPageIndex(barsPageIndex + 1)}>Next</Button>
                        </Stack>
                    </Stack>

                        <TableContainer component={Paper}>
                            <Table size="small" stickyHeader>
                                <TableHead>
                                    <TableRow>
                                        <TableCell>Date</TableCell>
                                        <TableCell>Time</TableCell>
                                        <TableCell>Open</TableCell>
                                        <TableCell>High</TableCell>
                                        <TableCell>Low</TableCell>
                                        <TableCell>Close</TableCell>
                                        <TableCell>Volume</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {reversedBars.slice(barsPageIndex * barsPerPage, (barsPageIndex + 1) * barsPerPage).map((bar) => (
                                        <TableRow key={`${bar.symbol}-${bar.date}-${bar.time}`}>
                                            <TableCell>{formatDate(bar.date)}</TableCell>
                                            <TableCell>{bar.time ? formatTime(bar.time) : 'N/A'}</TableCell>
                                            <TableCell>{bar.open?.toFixed(2) ?? 'N/A'}</TableCell>
                                            <TableCell>{bar.high?.toFixed(2) ?? 'N/A'}</TableCell>
                                            <TableCell>{bar.low?.toFixed(2) ?? 'N/A'}</TableCell>
                                            <TableCell>{bar.close?.toFixed(2) ?? 'N/A'}</TableCell>
                                            <TableCell>{bar.volume?.toFixed(0) ?? 'N/A'}</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                </Stack>
        </CardContent>
    </Card>
}
