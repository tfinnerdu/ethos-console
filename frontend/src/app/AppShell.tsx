import { AppShell as MantineAppShell, NavLink, Text, Group, Button } from '@mantine/core';
import { Outlet, NavLink as RouterNavLink } from 'react-router-dom';
import { useAuth } from '../features/auth/useAuth';

export function AppShell() {
  const { user, logout } = useAuth();

  return (
    <MantineAppShell
      header={{ height: 56 }}
      navbar={{ width: 220, breakpoint: 'sm' }}
      padding="md"
    >
      <MantineAppShell.Header p="sm">
        <Group justify="space-between">
          <Text fw={700} size="lg">Change Notification Manager</Text>
          <Group gap="xs">
            <Text size="sm" c="dimmed">{user?.displayName}</Text>
            <Button size="xs" variant="subtle" onClick={logout}>Sign out</Button>
          </Group>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="xs">
        <NavLink
          label="Change Notifications"
          component={RouterNavLink}
          to="/change-notifications"
        />
        <NavLink
          label="Audit Log"
          component={RouterNavLink}
          to="/audit"
        />
      </MantineAppShell.Navbar>

      <MantineAppShell.Main>
        <Outlet />
      </MantineAppShell.Main>
    </MantineAppShell>
  );
}
