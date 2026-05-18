import { AppRoutes } from './app/AppRoutes';
import { AuthProvider } from './features/auth/AuthProvider';

export function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
