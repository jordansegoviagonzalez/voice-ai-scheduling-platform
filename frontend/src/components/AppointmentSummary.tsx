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
        <div><CalendarDays /><span>Date & time</span><strong>{new Date(appointment.slot.starts_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}</strong></div>
      </div>
    </section>
  );
}
