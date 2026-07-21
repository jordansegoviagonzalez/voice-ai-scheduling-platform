import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { schedulingApi } from '../api/schedulingApi';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';

export function CallsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const queryString = useMemo(() => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    return params.size ? `?${params.toString()}` : '';
  }, [status]);
  const query = useQuery({ queryKey: ['calls', queryString], queryFn: () => schedulingApi.calls(queryString) });
  if (query.isLoading) return <LoadingState label="Loading call history" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Unknown error'} />;
  const calls = query.data.calls.filter((call) => `${call.patient?.full_name ?? ''} ${call.caller_phone} ${call.requested_body_part ?? ''} ${call.requested_issue_type ?? ''}`.toLowerCase().includes(search.toLowerCase()));

  return (
    <>
      <PageHeader title="Calls" subtitle="Review patient conversations, outcomes, transcripts, and routing decisions" />
      <section className="panel filter-panel">
        <label className="search-field"><Search size={17} /><input aria-label="Search calls" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search patient, phone, body part…" /></label>
        <select aria-label="Filter by status" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option>SCHEDULED</option><option>REDIRECTED</option><option>ABANDONED</option><option>FAILED</option><option>IN_PROGRESS</option></select>
      </section>
      <section className="panel">
        {calls.length === 0 ? <EmptyState title="No calls match these filters" detail="Change the search or status filter to view additional records." /> : <DataTable label="Call review records" headers={['Date / time', 'Caller or patient', 'Patient', 'Request', 'Status', 'Physician', 'Location', 'Appointment']}>
          {calls.map((call) => <tr key={call.id}><td>{new Date(call.started_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</td><td><Link to={`/calls/${call.id}`}>{call.patient?.full_name ?? call.caller_phone}</Link></td><td>{call.patient_status?.toLowerCase() ?? 'Unknown'}</td><td>{call.requested_body_part ?? '—'}<small className="cell-subtitle">{call.requested_issue_type ?? 'Not captured'}</small></td><td><StatusBadge status={call.status} /></td><td>{call.appointment?.doctor.full_name ?? '—'}</td><td>{call.appointment?.location.name ?? call.preferred_location?.name ?? '—'}</td><td>{call.appointment ? new Date(call.appointment.slot.starts_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—'}</td></tr>)}
        </DataTable>}
      </section>
    </>
  );
}
