import { useQuery } from '@tanstack/react-query';
import { Activity, CalendarCheck, CircleX, PhoneCall, PlugZap, RotateCcw } from 'lucide-react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { Link } from 'react-router-dom';
import { schedulingApi } from '../api/schedulingApi';
import { DataTable } from '../components/DataTable';
import { MetricCard } from '../components/MetricCard';
import { PageHeader } from '../components/PageHeader';
import { ErrorState, LoadingState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';

const chartColors = ['#16a34a', '#f59e0b', '#dc2626', '#2563eb', '#0ea5e9'];

function statusTone(state: string) {
  if (['operational', 'connected'].includes(state)) return 'ok';
  if (['not_configured', 'awaiting_credentials', 'awaiting_public_endpoint', 'ready_for_verification', 'adapter_ready', 'test_mode'].includes(state)) return 'pending';
  return 'error';
}

export function OverviewPage() {
  const query = useQuery({ queryKey: ['overview'], queryFn: schedulingApi.overview });
  if (query.isLoading) return <LoadingState label="Loading operations dashboard" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Unknown error'} />;
  const { metrics, outcomes, recent_calls: calls, upcoming_appointments: appointments, routing_exceptions: exceptions, integration_statuses: statuses } = query.data;
  const coreOperational = statuses.filter((item) => ['flask_api', 'postgresql', 'routing', 'transcripts'].includes(item.id)).every((item) => item.state === 'operational');

  return (
    <>
      <PageHeader title="Overview" subtitle="Real-time scheduling performance, patient outcomes, and routing health" actions={<Link className="button primary" to="/simulator">+ New simulation</Link>} />
      <section className="metrics-grid">
        <MetricCard label="Total calls" value={metrics.total_calls} detail="Last 30 days" icon={PhoneCall} />
        <MetricCard label="Scheduled" value={metrics.scheduled} detail={`${metrics.conversion_rate}% conversion`} icon={CalendarCheck} tone="green" />
        <MetricCard label="Redirected" value={metrics.redirected} detail="Alternative care path" icon={RotateCcw} tone="amber" />
        <MetricCard label="Failed / abandoned" value={metrics.failed + metrics.abandoned} detail="Requires review" icon={CircleX} tone="red" />
      </section>

      <section className="dashboard-grid">
        <article className="panel chart-panel">
          <div className="panel-head"><div><h2>Call outcomes</h2><p>Database-derived call status distribution</p></div><Activity size={19} /></div>
          <div className="chart-layout">
            <div className="donut-wrap">
              <ResponsiveContainer width="100%" height={230}>
                <PieChart><Pie data={outcomes} dataKey="count" nameKey="status" innerRadius={62} outerRadius={92} paddingAngle={2}>{outcomes.map((item, index) => <Cell key={item.status} fill={chartColors[index % chartColors.length]} />)}</Pie><Tooltip /></PieChart>
              </ResponsiveContainer>
              <div className="donut-center"><strong>{metrics.total_calls}</strong><span>Total calls</span></div>
            </div>
            <div className="legend-list">{outcomes.map((item, index) => <div key={item.status}><span className="legend-dot" style={{ background: chartColors[index % chartColors.length] }} /><span>{item.status.replace('_', ' ')}</span><strong>{item.count}</strong></div>)}</div>
          </div>
        </article>

        <article className="panel system-panel">
          <div className="panel-head"><div><h2>AI agent status</h2><p>Backend-derived readiness checks</p></div><PlugZap size={19} /></div>
          <div className={`system-banner ${coreOperational ? 'ok' : 'warning'}`}><CalendarCheck /><div><strong>{coreOperational ? 'Core scheduling services operational' : 'Core scheduling review required'}</strong><span>Provider integrations report their own verification state below</span></div></div>
          {statuses.map((service) => <div className="system-row" key={service.id}><span className={`status-dot ${statusTone(service.state)}`} /><span><strong className="system-name">{service.label}</strong><small>{service.detail}</small></span><strong className={`status-label ${statusTone(service.state)}`}>{service.status_label}</strong></div>)}
        </article>
      </section>

      <section className="dashboard-grid lower-grid">
        <article className="panel">
          <div className="panel-head"><div><h2>Recent calls</h2><p>Latest scheduling activity</p></div><Link to="/calls">View all</Link></div>
          <DataTable label="Recent calls" headers={['Time', 'Patient', 'Request', 'Status']}>
            {calls.map((call) => <tr key={call.id}><td>{new Date(call.started_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</td><td><Link to={`/calls/${call.id}`}>{call.patient?.full_name ?? call.caller_phone}</Link></td><td>{call.requested_body_part ?? 'Not captured'} · {call.requested_issue_type ?? 'Pending'}</td><td><StatusBadge status={call.status} /></td></tr>)}
          </DataTable>
        </article>
        <article className="panel">
          <div className="panel-head"><div><h2>Upcoming appointments</h2><p>Confirmed patient visits</p></div><Link to="/appointments">View all</Link></div>
          <DataTable label="Upcoming appointments" headers={['Time', 'Patient', 'Physician', 'Location']}>
            {appointments.map((appointment) => <tr key={appointment.id}><td>{new Date(appointment.slot.starts_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</td><td>{appointment.patient.full_name}</td><td>{appointment.doctor.full_name}</td><td>{appointment.location.name}</td></tr>)}
          </DataTable>
        </article>
      </section>

      <section className="panel exceptions-panel">
        <div className="panel-head"><div><h2>Recent routing exceptions</h2><p>Explainable protocol rejections for reviewer audit</p></div><Link to="/routing-audit">Open audit</Link></div>
        <div className="exception-grid">{exceptions.map((item) => <article key={item.id}><StatusBadge status={item.decision} /><strong>{item.doctor?.full_name ?? 'Routing engine'}</strong><p>{item.human_readable_reason}</p></article>)}</div>
      </section>
    </>
  );
}
