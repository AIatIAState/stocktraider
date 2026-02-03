import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Copyright from '../components/Copyright';
import ActiveStocksPieChart from './ActiveStocksPieChart.tsx';
import CustomizedDataGrid from './CustomizedDataGrid';
import HighlightedCard from './HighlightedCard';
import OptionBarChart from './OptionBarChart.tsx';


export default function MainGrid() {



    return (
    <Box sx={{ width: '100%', maxWidth: { sm: '100%', md: '1700px' } }}>
      {/* cards */}
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Overview
      </Typography>
        {/*<StockSearch setBars={setData}/>*/}
        <br/>
        <br/>
        {/*<StockScatterChart data={data}/>*/}
        <br/>
        <br/>
        {/*<StockPatternRecognitionGrid data={data}/>*/}
      <Grid
        container
        spacing={2}
        columns={12}
        sx={{ mb: (theme) => theme.spacing(2) }}
      >
        <Grid size={{ xs: 12, sm: 6, lg: 3 }}>
          <HighlightedCard />
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <OptionBarChart />
        </Grid>
      </Grid>
      <Typography component="h2" variant="h6" sx={{ mb: 2 }}>
        Suggested Trades
      </Typography>
      <Grid container spacing={2} columns={12}>
        <Grid size={{ xs: 12, lg: 9 }}>
          <CustomizedDataGrid />
        </Grid>
        <Grid size={{ xs: 12, lg: 3 }}>
            <ActiveStocksPieChart />
        </Grid>
      </Grid>
      <Copyright sx={{ my: 4 }} />
    </Box>
  );
}
