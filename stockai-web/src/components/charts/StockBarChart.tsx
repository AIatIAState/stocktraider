import { useTheme } from '@mui/material/styles';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import type {Bar} from "../../services/api.ts";
import { BarChart } from "@mui/x-charts";


function getDateFromYYYYMMDD(yyyymmdd: string): Date {
    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}
export interface StockBarChartProps {
    bars: Bar[]
}
export default function StockBarChart(props: StockBarChartProps) {
    const theme = useTheme();

    if(props.bars.length <= 0) {
        return <></>
    }
    const dates: Date[] = []
    const volumes: number[] = []
    props.bars.forEach((item: Bar)=> {
        const parsedDate = getDateFromYYYYMMDD(item.date.toString())
        dates.push(parsedDate)
        volumes.push(item.volume === null ? 0 : item.volume)

    })
    const symbol = props.bars[0].symbol
    const heading = symbol + " Volume"
    const percentage = ((props.bars[props.bars.length - 1].volume! - props.bars[0].volume!) / props.bars[0].volume! * 100)
    const colorPalette = [
        theme.palette.primary.light,
        theme.palette.primary.main,
        theme.palette.primary.dark,
    ];

    return (
        <Card variant="outlined" sx={{ width: '100%' }}>
            <CardContent>
                <Stack sx={{ justifyContent: 'space-between' }}>
                    <Stack
                        direction="row"
                        sx={{
                            alignContent: { xs: 'center', sm: 'flex-start' },
                            alignItems: 'center',
                            gap: 1,
                        }}
                    >
                        <Typography variant="h4" component="p">
                            {heading}
                        </Typography>
                        <Chip size="small" color={percentage > 0 ? "success" : "warning"} label={percentage > 0 ? "+" + percentage.toFixed(2) : percentage.toFixed(2)} />
                    </Stack>
                </Stack>
                <BarChart
                    colors={colorPalette}
                    xAxis={[
                        {
                            scaleType: 'band',
                            categoryGapRatio: 0.6,
                            data: dates,
                            height: 24,
                            valueFormatter: (value: Date) => {
                                return `${value.getMonth() + 1}/${value.getDate()}/${value.getFullYear()}`;
                            }
                        },
                    ]}
                    yAxis={[{ width: 50 }]}
                    series={[{
                        id: symbol,
                        label: symbol,
                        stack: 'total',
                        stackOrder: 'ascending',
                        data: volumes
                    }]}
                    height={250}
                    margin={{ left: 0, right: 20, top: 20, bottom: 0 }}
                    grid={{ horizontal: true }}
                    sx={{
                        '& .MuiAreaElement-series-fidelity': {
                            fill: "url('#fidelity')",
                        },
                        '& .MuiAreaElement-series-s&p500': {
                            fill: "url('#s&p500')",
                        },
                        '& .MuiAreaElement-series-user': {
                            fill: "url('#user')",
                        },
                    }}
                    hideLegend
                >
                </BarChart>
            </CardContent>
        </Card>
    );
}
