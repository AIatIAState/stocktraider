import type {Bar} from "../../services/api.ts";
import StatCard from "./StatCard.tsx";
import {Box, TableCell} from "@mui/material";
import {useMemo} from "react";
import Typography from "@mui/material/Typography";

interface HistoricalPatternCardProps {
    bars: Bar[],
    currentTrendStartDate: Date,
    historicalTrendStartDate: Date,
    trendLength: number,
    similarityScore: number
}

function getDateFromYYYYMMDD(yyyymmdd: string): Date {
    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}
export function HistoricalPattern(props: HistoricalPatternCardProps){
    const { historicalCloseSeries, historicalExtendedSeries, endDate } = useMemo(() => {
        const endDate = new Date(props.historicalTrendStartDate)
        endDate.setDate(props.historicalTrendStartDate.getDate() + props.trendLength)
        const extendedDate = new Date(props.historicalTrendStartDate)
        extendedDate.setDate(props.historicalTrendStartDate.getDate() + (props.trendLength * 2))
        const historicalCloseSeries: number[] = []
        const historicalExtendedSeries: number[] = []
        props.bars.forEach((bar) => {
            const barDate = getDateFromYYYYMMDD(bar.date.toString())
            if(barDate >= props.historicalTrendStartDate && barDate <= endDate){
                historicalCloseSeries.push(bar.close != null ? bar.close : 0)
            }
            if(barDate >= endDate && barDate <= extendedDate){
                historicalExtendedSeries.push(bar.close != null ? bar.close : 0)
            }
        })
        return { historicalCloseSeries: historicalCloseSeries, historicalExtendedSeries, endDate}
    }, [props.bars, props.historicalTrendStartDate, props.trendLength])

    const closeSeriesValue = (historicalCloseSeries[historicalCloseSeries.length - 1] - historicalCloseSeries[0]) / historicalCloseSeries[0]
    const extendedSeriesValue = (historicalExtendedSeries[historicalExtendedSeries.length - 1] - historicalExtendedSeries[0]) / historicalExtendedSeries[0]
    return <Box
        sx={{
            display: "grid",
            gridTemplateColumns: "2fr 3fr 3fr 1fr",
            gap: 2
        }}
        alignItems={'end'}
    >
        <TableCell>
            <Typography>
            {props.historicalTrendStartDate.toLocaleDateString() + " - " + endDate.toLocaleDateString()}
            </Typography>
        </TableCell>
        <TableCell>
            <StatCard
                title=""
                value={(closeSeriesValue > 0 ? "+" : "-") + closeSeriesValue.toFixed(2) + "%"}
                interval={""}
                trend={closeSeriesValue > 0 ? "up" : closeSeriesValue < 0 ? "down": "neutral"}
                data={historicalCloseSeries}
            />
        </TableCell>
        <TableCell>
            <StatCard
                title={""}
                value={(extendedSeriesValue > 0 ? "+" : "-") + extendedSeriesValue.toFixed(2) + "%"}
                interval={""}
                trend={extendedSeriesValue > 0 ? "up" : extendedSeriesValue < 0 ? "down": "neutral"}
                data={historicalExtendedSeries}
            />
        </TableCell>
        <TableCell>
            <Typography>{props.similarityScore.toFixed(2)}%</Typography>
        </TableCell>
    </Box>
}