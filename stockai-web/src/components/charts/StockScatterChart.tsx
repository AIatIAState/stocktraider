import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import {LineChart} from '@mui/x-charts/LineChart';
import { useMemo } from "react";
import HoverableTooltip from "../HoverableTooltip.tsx";
import { formatSymbol } from "../../utils/formatSymbol";


function getDateFromYYYYMMDD(yyyymmdd: string): Date {
    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}
export interface StockScatterChartProps {
        bars: [{ date: number, close: number }],
        symbol: string,
        title?: string,
        desc?: string,
        size?: "big" | "small"
}
export default function StockScatterChart(props: StockScatterChartProps) {

    const { closes, dates, min, max } = useMemo(() => {
        if (!props.bars?.length) {
            return { closes: [], dates: [], min: 0, max: 0 };
        }

        let min = Number.POSITIVE_INFINITY;
        let max = Number.NEGATIVE_INFINITY;

        const closes: number[] = [];
        const dates: Date[] = [];

        props.bars.forEach((item) => {
            const close = item.close ?? 0;
            const parsedDate = getDateFromYYYYMMDD(item.date.toString());

            closes.push(close);
            dates.push(parsedDate);

            if (item.close != null) {
                if (item.close < min) min = item.close;
                if (item.close > max) max = item.close;
            }
        });

        if (min === Number.POSITIVE_INFINITY) min = 0;
        if (max === Number.NEGATIVE_INFINITY) max = 0;

        return { closes, dates, min, max };
    }, [props.bars]);

    if(props.bars.length <= 0) {
        return <></>
    }
    const symbol = props.symbol
    const displaySymbol = formatSymbol(symbol)
  const heading = props.title ? props.title : displaySymbol + " Price"
    const desc = props.desc ? props.desc : null
    const percentage = ((props.bars[props.bars.length - 1].close! - props.bars[0].close!) / props.bars[0].close! * 100)
  return (
    <Card variant="outlined" sx={{ width: '100%', borderRadius: 3 }}>
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
            <Typography variant={props.size == "big" ? "h4" : "body1"} component="p">
                {heading}
            </Typography>
            <Chip size="small" color={percentage > 0 ? "success" : "warning"} label={percentage > 0 ? "+" + percentage.toFixed(2) : percentage.toFixed(2)} />
              {desc &&
                  <HoverableTooltip>
                      <Typography variant={props.size == "big" ? "h6": "body2"} component={"p"}>
                          {desc}
                      </Typography>
                  </HoverableTooltip>
              }
          </Stack>
        </Stack>
        <LineChart
          colors={['var(--mui-palette-primary-main)']}
          xAxis={[
            {
              scaleType: 'time',
              data: dates,
              valueFormatter: (value: Date) => {
                  return `${value.getMonth() + 1}/${value.getDate()}/${value.getFullYear()}`;
              }
            },
          ]}
          yAxis={[{
              max:max + 1,
              min:min - 1 > 0 ? min - 1 : 0,
              valueFormatter: (value: number) => {
                  return value.toFixed(2)
              }
          }]}
          series={[{
              id: symbol,
              label: displaySymbol,
              showMark: false,
              curve: 'linear',
              stack: 'total',
              area: true,
              stackOrder: 'ascending',
              data: closes,
        }]}
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
        </LineChart>
      </CardContent>
    </Card>
  );
}
