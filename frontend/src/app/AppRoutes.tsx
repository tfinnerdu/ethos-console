import { Routes, Route, Navigate } from 'react-router-dom';
import { RequireAuth } from '../features/auth/RequireAuth';
import { AppShell } from './AppShell';
import { ChangeNotificationList } from '../features/change-notifications/ChangeNotificationList';
import { ChangeNotificationDetail } from '../features/change-notifications/ChangeNotificationDetail';
import { AuditLog } from '../features/audit/AuditLog';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route index element={<Navigate to="/change-notifications" replace />} />
          <Route path="change-notifications" element={<ChangeNotificationList />} />
          <Route path="change-notifications/:id" element={<ChangeNotificationDetail />} />
          <Route path="audit" element={<AuditLog />} />
        </Route>
      </Route>
    </Routes>
  );
}
