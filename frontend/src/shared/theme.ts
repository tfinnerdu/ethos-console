import { createTheme } from '@mantine/core';

export const doaneTheme = createTheme({
  primaryColor: 'doaneOrange',
  colors: {
    doaneOrange: [
      '#fff3e6',
      '#ffe0bf',
      '#ffcc99',
      '#ffb366',
      '#ff9933',
      '#FF7900',
      '#e66d00',
      '#cc6100',
      '#b35400',
      '#994800',
    ],
    doaneNavy: [
      '#e8ecf2',
      '#c5cfe0',
      '#a2b1ce',
      '#7f93bc',
      '#5c75aa',
      '#3d5a91',
      '#334e7d',
      '#2a4169',
      '#1F3864',
      '#172b4d',
    ],
  },
  primaryShade: 5,
  fontFamily: 'Segoe UI, Arial, sans-serif',
  defaultRadius: 'sm',
  components: {
    Button: {
      defaultProps: { color: 'doaneOrange' },
    },
    Badge: {
      defaultProps: { radius: 'sm' },
    },
  },
});
