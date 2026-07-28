import { useQuery } from '@tanstack/react-query';
import { schedulingApi } from '../api/schedulingApi';
import { DataTable } from '../components/DataTable';
import { PageHeader } from '../components/PageHeader';
import { EmptyState, ErrorState, LoadingState } from '../components/States';
import { StatusBadge } from '../components/StatusBadge';
import { Link } from 'react-router-dom';

export function AppointmentsPage() {
  const query = useQuery({ queryKey: ['appointments'], queryFn: schedulingApi.appointments });
  if (query.isLoading) return <LoadingState label="Loading appointments" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Unknown error'} />;
  const appointments = query.data.appointments;
  return (
    <>
      <PageHeader title="Appointments" subtitle="Confirmed bookings created by the voice agent and local simulator" />
      <section className="panel">
        {appointments.length === 0 ? <EmptyState title="No appointments yet" detail="Use the simulator or Vogent flow to create the first booking." /> : <DataTable label="Appointments" headers={['Patient', 'Physician', 'Location', 'Request', 'Date / time', 'Source', 'Status', 'Record']}>
          {appointments.map((appointment) => <tr key={appointment.id}>
            <td>
              {appointment.booking_source === 'WEB_CHAT' && appointment.chat_session_id ? (
                <Link to={`/web-chat-sessions/${appointment.chat_session_id}`}>{appointment.patient.full_name}</Link>
              ) : appointment.booking_source === 'VOGENT' && appointment.call_id ? (
                <Link to={`/calls/${appointment.call_id}`}>{appointment.patient.full_name}</Link>
              ) : appointment.booking_source === 'SIMULATOR' && appointment.call_id ? (
                <Link to={`/calls/${appointment.call_id}`}>{appointment.patient.full_name}</Link>
              ) : (
                appointment.patient.full_name
              )}
              <small className="cell-subtitle">{appointment.patient.phone}</small>
            </td>
            <td>{appointment.doctor.full_name}</td><td>{appointment.location.name}</td><td>{appointment.body_part}<small className="cell-subtitle">{appointment.issue_type}</small></td><td>{formatSlotDateTime(appointment.slot)}</td><td>{appointment.booking_source}</td><td><StatusBadge status={appointment.status} /></td>
          <td>
            {appointment.booking_source === 'WEB_CHAT' && appointment.chat_session_id ? <Link to={`/web-chat-sessions/${appointment.chat_session_id}`}>View web chat</Link> :
             appointment.booking_source === 'VOGENT' && appointment.call_id ? <Link to={`/calls/${appointment.call_id}`}>View call</Link> :
             appointment.booking_source === 'SIMULATOR' && appointment.call_id ? <Link to={`/calls/${appointment.call_id}`}>View simulator record</Link> :
             <span style={{ color: '#64748b' }}>Transcript unavailable</span>}
          </td></tr>)}
        </DataTable>}
      </section>
    </>
  );
}

function formatSlotDateTime(slot: { starts_at: string; display_datetime?: string }) {
  if (slot.display_datetime) return slot.display_datetime;
  return new Date(slot.starts_at).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Los_Angeles',
  });
}
