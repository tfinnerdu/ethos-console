import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use((config) => {
  // Token is injected by the MSAL interceptor in useApiToken hook.
  // See shared/api/hooks.ts for token acquisition pattern.
  return config;
});
