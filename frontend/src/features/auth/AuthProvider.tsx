import { useMsal } from '@azure/msal-react';
import { createContext, useContext, type ReactNode } from 'react';
import { loginRequest } from './msalConfig';

interface AuthContextValue {
  user: { userId: string; displayName: string; roles: string[] } | null;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  logout: () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const { instance, accounts } = useMsal();

  const account = accounts[0] ?? null;

  const user = account
    ? {
        userId: account.username,
        displayName: account.name ?? account.username,
        roles: (account.idTokenClaims?.roles as string[] | undefined) ?? [],
      }
    : null;

  const logout = () =>
    instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin });

  return (
    <AuthContext.Provider value={{ user, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
