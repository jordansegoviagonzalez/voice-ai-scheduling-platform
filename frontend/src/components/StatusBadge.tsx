import type { CallStatus } from '../types/api';

const labels: Record<string, string> = {
  SCHEDULED: 'Scheduled',
  REDIRECTED: 'Redirected',
  ABANDONED: 'Abandoned',
  FAILED: 'Failed',
  IN_PROGRESS: 'In progress',
  ACCEPTED: 'Accepted',
  REJECTED: 'Rejected',
};

export function StatusBadge({ status }: { status: CallStatus | 'ACCEPTED' | 'REJECTED' | string }) {
  return <span className={`status-badge status-${status.toLowerCase()}`}>{labels[status] ?? status}</span>;
}
