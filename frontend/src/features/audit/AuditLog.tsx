import { Badge, Group, Loader, Pagination, Stack, Table, Text, Title } from '@mantine/core';
import { useState } from 'react';
import { useAuditLog } from '../../shared/api/hooks';

export function AuditLog() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError } = useAuditLog(page);

  const totalPages = data ? Math.ceil(data.totalCount / data.pageSize) : 1;

  return (
    <Stack gap="md">
      <Title order={3}>Audit Log</Title>

      {isLoading && <Loader />}
      {isError && <Text c="red">Failed to load audit log.</Text>}

      {data && (
        <>
          <Table striped withTableBorder>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Timestamp</Table.Th>
                <Table.Th>User</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Target</Table.Th>
                <Table.Th>Outcome</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((e) => (
                <Table.Tr key={e.auditId}>
                  <Table.Td>{new Date(e.timestamp).toLocaleString()}</Table.Td>
                  <Table.Td>{e.userDisplayName}</Table.Td>
                  <Table.Td>{e.action}</Table.Td>
                  <Table.Td>
                    <Text size="sm">{e.targetType}</Text>
                    {e.targetIdentifier && (
                      <Text size="xs" c="dimmed">{e.targetIdentifier}</Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Badge
                      color={
                        e.outcome === 'Success'
                          ? 'green'
                          : e.outcome === 'Denied'
                          ? 'orange'
                          : 'red'
                      }
                    >
                      {e.outcome}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Group justify="center">
            <Pagination total={totalPages} value={page} onChange={setPage} />
          </Group>
        </>
      )}
    </Stack>
  );
}
