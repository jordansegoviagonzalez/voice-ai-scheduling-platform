import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, PhoneCall, UserRound } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';
import { schedulingApi } from '../api/schedulingApi';
import { AppointmentSummary } from '../components/AppointmentSummary';
import { PageHeader } from '../components/PageHeader';
import { RoutingTimeline } from '../components/RoutingTimeline';
import { ErrorState, LoadingState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { TranscriptTimeline } from '../components/TranscriptTimeline';

export function CallDetailPage() {
  const { callId = '' } = useParams();
  const query = useQuery({ queryKey: ['call', callId], queryFn: () => schedulingApi.call(callId), enabled: Boolean(callId) });
  if (query.isLoading) return <LoadingState label="Loading call detail" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Call not found'} />;
  const call = query.data.call;
  return (
    <>
      <Link to="/calls" className="back-link"><ArrowLeft size={16} /> Back to calls</Link>
      <PageHeader title={`Call #${call.id}`} subtitle={`${new Date(call.started_at).toLocaleString([], { dateStyle: 'long', timeStyle: 'short' })} · ${call.caller_phone}`} actions={<StatusBadge status={call.status} />} />
      <section className="detail-grid">
        <div className="detail-main">
          {call.appointment ? <AppointmentSummary appointment={call.appointment} /> : null}
          <article className="panel"><div className="panel-head"><div><h2>Full transcript</h2><p>Speaker-labeled conversation stored by the scheduling API</p></div><PhoneCall size={19} /></div><TranscriptTimeline turns={call.transcript ?? []} /></article>
        </div>
        <aside className="detail-sidebar">
          <article className="panel"><div className="panel-head"><div><h2>Patient request</h2></div><UserRound size={19} /></div><dl className="detail-list"><div><dt>Patient</dt><dd>{call.patient?.full_name ?? 'Unidentified caller'}</dd></div><div><dt>Patient status</dt><dd>{call.patient_status ?? 'Unknown'}</dd></div><div><dt>Body part</dt><dd>{call.requested_body_part ?? 'Not captured'}</dd></div><div><dt>Issue type</dt><dd>{call.requested_issue_type ?? 'Not captured'}</dd></div><div><dt>Preferred physician</dt><dd>{call.preferred_doctor?.full_name ?? 'No preference'}</dd></div><div><dt>Preferred location</dt><dd>{call.preferred_location?.name ?? 'No preference'}</dd></div></dl>{call.failure_reason ? <div className="alert-box error"><strong>Failure reason</strong><p>{call.failure_reason}</p></div> : null}{call.redirect_summary ? <div className="alert-box warning"><strong>Redirect summary</strong><p>{call.redirect_summary}</p></div> : null}</article>
          <article className="panel"><div className="panel-head"><div><h2>Routing timeline</h2><p>Why each physician was accepted or rejected</p></div></div><RoutingTimeline decisions={call.routing_decisions ?? []} /></article>
        </aside>
      </section>
    </>
  );
}
