import {
  Badge,
  Button,
  Group,
  Loader,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useChangeNotifications, useResources } from '../../shared/api/hooks';

const statusColors: Record<string, string> = {
  Enabled: 'green',
  Disabled: 'gray',
  Unknown: 'yellow',
};

export function ChangeNotificationList() {
  const [resource, setResource] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  const { data: resources } = useResources();
  const { data: notifications, isLoading, isError } = useChangeNotifications(
    resource ?? undefined,
    status ?? undefined,
  );

  const resourceOptions = [
    { value: '', label: 'All resources' },
    ...(resources?.map((r) => ({ value: r.name, label: r.displayName })) ?? []),
  ];

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={3}>Change Notifications</Title>
        <Button disabled variant="filled" title="Available in v1.5">
          + New Notification
        </Button>
      </Group>

      <Group gap="sm">
        <Select
          placeholder="Filter by resource"
          data={resourceOptions}
          value={resource}
          onChange={setResource}
          clearable
          w={240}
        />
        <Select
          placeholder="Filter by status"
          data={['Enabled', 'Disabled']}
          value={status}
          onChange={setStatus}
          clearable
          w={180}
        />
      </Group>

      {isLoading && <Loader />}
      {isError && <Text c="red">Failed to load change notifications.</Text>}

      {notifications && (
        <Table striped highlightOnHover withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>ID</Table.Th>
              <Table.Th>Resource</Table.Th>
              <Table.Th>Description</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Paragraph</Table.Th>
              <Table.Th>Last Modified</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {notifications.map((n) => (
              <Table.Tr key={n.id}>
                <Table.Td>
                  <Text component={Link} to={`/change-notifications/${n.id}`} c="blue">
                    {n.id}
                  </Text>
                </Table.Td>
                <Table.Td>{n.resourceName}</Table.Td>
                <Table.Td>{n.description}</Table.Td>
                <Table.Td>
                  <Badge color={statusColors[n.status] ?? 'gray'}>{n.status}</Badge>
                </Table.Td>
                <Table.Td>{n.hasParagraph ? '✓' : '—'}</Table.Td>
                <Table.Td>
                  {n.lastModified
                    ? new Date(n.lastModified).toLocaleDateString()
                    : '—'}
                </Table.Td>
              </Table.Tr>
            ))}
            {notifications.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={6}>
                  <Text c="dimmed" ta="center">No change notifications found.</Text>
                </Table.Td>
              </Table.Tr>
            )}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
