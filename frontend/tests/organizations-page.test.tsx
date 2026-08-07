import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthProvider } from '../src/context/AuthContext';
import { AppLayout } from '../src/layouts/AppLayout';
import { OrganizationsPage } from '../src/pages/OrganizationsPage';
import type { Doctor, Organization } from '../src/types/api';

const defaultOrganization: Organization = {
  id: 1,
  slug: 'default-orthopedics',
  name: 'Default Orthopedics',
  organization_type: 'Orthopedics',
  doctor_count: 1,
  status: 'ACTIVE',
  timezone: 'America/Los_Angeles',
  active: true,
  created_at: '2026-08-06T10:00:00Z',
  updated_at: '2026-08-06T10:00:00Z',
};

const northsideOrganization: Organization = {
  id: 2,
  slug: 'northside-dental-care',
  name: 'Northside Dental Care',
  organization_type: 'Dental',
  doctor_count: 1,
  status: 'ACTIVE',
  timezone: 'America/Los_Angeles',
  active: true,
  created_at: '2026-08-06T10:00:00Z',
  updated_at: '2026-08-06T10:00:00Z',
};

const defaultDoctor: Doctor = {
  id: 10,
  organization_id: 1,
  first_name: 'Iris',
  last_name: 'Stone',
  full_name: 'Dr. Iris Stone',
  primary_specialty: 'Knee Orthopedics',
  is_general_orthopedics: false,
  accepts_new_patients: true,
  active: true,
  locations: [{ id: 100, organization_id: 1, code: 'MAIN', name: 'Main Campus' }],
  capabilities: [{ body_part: 'Knee', issue_type: 'General' }],
};

const northsideDoctor: Doctor = {
  id: 20,
  organization_id: 2,
  first_name: 'Noah',
  last_name: 'Pierce',
  full_name: 'Dr. Noah Pierce',
  primary_specialty: 'Dental',
  is_general_orthopedics: false,
  accepts_new_patients: true,
  active: true,
  locations: [{ id: 200, organization_id: 2, code: 'DENTAL', name: 'Northside Office' }],
  capabilities: [{ body_part: 'Jaw', issue_type: 'General' }],
};

afterEach(() => vi.unstubAllGlobals());

it('places Organizations directly under Overview in the admin navigation', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({
    authenticated: true,
    name: 'Dr. Admin',
    email: 'admin@example.test',
    role: 'admin_provider',
  })));

  render(
    <AuthProvider>
      <MemoryRouter>
        <AppLayout />
      </MemoryRouter>
    </AuthProvider>,
  );

  const navLinks = await screen.findAllByRole('link');
  expect(navLinks.map((link) => link.textContent).slice(0, 2)).toEqual(['Overview', 'Organizations']);
  expect(screen.getByRole('link', { name: /organizations/i })).toHaveAttribute('href', '/organizations');
});

it('renders the organizations route from backend API data', async () => {
  const fetchMock = createApiFetchMock({
    organizations: [{
      ...defaultOrganization,
      id: 7,
      slug: 'api-only-clinic',
      name: 'API Only Clinic',
      organization_type: 'Primary Care',
      doctor_count: 0,
    }],
    doctorsByOrganizationId: { 7: [] },
  });
  vi.stubGlobal('fetch', fetchMock);

  renderOrganizationsRoute();

  expect(await screen.findByRole('heading', { name: 'Organizations' })).toBeInTheDocument();
  expect((await screen.findAllByText('API Only Clinic')).length).toBeGreaterThan(0);
  expect(screen.queryByText('Northside Dental Care')).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith('/api/v1/organizations', expect.any(Object));
});

it('connects create and update organization and doctor flows to scoped API paths', async () => {
  const fetchMock = createApiFetchMock();
  vi.stubGlobal('fetch', fetchMock);
  renderOrganizationsRoute();

  expect((await screen.findAllByText('Default Orthopedics')).length).toBeGreaterThan(0);
  expect(await screen.findByText('Dr. Iris Stone')).toBeInTheDocument();
  expect(screen.queryByRole('tab', { name: 'Chat & Voice' })).not.toBeInTheDocument();
  expect(screen.queryByText('Chat & Voice at a glance')).not.toBeInTheDocument();
  expect(screen.queryByText('Chat link placeholders')).not.toBeInTheDocument();
  expect(screen.queryByText('Voice context placeholders')).not.toBeInTheDocument();
  expect(screen.queryByText('Pending generation')).not.toBeInTheDocument();
  expect(screen.queryByText('Pending mapping')).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: 'Edit organization' }));
  await userEvent.clear(screen.getByLabelText('Organization name'));
  await userEvent.type(screen.getByLabelText('Organization name'), 'Default Orthopedics Group');
  await userEvent.click(screen.getByRole('button', { name: 'Save organization' }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/organizations/1',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('Default Orthopedics Group'),
      }),
    );
  });

  await userEvent.click(screen.getByRole('tab', { name: 'Doctors' }));
  await userEvent.click(screen.getByRole('button', { name: 'Add doctor' }));
  await userEvent.type(screen.getByLabelText('Doctor first name'), 'Mara');
  await userEvent.type(screen.getByLabelText('Doctor last name'), 'Hayes');
  await userEvent.selectOptions(screen.getByLabelText('Capability area'), 'Heart/Circulation');
  await userEvent.selectOptions(screen.getByLabelText('Visit reason / issue type'), 'Routine Consult');
  expect(screen.getByRole('option', { name: 'Knee' })).toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Create doctor' }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/organizations/1/doctors',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"first_name":"Mara"'),
      }),
    );
  });
  const createDoctorCall = fetchMock.mock.calls.find(([path, init]) => {
    return path === '/api/v1/organizations/1/doctors' && init?.method === 'POST';
  });
  expect(requestBody(createDoctorCall?.[1])).toEqual(
    expect.objectContaining({
      capabilities: [{ body_part: 'Heart/Circulation', issue_type: 'Routine Consult' }],
    }),
  );

  const irisRow = screen.getByText('Dr. Iris Stone').closest('tr');
  expect(irisRow).not.toBeNull();
  await userEvent.click(within(irisRow as HTMLTableRowElement).getByRole('button', { name: 'Edit' }));
  await userEvent.clear(screen.getByLabelText('Doctor last name'));
  await userEvent.type(screen.getByLabelText('Doctor last name'), 'Gray');
  await userEvent.click(screen.getByRole('button', { name: 'Save doctor' }));

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/organizations/1/doctors/10',
      expect.objectContaining({
        method: 'PATCH',
        body: expect.stringContaining('"last_name":"Gray"'),
      }),
    );
  });

  await userEvent.click(screen.getByRole('button', { name: 'New organization' }));
  await userEvent.type(screen.getByLabelText('New organization name'), 'Harbor Pediatrics');
  expect(screen.queryByLabelText('New organization slug')).not.toBeInTheDocument();
  expect(screen.queryByText('Organization link name preview')).not.toBeInTheDocument();
  expect(screen.queryByText('Generated after name is entered')).not.toBeInTheDocument();
  await userEvent.click(screen.getAllByRole('button', { name: 'Create organization' })[0]);

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/organizations',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"name":"Harbor Pediatrics"'),
      }),
    );
  });
  const createOrganizationCall = fetchMock.mock.calls.find(([path, init]) => {
    return path === '/api/v1/organizations' && init?.method === 'POST';
  });
  expect(createOrganizationCall).toBeDefined();
  expect(requestBody(createOrganizationCall?.[1])).not.toHaveProperty('slug');
});

it('keeps doctor rows scoped to the selected organization', async () => {
  const leakedDoctor = { ...northsideDoctor, id: 99, full_name: 'Dr. Leaked Doctor' };
  vi.stubGlobal('fetch', createApiFetchMock({
    doctorsByOrganizationId: {
      1: [defaultDoctor, leakedDoctor],
      2: [northsideDoctor],
    },
  }));
  renderOrganizationsRoute();

  expect(await screen.findByText('Dr. Iris Stone')).toBeInTheDocument();
  expect(screen.queryByText('Dr. Leaked Doctor')).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('button', { name: /Northside Dental Care/i }));

  expect(await screen.findByText('Dr. Noah Pierce')).toBeInTheDocument();
  expect(screen.queryByText('Dr. Iris Stone')).not.toBeInTheDocument();
});

it('shows loading, empty, and API error states', async () => {
  vi.stubGlobal('fetch', vi.fn(() => new Promise(() => undefined)));
  const { unmount } = renderOrganizationsRoute();
  expect(screen.getByText(/Loading organizations/)).toBeInTheDocument();
  unmount();

  vi.stubGlobal('fetch', createApiFetchMock({ organizations: [], doctorsByOrganizationId: {} }));
  const emptyRender = renderOrganizationsRoute();
  expect(await screen.findByText('No organizations')).toBeInTheDocument();
  emptyRender.unmount();

  vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ error: { message: 'Organization API unavailable' } }, 500)));
  renderOrganizationsRoute();
  expect(await screen.findByText('Organization API unavailable')).toBeInTheDocument();
});

function renderOrganizationsRoute() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/organizations']}>
        <Routes>
          <Route path="/organizations" element={<OrganizationsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function createApiFetchMock({
  organizations = [defaultOrganization, northsideOrganization],
  doctorsByOrganizationId = {
    1: [defaultDoctor],
    2: [northsideDoctor],
  },
}: {
  organizations?: Organization[];
  doctorsByOrganizationId?: Record<number, Doctor[]>;
} = {}) {
  let organizationState = [...organizations];
  const doctorState = new Map<number, Doctor[]>(
    Object.entries(doctorsByOrganizationId).map(([organizationId, doctors]) => [Number(organizationId), [...doctors]]),
  );

  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? 'GET';

    if (path === '/api/v1/organizations' && method === 'GET') {
      return jsonResponse({ organizations: organizationState });
    }

    if (path === '/api/v1/organizations' && method === 'POST') {
      const body = requestBody(init);
      const created = {
        id: 30,
        slug: String(body.slug ?? previewSlug(String(body.name))),
        name: String(body.name),
        organization_type: 'Pediatrics',
        doctor_count: 0,
        status: 'ACTIVE',
        timezone: String(body.timezone ?? 'America/Los_Angeles'),
        active: true,
      } satisfies Organization;
      organizationState = [...organizationState, created];
      doctorState.set(created.id, []);
      return jsonResponse({ organization: created }, 201);
    }

    const organizationMatch = path.match(/^\/api\/v1\/organizations\/(\d+)$/);
    if (organizationMatch && method === 'PATCH') {
      const organizationId = Number(organizationMatch[1]);
      const body = requestBody(init);
      const updated = {
        ...organizationState.find((organization) => organization.id === organizationId),
        ...body,
      } as Organization;
      organizationState = organizationState.map((organization) => (organization.id === organizationId ? updated : organization));
      return jsonResponse({ organization: updated });
    }

    const doctorListMatch = path.match(/^\/api\/v1\/organizations\/(\d+)\/doctors$/);
    if (doctorListMatch && method === 'GET') {
      return jsonResponse({ doctors: doctorState.get(Number(doctorListMatch[1])) ?? [] });
    }

    if (doctorListMatch && method === 'POST') {
      const organizationId = Number(doctorListMatch[1]);
      const body = requestBody(init);
      const created = {
        id: 31,
        organization_id: organizationId,
        first_name: String(body.first_name),
        last_name: String(body.last_name),
        full_name: `Dr. ${body.first_name} ${body.last_name}`,
        primary_specialty: 'General',
        is_general_orthopedics: false,
        accepts_new_patients: Boolean(body.accepts_new_patients),
        active: Boolean(body.active),
        locations: [],
        capabilities: [],
      } satisfies Doctor;
      doctorState.set(organizationId, [...(doctorState.get(organizationId) ?? []), created]);
      return jsonResponse({ doctor: created }, 201);
    }

    const doctorMatch = path.match(/^\/api\/v1\/organizations\/(\d+)\/doctors\/(\d+)$/);
    if (doctorMatch && method === 'PATCH') {
      const organizationId = Number(doctorMatch[1]);
      const doctorId = Number(doctorMatch[2]);
      const body = requestBody(init);
      const updatedDoctors = (doctorState.get(organizationId) ?? []).map((doctor) => {
        if (doctor.id !== doctorId) return doctor;
        const nextDoctor = { ...doctor, ...body } as Doctor;
        nextDoctor.full_name = `Dr. ${nextDoctor.first_name} ${nextDoctor.last_name}`;
        return nextDoctor;
      });
      doctorState.set(organizationId, updatedDoctors);
      return jsonResponse({ doctor: updatedDoctors.find((doctor) => doctor.id === doctorId) });
    }

    return jsonResponse({ error: { message: `Unhandled ${method} ${path}` } }, 500);
  });
}

function requestBody(init?: RequestInit): Record<string, unknown> {
  return JSON.parse(typeof init?.body === 'string' ? init.body : '{}') as Record<string, unknown>;
}

function previewSlug(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 80)
    .replace(/-$/g, '');
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}
