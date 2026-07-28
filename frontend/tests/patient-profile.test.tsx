import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { PatientProfilePage } from '../src/pages/PatientProfilePage';

const profile = {
  firstName: 'Jordan',
  lastName: 'Segovia',
  fullName: 'Jordan Segovia',
  dateOfBirth: '1988-09-22',
  email: 'jordan.patient@example.com',
  phone: '+18052644217',
  insuranceProvider: 'Demo Health',
  accountCreatedAt: '2026-07-21T12:00:00+00:00',
};

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

it('loads the authenticated patient profile without exposing Encounter date labeling', async () => {
  mockProfileFetch({ '/api/patient/profile': { patient: profile } });

  renderProfile();

  expect(await screen.findByRole('heading', { name: /jordan segovia/i })).toBeInTheDocument();
  expect(screen.getByText('Account created')).toBeInTheDocument();
  expect(screen.queryByText(/encounter date/i)).not.toBeInTheDocument();
  expect(screen.getByDisplayValue('jordan.patient@example.com')).toBeInTheDocument();
  expect(screen.getByDisplayValue('+18052644217')).toBeInTheDocument();
  expect(screen.getByText('Demo Health')).toBeInTheDocument();
});

it('updates only email and phone and shows the saved values', async () => {
  const updated = { ...profile, email: 'jordan.updated@example.test', phone: '+18055559002' };
  mockProfileFetch({
    '/api/patient/profile': [
      { patient: profile },
      { patient: updated },
    ],
  });

  renderProfile();

  await userEvent.clear(await screen.findByLabelText(/^email$/i));
  await userEvent.type(screen.getByLabelText(/^email$/i), 'jordan.updated@example.test');
  await userEvent.clear(screen.getByLabelText(/phone number/i));
  await userEvent.type(screen.getByLabelText(/phone number/i), '+18055559002');
  await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

  expect(await screen.findByRole('status')).toHaveTextContent('Saved');
  expect(screen.getByDisplayValue('jordan.updated@example.test')).toBeInTheDocument();
  expect(screen.getByDisplayValue('+18055559002')).toBeInTheDocument();
  await waitFor(() => {
    expect(fetch).toHaveBeenCalledWith(
      '/api/patient/profile',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ email: 'jordan.updated@example.test', phone: '+18055559002' }),
      }),
    );
  });
});

it('displays structured validation errors without changing read-only fields', async () => {
  mockProfileFetch({
    '/api/patient/profile': {
      status: 422,
      body: {
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Only email and phone number can be updated.',
          field_errors: { firstName: ['Read-only field'] },
        },
      },
    },
  }, { initialProfile: { patient: profile } });

  renderProfile();

  expect(await screen.findByLabelText(/^email$/i)).toHaveValue('jordan.patient@example.com');
  await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

  expect(await screen.findByRole('alert')).toHaveTextContent('Only email and phone number can be updated.');
  expect(screen.getByRole('heading', { name: /jordan segovia/i })).toBeInTheDocument();
});

it('redirects to patient sign-in when the backend session expires', async () => {
  mockProfileFetch({
    '/api/patient/profile': {
      status: 401,
      body: { error: { code: 'SESSION_EXPIRED', message: 'Your session expired because of inactivity.' } },
    },
  });

  renderProfile();

  expect(await screen.findByText('Patient entry route')).toBeInTheDocument();
  expect(localStorage.getItem('patientChatSessionId')).toBeNull();
});

function renderProfile() {
  return render(
    <MemoryRouter initialEntries={['/patient/profile']}>
      <Routes>
        <Route path="/patient/profile" element={<PatientProfilePage />} />
        <Route path="/sign-in" element={<div>Patient entry route</div>} />
        <Route path="/chat" element={<div>Chat route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function mockProfileFetch(
  routes: Record<string, unknown>,
  options: { initialProfile?: unknown } = {},
) {
  const profileResponses = Array.isArray(routes['/api/patient/profile'])
    ? [...(routes['/api/patient/profile'] as unknown[])]
    : null;
  vi.stubGlobal(
    'fetch',
    vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input);
      if (path === '/api/patient/profile' && init?.method !== 'PATCH' && options.initialProfile) {
        return jsonResponse(options.initialProfile);
      }
      if (path === '/api/patient/profile' && profileResponses?.length) {
        return jsonResponse(profileResponses.shift());
      }
      const payload = routes[path];
      if (payload && isMockFailure(payload)) return jsonResponse(payload.body, false, payload.status);
      if (payload) return jsonResponse(payload);
      return jsonResponse({}, false, 404);
    }),
  );
}

function jsonResponse(body: unknown, ok = true, status = 200) {
  return Promise.resolve({ ok, status, json: async () => body });
}

function isMockFailure(value: unknown): value is { status: number; body: unknown } {
  return typeof value === 'object' && value !== null && 'status' in value && 'body' in value;
}
