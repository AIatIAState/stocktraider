import type {Bar} from "../../services/api.ts";
import {PieChart} from "@mui/x-charts/PieChart";
import type {PieValueType} from "@mui/x-charts";
import {useDrawingArea} from "@mui/x-charts/hooks";
import {styled} from "@mui/material/styles";
import CardContent from "@mui/material/CardContent";
import Card from "@mui/material/Card";
import Typography from "@mui/material/Typography";
import { formatSymbol } from "../../utils/formatSymbol";

interface StockPieChartProps {
    bars: Bar[],
}

interface StyledTextProps {
    variant: 'primary' | 'secondary'
}

const StyledText = styled('text', {
    shouldForwardProp: (prop) => prop !== 'variant',
})<StyledTextProps>(({ theme, variant }) => ({
    textAnchor: 'middle',
    dominantBaseline: 'central',
    fill: (theme.vars || theme).palette.text.secondary,
    fontSize:
        variant === 'primary'
            ? theme.typography.h5.fontSize
            : theme.typography.body2.fontSize,
    fontWeight:
        variant === 'primary'
            ? theme.typography.h5.fontWeight
            : theme.typography.body2.fontWeight,
}))
interface PieCenterLabelProps {
    primaryText: string
    secondaryText: string
}
function PieCenterLabel({ primaryText, secondaryText }: PieCenterLabelProps) {
    const { width, height, left, top } = useDrawingArea()
    const primaryY = top + height / 2 - 10
    const secondaryY = primaryY + 24

    return (
        <>
            <StyledText variant="primary" x={left + width / 2} y={primaryY}>
                {primaryText}
            </StyledText>
            <StyledText variant="secondary" x={left + width / 2} y={secondaryY}>
                {secondaryText}
            </StyledText>
        </>
    )
}

export function StockPieChart(props: StockPieChartProps){
    let trendUp = 0
    let trendDown = 0
    let trendFlat = 0
    props.bars.forEach((bar: Bar) => {
        if (bar.open! > bar.close!) {
            trendUp += 1
        } else if (bar.open! < bar.close!) {
            trendDown += 1
        } else {
            trendFlat += 1
        }
    })
    return <Card>
        <CardContent>
            <Typography>
                {formatSymbol(props.bars[0]?.symbol ?? '')} Trend Breakdown
            </Typography>
        <PieChart
            colors={['#4caf50', '#ef5350', '#9fa8da']}
            margin={{ left: 80, right: 80, top: 80, bottom: 80 }}
            series={[
                {
                    data: [{value: trendUp, label: "Up"}, {value: trendDown, label: "Down"}, {value: trendFlat, label: "Even"}] as PieValueType[],
                    innerRadius: 75,
                    outerRadius: 100,
                    paddingAngle: 0,
                    highlightScope: { fade: 'global', highlight: 'item' },
                },
            ]}
            height={260}
            width={260}
            hideLegend={false}
        >
            <PieCenterLabel primaryText={`${((trendUp/(trendUp+trendDown+trendFlat)) * 100).toFixed(2)}%`} secondaryText={`Up days`} />
        </PieChart>
        </CardContent>
    </Card>
    // {trendRows.map((row) => {
    //     const percent = trendTotal === 0 ? 0 : (row.value / trendTotal) * 100
    //     return (
    //         <Stack
    //             key={row.label}
    //             direction="row"
    //             sx={{ alignItems: 'center', gap: 2, pb: 2 }}
    //         >
    //             <Box
    //                 sx={{
    //                     width: 12,
    //                     height: 12,
    //                     borderRadius: '999px',
    //                     backgroundColor: row.color,
    //                 }}
    //             />
    //             <Stack sx={{ gap: 1, flexGrow: 1 }}>
    //                 <Stack
    //                     direction="row"
    //                     sx={{
    //                         justifyContent: 'space-between',
    //                         alignItems: 'center',
    //                         gap: 2,
    //                     }}
    //                 >
    //                     <Typography variant="body2" sx={{ fontWeight: '500' }}>
    //                         {row.label}
    //                     </Typography>
    //                     <Typography variant="body2" sx={{ color: 'text.secondary' }}>
    //                         {Math.round(percent)}%
    //                     </Typography>
    //                 </Stack>
    //                 <LinearProgress
    //                     variant="determinate"
    //                     aria-label={`${row.label} ${barLabel}`}
    //                     value={percent}
    //                     sx={{
    //                         [`& .${linearProgressClasses.bar}`]: {
    //                             backgroundColor: row.color,
    //                         },
    //                     }}
    //                 />
    //             </Stack>
    //         </Stack>
}