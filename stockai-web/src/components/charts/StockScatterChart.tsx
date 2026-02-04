import { useTheme } from '@mui/material/styles';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import {LineChart} from '@mui/x-charts/LineChart';
import { useMemo } from "react";
import HoverableTooltip from "../HoverableTooltip.tsx";


function getDateFromYYYYMMDD(yyyymmdd: string): Date {
    const year = parseInt(yyyymmdd.substring(0, 4), 10);
    const month = parseInt(yyyymmdd.substring(4, 6), 10) - 1;
    const day = parseInt(yyyymmdd.substring(6, 8), 10);

    return new Date(Date.UTC(year, month, day));
}
export interface StockScatterChartProps {
        bars: [{ date: number, open: number }],
        symbol: string,
        title?: string,
        desc?: string,
        size?: "big" | "small"
}
export default function StockScatterChart(props: StockScatterChartProps) {
    const theme = useTheme();

    const { opens, dates, min, max } = useMemo(() => {
        if (!props.bars?.length) {
            return { opens: [], dates: [], min: 0, max: 0 };
        }

        let min = Number.POSITIVE_INFINITY;
        let max = Number.NEGATIVE_INFINITY;

        const opens: number[] = [];
        const dates: Date[] = [];

        props.bars.forEach((item) => {
            const open = item.open ?? 0;
            const parsedDate = getDateFromYYYYMMDD(item.date.toString());

            opens.push(open);
            dates.push(parsedDate);

            if (item.open != null) {
                if (item.open < min) min = item.open;
                if (item.open > max) max = item.open;
            }
        });

        if (min === Number.POSITIVE_INFINITY) min = 0;
        if (max === Number.NEGATIVE_INFINITY) max = 0;

        return { opens, dates, min, max };
    }, [props.bars]);

    if(props.bars.length <= 0) {
        return <></>
    }
    const symbol = props.symbol
  const heading = props.title ? props.title : symbol + " Price"
    const desc = props.desc ? props.desc : null
    const percentage = ((props.bars[props.bars.length - 1].open! - props.bars[props.bars.length - 2].open!) / props.bars[props.bars.length - 2].open! * 100)
  const colorPalette = [
    theme.palette.primary.light,
    theme.palette.primary.main,
    theme.palette.primary.dark,
  ];

  return (
    <Card variant="outlined" sx={{ width: props.size == "big"? '100%' : '30%'}}>
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
          colors={colorPalette}
          xAxis={[
            {
              scaleType: 'time',
              data: dates,
              valueFormatter: (value: Date) => {
                  return `${value.getMonth() + 1}/${value.getDate()}/${value.getFullYear()}`;
              }
            },
          ]}
          yAxis={[{ max:max + 1, min:min - 1 > 0 ? min - 1 : 0}]}
          series={[{
              id: symbol,
              label: symbol,
              showMark: false,
              curve: 'linear',
              stack: 'total',
              area: true,
              stackOrder: 'ascending',
              data: opens,
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
