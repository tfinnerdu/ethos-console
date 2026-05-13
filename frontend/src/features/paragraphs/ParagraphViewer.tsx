import { Code, Loader, Stack, Text, Title } from '@mantine/core';
import { useParagraph } from '../../shared/api/hooks';

interface Props {
  notificationId: string;
}

export function ParagraphViewer({ notificationId }: Props) {
  const { data, isLoading, isError } = useParagraph(notificationId, true);

  if (isLoading) return <Loader size="sm" />;
  if (isError) return <Text c="red" size="sm">Failed to load paragraph source.</Text>;
  if (!data) return null;

  return (
    <Stack gap="xs">
      <Title order={6}>Paragraph: {data.code}</Title>
      <Code block style={{ maxHeight: 400, overflow: 'auto' }}>
        {data.source}
      </Code>
    </Stack>
  );
}
