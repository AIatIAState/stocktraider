import CssBaseline from '@mui/material/CssBaseline';
import { ThemeProvider } from '@mui/material/styles';
import type { ReactNode } from 'react';
import theme from '../theme';

type AppThemeProps = {
  children: ReactNode;
  disableCustomTheme?: boolean;
};

export default function AppTheme({ children, disableCustomTheme = false }: AppThemeProps) {
  return (
    <ThemeProvider theme={theme} defaultMode="system">
      {!disableCustomTheme && <CssBaseline enableColorScheme />}
      {children}
    </ThemeProvider>
  );
}
