import { render, screen } from '@testing-library/react';
import { AppointmentSummary } from '../src/components/AppointmentSummary';
import { EmptyState, ErrorState } from '../src/components/States';
import { RoutingTimeline } from '../src/components/RoutingTimeline';
import { StatusBadge } from '../src/components/StatusBadge';
import { TranscriptTimeline } from '../src/components/TranscriptTimeline';
import type { Appointment, RoutingDecision, TranscriptTurn } from '../src/types/api';

const doctor = {
  id: 1,
  first_name: 'Elena',
  last_name: 'Vasquez',
  full_name: 'Dr. Elena Vasquez',
  accepts_new_patients: true,
  active: true,
  locations: [{ id: 1, code: 'MAIN', name: 'Main Campus' }],
  capabilities: [{ body_part: 'Knee', issue_type: 'Fracture' }],
};

const patient = {
  id: 1,
  first_name: 'Taylor',
  last_name: 'Demo',
  full_name: 'Taylor Demo',
  date_of_birth: '1990-01-01',
  phone: '+18055550100',
  email: null,
};

it('renders status badges', () => {
  render(<StatusBadge status="SCHEDULED" />);
  expect(screen.getByText('Scheduled')).toBeInTheDocument();
});

it('renders transcript speaker labels and text', () => {
  const turns: TranscriptTurn[] = [{ id: 1, sequence_number: 1, speaker: 'AI', text: 'How can I help?', occurred_at: '2026-07-20T10:00:00Z' }];
  render(<TranscriptTimeline turns={turns} />);
  expect(screen.getByText('Scheduling Assistant')).toBeInTheDocument();
  expect(screen.getByText('How can I help?')).toBeInTheDocument();
});

it('renders a human-readable routing rejection', () => {
  const decision: RoutingDecision = {
    id: 1,
    call_id: 1,
    patient_id: 1,
    doctor,
    decision: 'REJECTED',
    reason_code: 'ISSUE_TYPE_NOT_SUPPORTED',
    human_readable_reason: 'Dr. Elena Vasquez does not treat this request.',
    request_context: {},
    created_at: '2026-07-20T10:00:00Z',
  };
  render(<RoutingTimeline decisions={[decision]} />);
  expect(screen.getByText('Dr. Elena Vasquez does not treat this request.')).toBeInTheDocument();
});

it('renders appointment summary', () => {
  const appointment: Appointment = {
    id: 1,
    patient,
    doctor,
    location: doctor.locations[0],
    slot: { id: 2, starts_at: '2026-07-22T16:00:00Z', ends_at: '2026-07-22T16:45:00Z', status: 'BOOKED', location: doctor.locations[0] },
    body_part: 'Knee',
    issue_type: 'Fracture',
    status: 'SCHEDULED',
    booking_source: 'SIMULATOR',
    call_id: 1,
    created_at: '2026-07-20T10:00:00Z',
  };
  render(<AppointmentSummary appointment={appointment} />);
  expect(screen.getByText('Taylor Demo')).toBeInTheDocument();
  expect(screen.getByText('Dr. Elena Vasquez')).toBeInTheDocument();
});

it('renders empty and error states', () => {
  const { rerender } = render(<EmptyState title="No calls" detail="Nothing here" />);
  expect(screen.getByText('No calls')).toBeInTheDocument();
  rerender(<ErrorState message="Network failure" />);
  expect(screen.getByText('Network failure')).toBeInTheDocument();
});
