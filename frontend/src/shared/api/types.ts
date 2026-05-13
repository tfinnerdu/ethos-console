export interface ChangeNotificationListItem {
  id: string;
  resourceName: string;
  description: string;
  status: 'Enabled' | 'Disabled' | 'Unknown';
  hasParagraph: boolean;
  lastModified: string | null;
}

export interface ChangeNotification {
  id: string;
  resourceName: string;
  description: string;
  status: 'Enabled' | 'Disabled' | 'Unknown';
  paragraphCode: string | null;
  processCode: string | null;
  parameters: string[];
  edpsRules: string[];
  lastModified: string | null;
}

export interface Paragraph {
  code: string;
  source: string;
}

export interface AuditEntry {
  auditId: number;
  timestamp: string;
  userId: string;
  userDisplayName: string;
  action: string;
  targetType: string;
  targetIdentifier: string | null;
  beforeState: string | null;
  afterState: string | null;
  outcome: 'Success' | 'Failure' | 'Denied';
  failureReason: string | null;
  correlationId: string;
  sourceIp: string | null;
}

export interface PagedAuditLog {
  items: AuditEntry[];
  totalCount: number;
  page: number;
  pageSize: number;
}

export interface UserInfo {
  userId: string;
  displayName: string;
  roles: string[];
}

export interface EedmResource {
  name: string;
  displayName: string;
  description: string | null;
}

export interface ColleagueAbout {
  version: string | null;
}

export interface SubscriptionPublishingDiff {
  subscribedNotPublished: string[];
  publishedNotSubscribed: string[];
  aligned: string[];
  totalSubscribed: number;
  totalPublished: number;
}
