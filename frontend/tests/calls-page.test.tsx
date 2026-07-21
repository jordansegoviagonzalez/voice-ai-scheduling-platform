import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, vi } from 'vitest';
import { CallsPage } from '../src/pages/CallsPage';

const response = {
  calls: [
    {
      id: 1,
      external_call_id: null,
      status: 'SCHEDULED',
      caller_phone: '+18055550100',
      patient_status: 'NEW',
      requested_body_part: 'Knee',
      requested_issue_type: 'Fracture',
      started_at: '2026-07-20T10:00:00Z',
      ended_at: null,
      patient: { id: 1, first_name: 'Taylor', last_name: 'Demo', full_name: 'Taylor Demo', date_of_birth: '1990-01-01', phone: '+18055550100', email: null },
      preferred_doctor: null,
      preferred_location: null,
      appointment: null,
      failure_reason: null,
      redirect_summary: null,
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it('renders API call data and filters it', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => response }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CallsPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('Taylor Demo')).toBeInTheDocument();
  await userEvent.type(screen.getByLabelText('Search calls'), 'shoulder');
  expect(screen.getByText('No calls match these filters')).toBeInTheDocument();
});

it('renders API errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({ error: { message: 'Service unavailable' } }) }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CallsPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('Service unavailable')).toBeInTheDocument();
});
