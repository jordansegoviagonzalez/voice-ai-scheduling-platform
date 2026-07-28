import { useEffect, useState } from 'react';
import { apiRequest } from '../api/client';
import { PageHeader } from '../components/PageHeader';

interface PatientRow {
  id: number;
  full_name: string;
  date_of_birth: string;
  phone: string;
  email?: string | null;
  insurance_provider?: string | null;
  latest_chat_status?: string | null;
  latest_appointment?: {
    id: number;
    doctor: { full_name: string };
    location: { name: string };
    slot: { starts_at: string };
  } | null;
}

export function PatientsPage() {
  const [patients, setPatients] = useState<PatientRow[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<{ patients: PatientRow[] }>('/dashboard/patients')
      .then((data) => setPatients(data.patients || []))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load patients.'));
  }, []);

  return (
    <div>
      <PageHeader title="Patients" subtitle="View registered synthetic patients." />
      {error && <div role="alert" style={{ margin: '1rem', padding: '0.75rem', border: '1px solid #f59e0b', borderRadius: '8px' }}>{error}</div>}
      <div style={{ padding: '1rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: 'white' }}>
          <thead>
            <tr>
              <th style={headerCell}>Name</th>
              <th style={headerCell}>DOB</th>
              <th style={headerCell}>Phone</th>
              <th style={headerCell}>Email</th>
              <th style={headerCell}>Insurance</th>
              <th style={headerCell}>Latest appointment</th>
              <th style={headerCell}>Latest chat</th>
            </tr>
          </thead>
          <tbody>
            {patients.length === 0 ? (
              <tr><td colSpan={7} style={bodyCell}>No patients found.</td></tr>
            ) : patients.map((patient) => (
              <tr key={patient.id}>
                <td style={bodyCell}>{patient.full_name}</td>
                <td style={bodyCell}>{patient.date_of_birth}</td>
                <td style={bodyCell}>{patient.phone}</td>
                <td style={bodyCell}>{patient.email || '-'}</td>
                <td style={bodyCell}>{patient.insurance_provider || '-'}</td>
                <td style={bodyCell}>
                  {patient.latest_appointment
                    ? `${patient.latest_appointment.doctor.full_name}, ${new Date(patient.latest_appointment.slot.starts_at).toLocaleString()}`
                    : '-'}
                </td>
                <td style={bodyCell}>{patient.latest_chat_status || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const headerCell = { textAlign: 'left' as const, borderBottom: '1px solid #cbd5e1', padding: '0.75rem' };
const bodyCell = { padding: '0.75rem', borderBottom: '1px solid #e2e8f0' };
