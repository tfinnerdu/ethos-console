import { Configuration, LogLevel } from '@azure/msal-browser';

export const msalConfig: Configuration = {
  auth: {
    clientId: import.meta.env.VITE_MSAL_CLIENT_ID as string,
    authority: import.meta.env.VITE_MSAL_AUTHORITY as string,
    redirectUri: import.meta.env.VITE_MSAL_REDIRECT_URI as string,
  },
  cache: {
    cacheLocation: 'sessionStorage',
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      loggerCallback: (level, message, containsPii) => {
        if (containsPii) return;
        if (level === LogLevel.Error) console.error(message);
      },
    },
  },
};

export const loginRequest = {
  scopes: ['openid', 'profile', 'User.Read'],
};
