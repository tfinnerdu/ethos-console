import { useMsal, AuthenticatedTemplate, UnauthenticatedTemplate } from '@azure/msal-react';
import { Button, Center, Stack, Text, Title } from '@mantine/core';
import { Outlet } from 'react-router-dom';
import { loginRequest } from './msalConfig';
import { authEnabled } from '../../main';

function MsalGate() {
  const { instance } = useMsal();
  return (
    <>
      <AuthenticatedTemplate>
        <Outlet />
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <Center h="100vh">
          <Stack align="center" gap="md">
            <Title order={2}>Change Notification Manager</Title>
            <Text c="dimmed">Sign in with your Doane account to continue.</Text>
            <Button onClick={() => instance.loginRedirect(loginRequest)}>
              Sign in
            </Button>
          </Stack>
        </Center>
      </UnauthenticatedTemplate>
    </>
  );
}

export function RequireAuth() {
  if (!authEnabled) return <Outlet />;
  return <MsalGate />;
}
