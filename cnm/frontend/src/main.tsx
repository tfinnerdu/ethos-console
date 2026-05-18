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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

const clientId = import.meta.env.VITE_MSAL_CLIENT_ID as string | undefined;
export const authEnabled = !!clientId;

async function mount() {
  let msalInstance: PublicClientApplication | null = null;
  if (authEnabled) {
    msalInstance = new PublicClientApplication(msalConfig);
    await msalInstance.initialize();
  }

  const tree = (
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <MantineProvider theme={doaneTheme}>
          <Notifications />
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </MantineProvider>
        <ReactQueryDevtools initialIsOpen={false} />
      </QueryClientProvider>
    </StrictMode>
  );

  createRoot(document.getElementById('root')!).render(
    msalInstance ? <MsalProvider instance={msalInstance}>{tree}</MsalProvider> : tree,
  );
}

mount();
