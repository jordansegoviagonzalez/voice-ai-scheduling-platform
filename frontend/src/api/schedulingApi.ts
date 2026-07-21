import { apiRequest } from './client';
import type {
  Appointment,
  BookingConfirmation,
  Call,
  Doctor,
  OverviewResponse,
  ProtocolResponse,
  RoutingDecision,
  RoutingResponse,
} from '../types/api';

export const schedulingApi = {
  overview: () => apiRequest<OverviewResponse>('/dashboard/overview'),
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
