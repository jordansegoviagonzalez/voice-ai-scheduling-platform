import { apiRequest } from './client';
import type {
  Appointment,
  BookingConfirmation,
  Call,
  Doctor,
  DoctorInput,
  Location,
  LocationInput,
  Organization,
  OrganizationInput,
  OverviewResponse,
  ProtocolResponse,
  RoutingDecision,
  RoutingResponse,
} from '../types/api';

export const schedulingApi = {
  overview: () => apiRequest<OverviewResponse>('/dashboard/overview'),
  organizations: () => apiRequest<{ organizations: Organization[] }>('/organizations'),
  organization: (id: string | number) => apiRequest<{ organization: Organization }>(`/organizations/${id}`),
  createOrganization: (body: OrganizationInput) =>
    apiRequest<{ organization: Organization }>('/organizations', { method: 'POST', body: JSON.stringify(body) }),
  updateOrganization: (id: string | number, body: Partial<OrganizationInput>) =>
    apiRequest<{ organization: Organization }>(`/organizations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  resolveOrganizationBySlug: (slug: string) =>
    apiRequest<{ organization: Organization }>(`/organizations/slug/${encodeURIComponent(slug)}`),
  organizationDoctors: (organizationId: string | number) =>
    apiRequest<{ doctors: Doctor[] }>(`/organizations/${organizationId}/doctors`),
  organizationDoctor: (organizationId: string | number, doctorId: string | number) =>
    apiRequest<{ doctor: Doctor }>(`/organizations/${organizationId}/doctors/${doctorId}`),
  createOrganizationDoctor: (organizationId: string | number, body: DoctorInput) =>
    apiRequest<{ doctor: Doctor }>(`/organizations/${organizationId}/doctors`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateOrganizationDoctor: (organizationId: string | number, doctorId: string | number, body: Partial<DoctorInput>) =>
    apiRequest<{ doctor: Doctor }>(`/organizations/${organizationId}/doctors/${doctorId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  organizationLocations: (organizationId: string | number) =>
    apiRequest<{ locations: Location[] }>(`/organizations/${organizationId}/locations`),
  createOrganizationLocation: (organizationId: string | number, body: LocationInput) =>
    apiRequest<{ location: Location }>(`/organizations/${organizationId}/locations`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  updateOrganizationLocation: (organizationId: string | number, locationId: string | number, body: Partial<LocationInput>) =>
    apiRequest<{ location: Location }>(`/organizations/${organizationId}/locations/${locationId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
  calls: (query = '') => apiRequest<{ calls: Call[] }>(`/calls${query}`),
  call: (id: string | number) => apiRequest<{ call: Call }>(`/calls/${id}`),
  appointments: () => apiRequest<{ appointments: Appointment[] }>('/appointments'),
  doctors: () => apiRequest<{ doctors: Doctor[] }>('/doctors'),
  protocol: () => apiRequest<ProtocolResponse>('/protocol'),
  routingAudit: () => apiRequest<{ decisions: RoutingDecision[] }>('/routing-audit'),
  simulatorPreview: (body: Record<string, unknown>) =>
    apiRequest<{ patient: { id: number }; call: Call; routing: RoutingResponse }>(
      '/simulator/preview',
      { method: 'POST', body: JSON.stringify(body) },
    ),
  bookingConfirmation: (body: Record<string, unknown>) =>
    apiRequest<{ confirmation: BookingConfirmation }>('/booking-confirmations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  simulatorBook: (body: Record<string, unknown>) =>
    apiRequest<{ appointment: Appointment }>('/simulator/book', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};
