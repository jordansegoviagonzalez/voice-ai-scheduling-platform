import { apiRequestAbsolute } from './client';

export interface PatientProfile {
  firstName: string;
  lastName: string;
  fullName: string;
  dateOfBirth: string;
  email: string | null;
  phone: string;
  insuranceProvider: string | null;
  accountCreatedAt: string;
}

export async function getPatientProfile() {
  return apiRequestAbsolute<{ patient: PatientProfile }>('/api/patient/profile');
}

export async function updatePatientProfile(payload: { email: string; phone: string }) {
  return apiRequestAbsolute<{ patient: PatientProfile }>('/api/patient/profile', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function logoutPatient() {
  return apiRequestAbsolute<{ success: boolean }>('/api/patient/logout', { method: 'POST' });
}
