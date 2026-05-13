import {
  Alert,
  Badge,
  Group,
  Loader,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { useSubscriptionPublishingDiagnostic } from '../../shared/api/hooks';

function NamespaceBadge({ name }: { name: string }) {
  if (name.startsWith('d45-'))
    return <Badge color="grape" size="xs">vendor</Badge>;
  if (name.startsWith('x-'))
    return <Badge color="teal" size="xs">institution</Badge>;
  return <Badge color="blue" size="xs">standard</Badge>;
}

export function SubscriptionPublishingDiagnostic() {
  const { data, isLoading, isError } = useSubscriptionPublishingDiagnostic();

  if (isLoading) return <Loader />;
  if (isError || !data)
    return <Alert color="red">Failed to load diagnostic data.</Alert>;

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={3}>Subscription vs. Publishing Diagnostic</Title>
        <Group gap="xs">
          <Text size="sm" c="dimmed">
            {data.totalSubscribed} subscribed · {data.totalPublished} published by Colleague
          </Text>
        </Group>
      </Group>

      {data.subscribedNotPublished.length > 0 && (
        <Stack gap="xs">
          <Group gap="xs">
            <Badge color="red">{data.subscribedNotPublished.length}</Badge>
            <Text fw={600}>Subscribed but Colleague is NOT publishing</Text>
          </Group>
          <Text size="sm" c="dimmed">
            We consume these in Conductor but Colleague has no matching CINC entry.
            Likely vendor-proxied or RPC-only resources.
          </Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Resource</Table.Th>
                <Table.Th>Namespace</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.subscribedNotPublished.map(name => (
                <Table.Tr key={name}>
                  <Table.Td><Text size="sm" ff="monospace">{name}</Text></Table.Td>
                  <Table.Td><NamespaceBadge name={name} /></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}

      {data.publishedNotSubscribed.length > 0 && (
        <Stack gap="xs">
          <Group gap="xs">
            <Badge color="yellow">{data.publishedNotSubscribed.length}</Badge>
            <Text fw={600}>Colleague is publishing but we are NOT subscribed</Text>
          </Group>
          <Text size="sm" c="dimmed">
            Colleague has CINC entries for these but Conductor does not consume them.
          </Text>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Resource</Table.Th>
                <Table.Th>Namespace</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.publishedNotSubscribed.map(name => (
                <Table.Tr key={name}>
                  <Table.Td><Text size="sm" ff="monospace">{name}</Text></Table.Td>
                  <Table.Td><NamespaceBadge name={name} /></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Stack>
      )}

      <Stack gap="xs">
        <Group gap="xs">
          <Badge color="green">{data.aligned.length}</Badge>
          <Text fw={600}>Aligned — subscribed and published</Text>
        </Group>
        <Table striped withTableBorder>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Resource</Table.Th>
              <Table.Th>Namespace</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data.aligned.map(name => (
              <Table.Tr key={name}>
                <Table.Td><Text size="sm" ff="monospace">{name}</Text></Table.Td>
                <Table.Td><NamespaceBadge name={name} /></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Stack>
  );
}
