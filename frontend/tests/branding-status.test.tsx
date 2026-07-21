import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AppLayout } from '../src/layouts/AppLayout';
import { OverviewPage } from '../src/pages/OverviewPage';

const overview = {
  metrics: { total_calls: 1, scheduled: 0, redirected: 0, abandoned: 0, failed: 0, in_progress: 1, conversion_rate: 0 },
  outcomes: [{ status: 'IN_PROGRESS', count: 1 }],
  recent_calls: [],
  upcoming_appointments: [],
  routing_exceptions: [],
  integration_statuses: [
    {
      id: 'flask_api',
      label: 'Flask Scheduling API',
      state: 'operational',
      status_label: 'Operational',
      detail: 'Backend API responded from the active app process.',
      checked_at: '2026-07-20T10:00:00Z',
      last_success_at: '2026-07-20T10:00:00Z',
      metadata: {},
    },
    {
      id: 'openai_gpt_5_2',
      label: 'OpenAI GPT-5.2',
      state: 'not_configured',
      status_label: 'Not configured',
      detail: 'OPENAI_API_KEY is not configured for the backend.',
      checked_at: '2026-07-20T10:00:00Z',
      last_success_at: null,
      metadata: { model: 'gpt-5.2', mode: 'live' },
    },
    {
      id: 'vogent_voice_agent',
      label: 'Vogent voice agent',
      state: 'awaiting_credentials',
      status_label: 'Awaiting credentials',
      detail: 'Vogent function and webhook secrets must both be configured before live verification.',
      checked_at: '2026-07-20T10:00:00Z',
      last_success_at: null,
      metadata: {},
    },
  ],
};

afterEach(() => vi.unstubAllGlobals());

it('uses the Voice AI Scheduling Platform product name', () => {
  const html = readFileSync('index.html', 'utf-8');
  expect(html).toContain('<title>Voice AI Scheduling Platform</title>');
  expect(html).not.toContain('MedRoute');
  render(<MemoryRouter><AppLayout /></MemoryRouter>);
  expect(screen.getByText('Voice AI Scheduling Platform')).toBeInTheDocument();
  expect(screen.queryByText('Clinical Scheduling')).not.toBeInTheDocument();
});

it('renders backend-derived provider readiness states', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => overview }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><OverviewPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('OpenAI GPT-5.2')).toBeInTheDocument();
  expect(screen.getByText('Not configured')).toBeInTheDocument();
  expect(screen.getByText('Vogent voice agent')).toBeInTheDocument();
  expect(screen.getByText('Awaiting credentials')).toBeInTheDocument();
  expect(screen.queryByText('All systems operational')).not.toBeInTheDocument();
});
