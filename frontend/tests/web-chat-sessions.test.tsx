import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { expect, test, vi } from 'vitest';
import { WebChatSessionsPage } from '../src/pages/WebChatSessionsPage';
import { apiRequest } from '../src/api/client';

vi.mock('../src/api/client', () => ({
  apiRequest: vi.fn(),
}));

test('displays symptom duration if captured', async () => {
  vi.mocked(apiRequest).mockImplementation((url: string) => {
    if (url === '/dashboard/chat-sessions') {
      return Promise.resolve({ chat_sessions: [] });
    }
    return Promise.resolve({
      chat_session: {
        id: 52,
        created_at: '2026-08-01T10:00:00Z',
        status: 'COMPLETED',
        patient: { full_name: 'Sophia Martinez' },
        collected_data: { symptom_duration: 'Three days' },
        messages: [],
        events: [],
      }
    });
  });

  render(
    <MemoryRouter initialEntries={['/web-chat-sessions/52']}>
      <Routes>
        <Route path="/web-chat-sessions/:sessionId" element={<WebChatSessionsPage />} />
      </Routes>
    </MemoryRouter>
  );

  await waitFor(() => {
    expect(screen.getByText('Three days')).toBeInTheDocument();
  });
});

test('displays "Not captured" if symptom duration is missing', async () => {
  vi.mocked(apiRequest).mockImplementation((url: string) => {
    if (url === '/dashboard/chat-sessions') {
      return Promise.resolve({ chat_sessions: [] });
    }
    return Promise.resolve({
      chat_session: {
        id: 53,
        created_at: '2026-08-01T10:00:00Z',
        status: 'COMPLETED',
        patient: { full_name: 'Sophia Martinez' },
        collected_data: {},
        messages: [],
        events: [],
      }
    });
  });

  render(
    <MemoryRouter initialEntries={['/web-chat-sessions/53']}>
      <Routes>
        <Route path="/web-chat-sessions/:sessionId" element={<WebChatSessionsPage />} />
      </Routes>
    </MemoryRouter>
  );

  await waitFor(() => {
    expect(screen.getByText('Not captured')).toBeInTheDocument();
  });
});
