import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider } from '@azure/msal-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import { msalConfig } from './features/auth/msalConfig';
import { doaneTheme } from './shared/theme';
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

const msalInstance = new PublicClientApplication(msalConfig);
await msalInstance.initialize();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <MantineProvider theme={doaneTheme}>
          <Notifications />
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </MantineProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </MsalProvider>
  </StrictMode>,
);
