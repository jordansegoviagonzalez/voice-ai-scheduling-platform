import { useMutation, useQuery } from '@tanstack/react-query';
import { CheckCircle2, FlaskConical, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { schedulingApi } from '../api/schedulingApi';
import { AppointmentSummary } from '../components/AppointmentSummary';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/States';
import type { Appointment, RoutingResponse } from '../types/api';

interface SimulatorContext {
  callId: number;
  patientId: number;
  bodyPart: string;
  issueType: string;
  routing: RoutingResponse;
}

export function SimulatorPage() {
  const protocol = useQuery({ queryKey: ['protocol'], queryFn: schedulingApi.protocol });
  const [context, setContext] = useState<SimulatorContext | null>(null);
  const [appointment, setAppointment] = useState<Appointment | null>(null);
  const preview = useMutation({
    mutationFn: schedulingApi.simulatorPreview,
    onSuccess: (data, variables) => {
      setAppointment(null);
      setContext({ callId: data.call.id, patientId: data.patient.id, bodyPart: String(variables.body_part), issueType: String(variables.issue_type), routing: data.routing });
    },
  });
  const booking = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      const confirmed = await schedulingApi.bookingConfirmation({ ...body, source: 'SIMULATOR' });
      return schedulingApi.simulatorBook({
        ...body,
        confirmation_token: confirmed.confirmation.confirmation_token,
      });
    },
    onSuccess: (data) => setAppointment(data.appointment),
  });
  if (protocol.isError) return <ErrorState message={protocol.error.message} />;

  return (
    <>
      <PageHeader title="Call Simulator" subtitle="Developer demo tool using the same patient, routing, slot, booking, transcript, and audit services as Vogent" />
      <div className="simulator-banner"><FlaskConical /><div><strong>This is not a replacement for Vogent.</strong><span>It provides a credential-independent, reproducible demonstration of the identical backend workflow.</span></div></div>
      <section className="simulator-grid">
        <form className="panel simulator-form" onSubmit={(event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          preview.mutate(Object.fromEntries(form.entries()));
        }}>
          <div className="panel-head"><div><h2>Patient and request</h2><p>One focused scheduling scenario</p></div><ShieldCheck size={19} /></div>
          <div className="form-grid">
            <label>First name<input name="first_name" defaultValue="Jordan" required /></label>
            <label>Last name<input name="last_name" defaultValue="Demo" required /></label>
            <label>Caller phone<input name="caller_phone" defaultValue="+18055550991" required /></label>
            <label>Date of birth<input name="date_of_birth" type="date" defaultValue="1991-09-15" required /></label>
            <label>Patient status<select name="patient_status" defaultValue="NEW"><option>NEW</option><option>RETURNING</option></select></label>
            <label>Body part<select name="body_part" defaultValue="Knee">{protocol.data?.body_parts.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Issue type<select name="issue_type" defaultValue="Fracture">{protocol.data?.issue_types.map((item) => <option key={item}>{item}</option>)}</select></label>
            <label>Preferred physician<select name="preferred_doctor_id" defaultValue=""><option value="">No preference</option>{protocol.data?.doctors.map((doctor) => <option key={doctor.id} value={doctor.id}>{doctor.full_name}</option>)}</select></label>
            <label>Preferred location<select name="preferred_location_id" defaultValue=""><option value="">No preference</option>{protocol.data?.locations.map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
          </div>
          <button className="button primary full-width" type="submit" disabled={preview.isPending}>{preview.isPending ? 'Evaluating protocol…' : 'Run routing evaluation'}</button>
          {preview.isError ? <div className="alert-box error"><p>{preview.error.message}</p></div> : null}
        </form>

        <section className="panel simulator-results">
          <div className="panel-head"><div><h2>Routing result</h2><p>Live database availability and human-readable reasons</p></div></div>
          {!context ? <div className="simulator-placeholder"><FlaskConical /><h3>Ready to simulate</h3><p>Submit the request to create a patient, call record, transcript, and routing audit.</p></div> : <>
            <div className="routing-summary"><CheckCircle2 /><p>{context.routing.caller_safe_summary}</p></div>
            {context.routing.rejected_doctors.filter((item) => item.is_preferred_doctor).map((item) => <div className="rejection-card" key={item.doctor.id}><strong>{item.doctor.full_name} was not selected</strong><p>{item.reason}</p></div>)}
            {context.routing.ranked_recommendations.map((item, index) => <article className="recommendation-card" key={item.doctor.id}><div><span>Option {index + 1}</span><h3>{item.doctor.full_name}</h3><p>{item.available_slots[0]?.location.name}</p></div><div className="slot-buttons">{item.available_slots.slice(0, 3).map((slot) => <button className="button secondary" type="button" key={slot.id} disabled={booking.isPending || Boolean(appointment)} onClick={() => booking.mutate({ call_id: context.callId, patient_id: context.patientId, slot_id: slot.id, body_part: context.bodyPart, issue_type: context.issueType })}>{new Date(slot.starts_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</button>)}</div></article>)}
            {booking.isError ? <div className="alert-box error"><p>{booking.error.message}</p></div> : null}
          </>}
        </section>
      </section>
      {appointment ? <AppointmentSummary appointment={appointment} /> : null}
    </>
  );
}
