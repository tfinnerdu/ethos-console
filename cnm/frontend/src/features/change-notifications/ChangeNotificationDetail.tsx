import {
  Accordion,
  Badge,
  Button,
  Code,
  Divider,
  Group,
  Loader,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Textarea,
  Title,
} from '@mantine/core';
import { Link, useParams } from 'react-router-dom';
import {
  useChangeNotification,
  useNotificationHistory,
  useParagraph,
} from '../../shared/api/hooks';

export function ChangeNotificationDetail() {
  const { id } = useParams<{ id: string }>();
  const { data: notification, isLoading } = useChangeNotification(id!);
  const { data: history } = useNotificationHistory(id!);
  const { data: paragraph } = useParagraph(id!, !!notification?.paragraphCode);

  if (isLoading) return <Loader />;
  if (!notification) return <Text c="red">Not found.</Text>;

  const isEnabled = notification.status === 'Enabled';

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Stack gap={0}>
          <Text component={Link} to="/change-notifications" c="blue" size="sm">
            ← Back to list
          </Text>
          <Title order={3}>{notification.id}</Title>
          <Text c="dimmed">{notification.resourceName}</Text>
        </Stack>
        <Group gap="sm">
          <Button disabled color="red" variant="outline" title="Available in v1.5">
            Delete
          </Button>
          <Switch
            disabled
            checked={isEnabled}
            label={isEnabled ? 'Enabled' : 'Disabled'}
            title="Available in v1.5"
          />
          <Button disabled title="Available in v1.5">
            Save changes
          </Button>
        </Group>
      </Group>

      <Divider />

      <Stack gap="sm">
        <TextInput label="Description" value={notification.description} readOnly />
        <TextInput label="Process Code" value={notification.processCode ?? ''} readOnly />
        <TextInput label="Paragraph Code" value={notification.paragraphCode ?? '(none)'} readOnly />

        {notification.parameters.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={500}>Parameters</Text>
            {notification.parameters.map((p, i) => (
              <TextInput key={i} value={p} readOnly />
            ))}
          </Stack>
        )}

        {notification.edpsRules.length > 0 && (
          <Stack gap="xs">
            <Text size="sm" fw={500}>EDPS Rules</Text>
            {notification.edpsRules.map((r, i) => (
              <Text key={i} size="sm" c="dimmed">{r}</Text>
            ))}
          </Stack>
        )}
      </Stack>

      {paragraph && (
        <Accordion>
          <Accordion.Item value="paragraph">
            <Accordion.Control>
              Paragraph source — {paragraph.code}
            </Accordion.Control>
            <Accordion.Panel>
              <Code block>{paragraph.source}</Code>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}

      {history && history.length > 0 && (
        <Stack gap="xs">
          <Title order={5}>History</Title>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Timestamp</Table.Th>
                <Table.Th>User</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Outcome</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {history.map((e) => (
                <Table.Tr key={e.auditId}>
                  <Table.Td>{new Date(e.timestamp).toLocaleString()}</Table.Td>
                  <Table.Td>{e.userDisplayName}</Table.Td>
                  <Table.Td>{e.action}</Table.Td>
                  <Table.Td>
                    <Badge
                      color={e.outcome === 'Success' ? 'green' : e.outcome === 'Denied' ? 'orange' : 'red'}
                    >
                      {e.outcome}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}
    </Stack>
  );
}
