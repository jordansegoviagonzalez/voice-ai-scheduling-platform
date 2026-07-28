import { CalendarDays, MapPin, Stethoscope, UserRound } from 'lucide-react';
import type { Appointment } from '../types/api';

export function AppointmentSummary({ appointment }: { appointment: Appointment }) {
  return (
    <section className="appointment-summary">
      <h3>Confirmed appointment</h3>
      <div className="summary-grid">
        <div><UserRound /><span>Patient</span><strong>{appointment.patient.full_name}</strong></div>
        <div><Stethoscope /><span>Physician</span><strong>{appointment.doctor.full_name}</strong></div>
        <div><MapPin /><span>Location</span><strong>{appointment.location.name}</strong></div>
        <div><CalendarDays /><span>Date & time</span><strong>{formatSlotDateTime(appointment.slot)}</strong></div>
      </div>
    </section>
  );
}

function formatSlotDateTime(slot: Appointment['slot']) {
  if (slot.display_datetime) return slot.display_datetime;
  return new Date(slot.starts_at).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Los_Angeles',
  });
}
