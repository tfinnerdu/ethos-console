import { useMsal } from '@azure/msal-react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from './client';
import { loginRequest } from '../../features/auth/msalConfig';
import type {
  ChangeNotification,
  ChangeNotificationListItem,
  AuditEntry,
  PagedAuditLog,
  Paragraph,
  EedmResource,
  ColleagueAbout,
  SubscriptionPublishingDiff,
} from './types';

const V1 = '/api/v1';

function useAuthHeader() {
  const { instance, accounts } = useMsal();
  const account = accounts[0];

  return async () => {
    if (!account) throw new Error('No account');
    const result = await instance.acquireTokenSilent({ ...loginRequest, account });
    return `Bearer ${result.accessToken}`;
  };
}

export function useChangeNotifications(resource?: string, status?: string) {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['change-notifications', { resource, status }],
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<ChangeNotificationListItem[]>(
        `${V1}/change-notifications`,
        { headers: { Authorization: auth }, params: { resource, status } },
      );
      return data;
    },
  });
}

export function useChangeNotification(id: string) {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['change-notifications', id],
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<ChangeNotification>(
        `${V1}/change-notifications/${id}`,
        { headers: { Authorization: auth } },
      );
      return data;
    },
  });
}

export function useParagraph(id: string, enabled: boolean) {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['paragraphs', id],
    enabled,
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<Paragraph>(
        `${V1}/change-notifications/${id}/paragraph`,
        { headers: { Authorization: auth } },
      );
      return data;
    },
  });
}

export function useNotificationHistory(id: string) {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['notification-history', id],
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<AuditEntry[]>(
        `${V1}/change-notifications/${id}/history`,
        { headers: { Authorization: auth } },
      );
      return data;
    },
  });
}

export function useAuditLog(page = 1, pageSize = 50) {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['audit-log', { page, pageSize }],
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<PagedAuditLog>(
        `${V1}/audit-log`,
        { headers: { Authorization: auth }, params: { page, pageSize } },
      );
      return data;
    },
  });
}

export function useResources() {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['resources'],
    staleTime: Infinity,
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<EedmResource[]>(`${V1}/resources`, {
        headers: { Authorization: auth },
      });
      return data;
    },
  });
}

export function useAbout() {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['about'],
    staleTime: 5 * 60_000,
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<ColleagueAbout>(`${V1}/about`, {
        headers: { Authorization: auth },
      });
      return data;
    },
  });
}

export function useSubscriptionPublishingDiagnostic() {
  const getHeader = useAuthHeader();

  return useQuery({
    queryKey: ['diagnostics', 'subscription-publishing'],
    queryFn: async () => {
      const auth = await getHeader();
      const { data } = await apiClient.get<SubscriptionPublishingDiff>(
        `${V1}/diagnostics/subscription-publishing`,
        { headers: { Authorization: auth } },
      );
      return data;
    },
  });
}
