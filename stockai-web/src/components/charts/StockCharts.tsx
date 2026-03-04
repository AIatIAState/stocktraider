import {Grid, InputLabel} from "@mui/material";
import type {Bar} from "../../services/api.ts";
import StockScatterChart from "./StockScatterChart.tsx";
import {useMemo, useState} from "react";
import StockBarChart from "./StockBarChart.tsx";
import { StockPieChart } from "./StockPieChart.tsx";
import Box from "@mui/material/Box";
import FormControl from "@mui/material/FormControl";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";

interface StockChartsProps {
    bars: Bar[],
    symbol: string
}
const oneMonthAgo = new Date()
oneMonthAgo.setDate(oneMonthAgo.getDate() - 30)

function getDateFromYYYYMMDD(yyyymmdd: string): Date {

    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}

export function StockCharts(props : StockChartsProps) {
    const [startDate, setStartDate] = useState<Date>(oneMonthAgo)
    const chartBars = useMemo(() => {
        const chartBars: Bar[] = []
        props.bars.forEach((bar) => {
            const barDate = getDateFromYYYYMMDD(bar.date.toString())
            if(barDate >= startDate){
                chartBars.push(bar)
            }
        })
        return chartBars
    }, [props.bars, startDate, props.symbol])
    if(props.bars.length == 0){
        if(startDate.getDate() != oneMonthAgo.getDate()){
            setStartDate(oneMonthAgo)
        }
        return <></>
    }

    const today = new Date()


    return (<>
            <Box sx={{ ml: 'auto' }}>
                <FormControl size="small">
                    <InputLabel>Timeframe</InputLabel>
                    <Select
                        label="Timeframe"
                        defaultValue="1 Month"
                        sx={{
                          borderRadius: 2,
                          minWidth: 130,
                          '& .MuiOutlinedInput-notchedOutline': { borderColor: 'divider' },
                        }}
                        onChange={(e) => {
                            if(e.target.value === "All Time") {
                                setStartDate(getDateFromYYYYMMDD(props.bars[0]?.date.toString()))
                                return
                            }
                            const newDate = new Date()
                            newDate.setDate(
                                e.target.value === "1 Week" ? today.getDate() - 7 :
                                e.target.value === "1 Month" ? today.getDate() - 30 :
                                e.target.value === "3 Months" ? today.getDate() - 92 :
                                e.target.value === "6 Months" ? today.getDate() - 183 :
                                e.target.value === "1 Year" ? today.getDate() - 365 :
                                today.getDate() - 1825 // 5 Years
                            )
                        setStartDate(newDate)
                    }}>
                        <MenuItem value={"1 Week"}>1 Week</MenuItem>
                        <MenuItem value={"1 Month"}>1 Month</MenuItem>
                        <MenuItem value={"3 Months"}>3 Months</MenuItem>
                        <MenuItem value={"6 Months"}>6 Months</MenuItem>
                        <MenuItem value={"1 Year"}>1 Year</MenuItem>
                        <MenuItem value={"5 Years"}>5 Years</MenuItem>
                        <MenuItem value={"All Time"}>All Time</MenuItem>
                    </Select>
                </FormControl>
            </Box>
        <Grid container spacing={2} columns={12}>

            <Grid size={{ xs: 12, md: 8 }}>
                <StockBarChart bars={chartBars}/>
            </Grid>

            <Grid size={{ xs: 12, md: 4}}>
                <StockPieChart bars={chartBars}/>
            </Grid>
            <Grid size={{ xs: 12}}>
                <StockScatterChart size={"big"} symbol={props.symbol} bars={chartBars as unknown as [{date: number, open: number}]}/>
            </Grid>
        </Grid>
        </>
    )
}

