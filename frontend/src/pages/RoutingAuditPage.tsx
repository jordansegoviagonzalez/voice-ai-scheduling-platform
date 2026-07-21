import { useQuery } from '@tanstack/react-query';
import { schedulingApi } from '../api/schedulingApi';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';

export function RoutingAuditPage() {
  const query = useQuery({ queryKey: ['routing-audit'], queryFn: schedulingApi.routingAudit });
  if (query.isLoading) return <LoadingState label="Loading routing audit" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Unknown error'} />;
  const decisions = query.data.decisions;
  return (
    <>
      <PageHeader title="Routing Audit" subtitle="Explainable, persisted physician eligibility and fallback decisions" />
      <section className="panel">
        {decisions.length === 0 ? <EmptyState title="No routing decisions" detail="Run a call simulation to generate an auditable decision trail." /> : <DataTable label="Routing audit decisions" headers={['Timestamp', 'Call', 'Physician', 'Decision', 'Reason code', 'Human-readable explanation']}>
          {decisions.map((decision) => <tr key={decision.id}><td>{new Date(decision.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}</td><td>{decision.call_id ? `#${decision.call_id}` : '—'}</td><td>{decision.doctor?.full_name ?? 'Routing engine'}</td><td><StatusBadge status={decision.decision} /></td><td><code>{decision.reason_code}</code></td><td className="wide-cell">{decision.human_readable_reason}</td></tr>)}
        </DataTable>}
      </section>
    </>
  );
}
