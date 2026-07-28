import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthProvider } from '../src/context/AuthContext';
import { ChatPage } from '../src/pages/ChatPage';
import { SignInPage } from '../src/pages/SignInPage';

const genericEntryQuestion = 'Hi, I can help you schedule an orthopedic appointment. Are you a new or returning patient?';
const jordanWelcome = 'Welcome back, Olivia. What is the reason for your visit today?';
const joseWelcome = 'Welcome, Jose. What is the reason for your visit today?';
const patientProfile = {
  patient: {
    firstName: 'Jordan',
    lastName: 'Segovia',
    fullName: 'Olivia Carter',
    dateOfBirth: '1993-06-12',
    email: 'olivia.carter.phase2.demo@example.com',
    phone: '+18055550187',
    insuranceProvider: null,
    accountCreatedAt: '2026-07-21T12:00:00+00:00',
  },
};

const returningSession = sessionPayload(51, jordanWelcome, {
  patient_type: 'returning',
  full_name: 'Olivia Carter',
});
const newSession = sessionPayload(52, joseWelcome, {
  patient_type: 'new',
  full_name: 'Jose Rivera',
  insurance_provider: 'Acme Health',
});

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('offers patient-first entry choices with staff access secondary', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');

  expect(await screen.findByRole('button', { name: /^new patient$/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /^returning patient$/i })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /clinic staff access/i })).toBeInTheDocument();
});

it('reveals the returning-patient credential flow', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^returning patient$/i }));

  expect(screen.getByRole('heading', { name: /returning patient/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/email address/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
});

it('reveals the new-patient registration flow', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));

  expect(screen.getByRole('heading', { name: /new patient registration/i })).toBeInTheDocument();
  expect(screen.getByLabelText(/first name/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/last name/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/date of birth/i)).toHaveValue('');
  expect(screen.getByLabelText(/contact number/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/insurance provider/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/^password$/i)).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText(/^password$/i)).toHaveAttribute('autocomplete', 'new-password');
  expect(screen.getByLabelText(/confirm password/i)).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText(/confirm password/i)).toHaveAttribute('autocomplete', 'new-password');
  expect(screen.getByText(/use this email and password to return/i)).toBeInTheDocument();
  expect(fieldOrder()).toEqual([
    'First name',
    'Last name',
    'Date of birth',
    'Contact number',
    'Email',
    'Insurance provider',
    'Password',
    'Confirm password',
  ]);
});

it('blocks new-patient registration when password confirmation does not match', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));
  await userEvent.type(screen.getByLabelText(/^password$/i), 'correct horse battery staple');
  await userEvent.type(screen.getByLabelText(/confirm password/i), 'correct horse battery staples');

  expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match.');
  expect(screen.getByRole('button', { name: /continue to scheduling chat/i })).toBeDisabled();
});

it('blocks new-patient registration when the password is too short', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));
  await userEvent.type(screen.getByLabelText(/^password$/i), 'short');
  await userEvent.type(screen.getByLabelText(/confirm password/i), 'short');

  expect(screen.getByRole('button', { name: /continue to scheduling chat/i })).toBeDisabled();
});

it('keeps date of birth blank and blocks future date values', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));
  const dob = screen.getByLabelText(/date of birth/i);

  expect(dob).toHaveValue('');
  await userEvent.type(dob, '2999-01-01');

  expect(await screen.findByRole('alert')).toHaveTextContent('Date of birth cannot be in the future.');
  expect(screen.getByRole('button', { name: /continue to scheduling chat/i })).toBeDisabled();
});

it('toggles new-patient password visibility without exposing it by default', async () => {
  mockFetch();

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));
  const passwordInput = screen.getByLabelText(/^password$/i);

  expect(passwordInput).toHaveAttribute('type', 'password');
  await userEvent.click(screen.getAllByRole('button', { name: /show password/i })[0]);
  expect(passwordInput).toHaveAttribute('type', 'text');
  await userEvent.click(screen.getAllByRole('button', { name: /hide password/i })[0]);
  expect(passwordInput).toHaveAttribute('type', 'password');
});

it('authenticates a returning patient and renders one personalized transcript welcome', async () => {
  mockFetch({
    '/api/chat/sessions': returningSession,
    '/api/chat/sessions/51': returningSession,
  });

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^returning patient$/i }));
  await userEvent.type(screen.getByLabelText(/email address/i), 'olivia.carter.phase2.demo@example.com');
  await userEvent.type(screen.getByLabelText(/^password$/i), 'Patient!2026');
  await userEvent.click(screen.getByRole('button', { name: /continue to scheduling chat/i }));

  expect(await screen.findByText(jordanWelcome)).toBeInTheDocument();
  expect(screen.queryByText(genericEntryQuestion)).not.toBeInTheDocument();
  expect(screen.getAllByText(jordanWelcome)).toHaveLength(1);
  expect(localStorage.getItem('patientChatSessionId')).toBe('51');
});

it('registers a new patient and renders one personalized transcript welcome', async () => {
  mockFetch({
    '/api/chat/sessions': newSession,
    '/api/chat/sessions/52': newSession,
  });

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^new patient$/i }));
  await userEvent.type(screen.getByLabelText(/first name/i), 'Jose');
  await userEvent.type(screen.getByLabelText(/last name/i), 'Rivera');
  await userEvent.type(screen.getByLabelText(/date of birth/i), '1994-05-04');
  await userEvent.type(screen.getByLabelText(/contact number/i), '8055554001');
  await userEvent.type(screen.getByLabelText(/^email$/i), 'jose.rivera@example.test');
  await userEvent.type(screen.getByLabelText(/insurance provider/i), 'Acme Health');
  await userEvent.type(screen.getByLabelText(/^password$/i), 'correct horse battery staple');
  await userEvent.type(screen.getByLabelText(/confirm password/i), 'correct horse battery staple');
  await userEvent.click(screen.getByRole('button', { name: /continue to scheduling chat/i }));

  expect(await screen.findByText(joseWelcome)).toBeInTheDocument();
  expect(screen.queryByText(genericEntryQuestion)).not.toBeInTheDocument();
  expect(screen.queryByText(/what is your full name/i)).not.toBeInTheDocument();
  expect(screen.getAllByText(joseWelcome)).toHaveLength(1);
  expect(localStorage.getItem('patientChatSessionId')).toBe('52');
  expect(localStorage.getItem('correct horse battery staple')).toBeNull();
  await waitFor(() => {
    expect(fetch).toHaveBeenCalledWith(
      '/api/chat/sessions',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          patientMode: 'new',
          firstName: 'Jose',
          lastName: 'Rivera',
          dateOfBirth: '1994-05-04',
          phone: '8055554001',
          email: 'jose.rivera@example.test',
          password: 'correct horse battery staple',
          confirmPassword: 'correct horse battery staple',
          insuranceProvider: 'Acme Health',
        }),
      }),
    );
  });
});

it('redirects direct chat navigation without a valid patient session to entry', async () => {
  mockFetch();

  renderChatOnly('/chat');

  expect(await screen.findByText('Patient entry route')).toBeInTheDocument();
});

it('restores an existing session without duplicating the welcome', async () => {
  localStorage.setItem('patientChatSessionId', '51');
  mockFetch({ '/api/chat/sessions/51': returningSession });

  renderChatOnly('/chat');

  expect(await screen.findByText(jordanWelcome)).toBeInTheDocument();
  expect(screen.getAllByText(jordanWelcome)).toHaveLength(1);
});

it('redirects direct chat navigation when stored session access is unauthorized', async () => {
  localStorage.setItem('patientChatSessionId', '99');
  mockFetch({ '/api/chat/sessions/99': unauthorizedPayload() });

  renderChatOnly('/chat');

  expect(await screen.findByText('Patient entry route')).toBeInTheDocument();
  expect(localStorage.getItem('patientChatSessionId')).toBeNull();
});

it('shows accessible errors for failed returning-patient authentication', async () => {
  mockFetch({ '/api/chat/sessions': unauthorizedPayload() });

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /^returning patient$/i }));
  await userEvent.type(screen.getByLabelText(/email address/i), 'olivia.carter.phase2.demo@example.com');
  await userEvent.type(screen.getByLabelText(/^password$/i), 'wrong-password');
  await userEvent.click(screen.getByRole('button', { name: /continue to scheduling chat/i }));

  const alert = await screen.findByRole('alert');
  expect(alert).toHaveTextContent('We could not verify those patient details.');
  expect(alert).toHaveFocus();
  expect(screen.queryByText(/jordan segovia/i)).not.toBeInTheDocument();
});

it('keeps admin authentication available as a separate staff path', async () => {
  const adminSession = { authenticated: true, name: 'Dr. James Walsh', email: 'admin@example.com', role: 'admin_provider' };
  mockFetch({ '/api/auth/admin/login': adminSession });

  renderEntry('/sign-in?role=patient');
  await userEvent.click(await screen.findByRole('button', { name: /clinic staff access/i }));
  await userEvent.type(screen.getByLabelText(/email address/i), 'admin@example.com');
  await userEvent.type(screen.getByLabelText(/^password$/i), 'admin123');
  await userEvent.click(screen.getByRole('button', { name: /sign in to operations console/i }));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/auth/admin/login', expect.any(Object)));
});

function renderEntry(initialPath: string) {
  return render(
    <AuthProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/sign-in" element={<SignInPage />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/" element={<div>Admin route</div>} />
        </Routes>
      </MemoryRouter>
    </AuthProvider>,
  );
}

function renderChatOnly(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/sign-in" element={<div>Patient entry route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockFetch(routes: Record<string, unknown> = {}) {
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL) => {
      const path = String(input);
      if (path === '/api/auth/admin/session') return jsonResponse({}, false, 401);
      if (path === '/api/patient/profile') return jsonResponse(patientProfile);
      const payload = routes[path];
      if (payload && isMockFailure(payload)) {
        return jsonResponse(payload.body, false, payload.status);
      }
      if (payload) return jsonResponse(payload);
      return jsonResponse({}, false, 404);
    }),
  );
}

function fieldOrder() {
  return screen
    .getAllByLabelText(/first name|last name|date of birth|contact number|^email$|insurance provider|^password$|confirm password/i)
    .map((input) => input.closest('label')?.querySelector('span')?.textContent);
}

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: async () => body });
}

function unauthorizedPayload() {
  return {
    status: 401,
    body: {
      error: {
        code: 'UNAUTHORIZED',
        message: 'We could not verify those patient details.',
        field_errors: {},
      },
    },
  };
}

function isMockFailure(value: unknown): value is { status: number; body: unknown } {
  return typeof value === 'object' && value !== null && 'status' in value && 'body' in value;
}

function sessionPayload(sessionId: number, welcome: string, collectedData: Record<string, unknown>) {
  return {
    sessionId,
    status: 'collecting_intake',
    currentStep: 'collect_intake',
    messages: [{ role: 'assistant', content: welcome, sequenceNumber: 1 }],
    assistantMessage: { role: 'assistant', content: welcome, sequenceNumber: 1 },
    collectedData,
    recommendations: [],
    availableSlots: [],
    booking: null,
    escalation: null,
  };
}
