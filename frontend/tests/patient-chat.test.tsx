import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { ChatPage } from '../src/pages/ChatPage';

const patientProfile = {
  firstName: 'Jordan',
  lastName: 'Segovia',
  fullName: 'Jordan Segovia',
  dateOfBirth: '1988-09-22',
  email: 'jordan.patient@example.com',
  phone: '+18052644217',
  insuranceProvider: 'Demo Health',
  accountCreatedAt: '2026-07-21T12:00:00+00:00',
};

const collectingSession = {
  sessionId: 42,
  status: 'collecting_intake',
  currentStep: 'collect_intake',
  messages: [
    { role: 'assistant', content: 'Welcome back, Jordan. What is the reason for your visit today?', sequenceNumber: 1 },
  ],
  collectedData: {
    patient_type: 'returning',
    full_name: 'Jordan Segovia',
  },
  recommendations: [],
  availableSlots: [],
  booking: null,
  escalation: null,
};

const SLOT_120 = {
  id: 120,
  starts_at: '2026-08-03T09:00:00+00:00',
  ends_at: '2026-08-03T09:45:00+00:00',
  display_date: 'Aug 3',
  display_time: '9:00 AM',
  display_datetime: 'Monday, August 3 at 9:00 AM',
  location: { id: 2, code: 'NORTH', name: 'North Clinic' },
};

const WALSH_REC = {
  physician_id: 7,
  physician_name: 'Dr. James Walsh',
  initials: 'JW',
  specialty: 'Knee Fracture',
  match_explanation: 'Dr. James Walsh matches the Knee fracture protocol and has real open slots.',
  labels: ['Recommended'],
  // Canonical location-grouped shape (current backend)
  locations: [
    {
      clinic_location: 'North Clinic',
      clinic_location_code: 'NORTH',
      is_preferred: true,
      labels: [],
      available_slots: [SLOT_120],
    },
  ],
};

const selectingSession = {
  ...collectingSession,
  status: 'selecting_appointment',
  currentStep: 'slot_selection',
  routingResult: {},
  collectedData: {
    ...collectingSession.collectedData,
    chief_complaint: 'knee fracture',
    body_part: 'Knee',
    issue_type: 'Fracture',
    appointment_type: 'urgent',
    preferred_location: 'NORTH',
    preferred_date_or_time: 'earliest available',
    preferred_time_of_day: 'morning',
  },
  recommendations: [WALSH_REC],
  availableSlots: [SLOT_120],
};

const confirmedSession = {
  ...selectingSession,
  status: 'confirmed',
  currentStep: 'booking_confirmation',
  recommendations: [],
  availableSlots: [],
  booking: {
    id: 12,
    doctor: { full_name: 'Dr. James Walsh' },
    location: { name: 'North Clinic' },
    slot: {
      starts_at: '2026-08-03T09:00:00+00:00',
      ends_at: '2026-08-03T09:45:00+00:00',
      display_datetime: 'Monday, August 3 at 9:00 AM',
    },
    issue_type: 'Fracture',
    body_part: 'Knee',
    patient: { full_name: 'Jordan Segovia', phone: '+18052644217', email: 'jordan.patient@example.com' },
  },
};

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('renders a patient-facing progress dropdown instead of raw chat state', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': collectingSession, '/api/patient/profile': { patient: patientProfile } });

  render(<MemoryRouter initialEntries={['/chat']}><ChatPage /></MemoryRouter>);

  const trigger = await screen.findByRole('button', { name: /scheduling progress: intake in progress/i });
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText('collecting intake')).not.toBeInTheDocument();

  await userEvent.click(trigger);

  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('dialog', { name: /scheduling progress/i })).toBeInTheDocument();
  expect(screen.getByText('Patient verified')).toBeInTheDocument();
  expect(screen.getByText('Reason for visit')).toBeInTheDocument();
  expect(screen.getByText('Current')).toBeInTheDocument();
});

it('shows a backend-derived patient account menu separate from appointment details', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': confirmedSession, '/api/patient/profile': { patient: patientProfile } });

  renderChatRoutes('/chat');

  const account = await screen.findByRole('button', { name: /jordan segovia/i });
  expect(account).toHaveAttribute('aria-haspopup', 'menu');

  await userEvent.click(account);

  const menu = screen.getByRole('menu', { name: /patient account/i });
  expect(menu).toBeInTheDocument();
  expect(screen.getByRole('menuitem', { name: /profile/i })).toBeInTheDocument();
  expect(screen.getByRole('menuitem', { name: /sign out/i })).toBeInTheDocument();
  expect(menu).not.toHaveTextContent('Appointment 12');
  expect(menu).not.toHaveTextContent('Dr. James Walsh');
});

it('keeps confirmed appointment details hidden until the status disclosure is expanded', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': confirmedSession, '/api/patient/profile': { patient: patientProfile } });

  renderChatRoutes('/chat');

  const trigger = await screen.findByRole('button', { name: /scheduling progress: appointment confirmed/i });
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText('Appointment 12')).not.toBeInTheDocument();
  expect(screen.queryByText('+18052644217 / jordan.patient@example.com')).not.toBeInTheDocument();

  await userEvent.click(trigger);

  expect(trigger).toHaveAttribute('aria-expanded', 'true');
  expect(screen.getByRole('dialog', { name: /appointment confirmed details/i })).toBeInTheDocument();
  expect(screen.getByText('Appointment 12')).toBeInTheDocument();
  expect(screen.getByText('Dr. James Walsh')).toBeInTheDocument();
  expect(screen.getByText('+18052644217 / jordan.patient@example.com')).toBeInTheDocument();
  expect(screen.getAllByText('Appointment confirmation')).toHaveLength(1);

  await userEvent.keyboard('{Escape}');
  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByText('Appointment 12')).not.toBeInTheDocument();
});

it('closes the status disclosure on outside click', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': collectingSession, '/api/patient/profile': { patient: patientProfile } });

  renderChatRoutes('/chat');

  const trigger = await screen.findByRole('button', { name: /scheduling progress: intake in progress/i });
  await userEvent.click(trigger);
  expect(trigger).toHaveAttribute('aria-expanded', 'true');

  await userEvent.click(document.body);

  expect(trigger).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('dialog', { name: /scheduling progress/i })).not.toBeInTheDocument();
});

it('keeps physician slots and review controls visible before booking', async () => {
  localStorage.setItem('patientChatSessionId', '42');

  // selectResponse simulates the backend's server-authoritative selection:
  // - selected_slot_id matches the actual clicked slot (120)
  // - availableSlots contains that slot so applySession can resolve it
  const selectResponse = {
    ...selectingSession,
    routingResult: {
      selected_slot_id: SLOT_120.id,
      selected_recommendation: WALSH_REC,
    },
    availableSlots: [SLOT_120],
  };

  mockChatFetch({
    '/api/chat/sessions/42': selectingSession,
    '/api/chat/sessions/42/appointments/select': selectResponse,
    '/api/patient/profile': { patient: patientProfile },
  });

  renderChatRoutes('/chat');

  expect(await screen.findByRole('heading', { name: /recommended physicians/i })).toBeInTheDocument();
  expect(screen.getByText('Times shown in clinic local time.')).toBeInTheDocument();
  expect(screen.queryByText('Times shown in UTC.')).not.toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /dr\. james walsh/i })).toBeInTheDocument();

  // Slot button renders from canonical locations shape
  await userEvent.click(screen.getByRole('button', { name: /9:00 am/i }));

  // Review panel must only render after the server responds with a successful selection
  expect(await screen.findByRole('heading', { name: /review appointment/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /change time/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /confirm appointment/i })).toBeInTheDocument();
});

it('uses an accessible retry-friendly textarea composer', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': collectingSession, '/api/patient/profile': { patient: patientProfile } });

  render(<MemoryRouter initialEntries={['/chat']}><ChatPage /></MemoryRouter>);

  const composer = await screen.findByLabelText('Message the scheduling assistant');
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/chat/sessions/42', expect.any(Object)));
  expect(composer.tagName).toBe('TEXTAREA');
  expect(composer).toHaveAttribute('placeholder', 'Message the scheduling assistant');
  expect(composer).toHaveAttribute('spellcheck', 'true');
  expect(screen.getByRole('button', { name: /send/i })).toBeDisabled();
});

it('signs out through the backend and clears the stored chat session', async () => {
  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({
    '/api/chat/sessions/42': confirmedSession,
    '/api/patient/profile': { patient: patientProfile },
    '/api/patient/logout': { success: true },
  });

  renderChatRoutes('/chat');

  await userEvent.click(await screen.findByRole('button', { name: /jordan segovia/i }));
  await userEvent.click(screen.getByRole('menuitem', { name: /sign out/i }));

  expect(await screen.findByText('Patient entry route')).toBeInTheDocument();
  expect(localStorage.getItem('patientChatSessionId')).toBeNull();
  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/patient/logout', expect.any(Object)));
});

it('handles varying recommendation payload shapes safely', async () => {
  const malformedSession = {
    ...selectingSession,
    recommendations: [
      {
        physician_id: 1,
        physician_name: 'Dr. One',
        locations: [{ clinic_location: 'Clinic 1', clinic_location_code: 'C1', is_preferred: false, labels: [], available_slots: [{ id: 101, starts_at: '2026-08-01T09:00:00Z', location: { id: 1, name: 'Clinic 1', code: 'C1' } }] }]
      },
      {
        physician_id: 2,
        physician_name: 'Dr. Two',
        available_slots: [{ id: 102, starts_at: '2026-08-01T10:00:00Z', location: { id: 2, code: 'C2', name: 'Clinic 2' } }]
      },
      {
        physician_id: 3,
        physician_name: 'Dr. Three'
      },
      {
        physician_id: 4,
        physician_name: 'Dr. Four',
        locations: [{ clinic_location: 'Clinic 4', clinic_location_code: 'C4', is_preferred: false, labels: [] }]
      },
      {
        physician_id: 5,
        physician_name: 'Dr. Five',
        locations: [{ clinic_location: 'Clinic 5', clinic_location_code: 'C5', is_preferred: false, labels: [], available_slots: null }],
        available_slots: null
      }
    ]
  };

  localStorage.setItem('patientChatSessionId', '42');
  mockChatFetch({ '/api/chat/sessions/42': malformedSession, '/api/patient/profile': { patient: patientProfile } });

  renderChatRoutes('/chat');

  expect(await screen.findByRole('heading', { name: /dr\. one/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /dr\. two/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /dr\. three/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /dr\. four/i })).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: /dr\. five/i })).toBeInTheDocument();
  expect(screen.getByText('Clinic 2')).toBeInTheDocument();
});

function renderChatRoutes(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/patient/profile" element={<div>Patient profile route</div>} />
        <Route path="/sign-in" element={<div>Patient entry route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockChatFetch(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      const payload = routes[path];
      if (payload) return jsonResponse(payload);
      return jsonResponse({}, false, 404);
    }),
  );
}

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: async () => body });
}
