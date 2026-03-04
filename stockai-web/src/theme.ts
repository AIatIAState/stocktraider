import { createTheme } from '@mui/material/styles';
import { spaceIndigo, stockSignals } from './themes/colors';

// cssVariables is required for useColorScheme() to work.
// Without it, mode is always undefined and ColorModeIconDropdown/ColorModeSelect render nothing.
const theme = createTheme({
  cssVariables: {
    colorSchemeSelector: 'class',
  },
  colorSchemes: {
    light: {
      palette: {
        primary: {
          main:  spaceIndigo[800],  // '#1B224B' — contrast ~11:1 on white (WCAG AAA)
          light: spaceIndigo[500],  // '#4d5fa3'
          dark:  spaceIndigo[900],  // '#0d1117'
        },
        success: { main: stockSignals.gainLight },  // '#2e7d32'
        error:   { main: stockSignals.lossLight },  // '#c62828'
        background: { default: '#f8f9fa', paper: '#ffffff' },
      },
    },
    dark: {
      palette: {
        primary: {
          main:  spaceIndigo[400],  // '#7986CB' — contrast ~6.5:1 on dark bg (WCAG AA)
          light: spaceIndigo[300],  // '#9fa8da'
          dark:  spaceIndigo[600],  // '#3a4a8a'
        },
        success: { main: stockSignals.gainDark },  // '#4caf50'
        error:   { main: stockSignals.lossDark },  // '#ef5350'
        background: { default: spaceIndigo[900], paper: '#161b2e' },
      },
    },
  },
});

export default theme;
