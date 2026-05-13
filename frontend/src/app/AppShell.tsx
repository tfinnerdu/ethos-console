import { AppShell as MantineAppShell, NavLink, Text, Group, Button, Box } from '@mantine/core';
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
      <MantineAppShell.Header
        style={{ backgroundColor: '#1F3864', borderBottom: '3px solid #FF7900' }}
        p="sm"
      >
        <Group justify="space-between" h="100%">
          <Text fw={700} size="lg" c="white">
            Change Notification Manager
          </Text>
          <Group gap="xs">
            <Text size="sm" c="rgba(255,255,255,0.75)">{user?.displayName}</Text>
            <Button size="xs" variant="outline" color="white" onClick={logout}>
              Sign out
            </Button>
          </Group>
        </Group>
      </MantineAppShell.Header>

      <MantineAppShell.Navbar p="xs" style={{ borderRight: '1px solid #e9ecef' }}>
        <Box mb="xs">
          <Text size="xs" fw={600} c="dimmed" tt="uppercase" px="sm" py={4}>
            Navigation
          </Text>
        </Box>
        <NavLink
          label="Change Notifications"
          component={RouterNavLink}
          to="/change-notifications"
          style={({ isActive }: { isActive: boolean }) =>
            isActive ? { backgroundColor: '#fff3e6', color: '#FF7900', borderRadius: 4 } : {}
          }
        />
        <NavLink
          label="Audit Log"
          component={RouterNavLink}
          to="/audit"
          style={({ isActive }: { isActive: boolean }) =>
            isActive ? { backgroundColor: '#fff3e6', color: '#FF7900', borderRadius: 4 } : {}
          }
        />
      </MantineAppShell.Navbar>

      <MantineAppShell.Main>
        <Outlet />
      </MantineAppShell.Main>
    </MantineAppShell>
  );
}
