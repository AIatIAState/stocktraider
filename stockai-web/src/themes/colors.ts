export const spaceIndigo = {
  950: '#0b0f23',
  900: '#0d1117',   // dark mode background.default
  800: '#1B224B',   // brand anchor — light mode primary.main
  700: '#243066',
  600: '#3a4a8a',
  500: '#4d5fa3',
  400: '#7986CB',   // dark mode primary.main (legible on dark bg)
  300: '#9fa8da',
  200: '#c5cae9',
  100: '#e8eaf6',
} as const;

export const stockSignals = {
  gainLight: '#2e7d32',  // success.main in light mode
  gainDark:  '#4caf50',  // success.main in dark mode
  lossLight: '#c62828',  // error.main in light mode
  lossDark:  '#ef5350',  // error.main in dark mode
} as const;
