import {useEffect, useState} from "react";
import Stack from "@mui/material/Stack";
import {
    Accordion,
    AccordionSummary, Card, CardContent,
    Typography
} from "@mui/material";
import {GradientCircularProgress} from "../GradientCircularProgress.tsx";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import {fetchStockForecasts, type StockForecast} from "../../services/StockForecastService.ts";
import StockScatterChart from "./StockScatterChart.tsx";
import Grid from "@mui/material/Grid";

interface ForecastChartsProps {
    symbol: string
}
async function getForecasts(symbol:string, forecastLength: number, setLoading: (data: boolean) => void) {
    setLoading(true)
    const response = await fetchStockForecasts(symbol, "daily", forecastLength)
    const forecasts: StockForecast[] = response['results']
    setLoading(false)
    return forecasts
}
export function ForecastCharts(props: ForecastChartsProps){
    const [ loading, setLoading ] = useState(false)
    const [ forecasts, setForecasts ] = useState<StockForecast[]>([])
    const forecastLength = 7


    useEffect(() => {
        if(props.symbol === ""){
            return
        }
        getForecasts(props.symbol, forecastLength, setLoading).then((response) => setForecasts(response))
    }, [props.symbol])

    if(props.symbol == ""){
        return <></>
    }
    return <>
        {loading ? <Card><CardContent><Stack direction={'row'} alignItems={'center'} spacing={2}><Typography variant={'h4'}>Price Forecasting</Typography><GradientCircularProgress/></Stack></CardContent></Card> :
                <Accordion style={{padding:'16px'}}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Stack direction={'row'} alignItems={'center'} spacing={2}>
                            <Typography variant={'h4'}>Price Forecasting</Typography>
                            <Typography variant={'h6'}>View several predictions of {props.symbol}'s prices for next week from ML and statistical models</Typography>
                        </Stack>
                    </AccordionSummary>
                    <Grid container justifyContent={'space-around'} rowSpacing={'16pt'}>
                        {forecasts.map((forecast) => (
                            <>
                                <StockScatterChart title={forecast.name} desc={forecast.summary} bars={forecast.forecast} symbol={props.symbol}/>
                            </>
                        ))
                        }
                    </Grid>
                </Accordion>}
    </>
}