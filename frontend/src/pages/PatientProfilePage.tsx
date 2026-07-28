import { FormEvent, useEffect, useState } from 'react';
import { ArrowLeft, Loader2, Save } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { ApiClientError } from '../api/client';
import { getPatientProfile, logoutPatient, updatePatientProfile, type PatientProfile } from '../api/patientApi';
import { PatientAccountMenu } from '../components/PatientAccountMenu';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export function PatientProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    getPatientProfile()
      .then((data) => {
        setProfile(data.patient);
        setEmail(data.patient.email || '');
        setPhone(data.patient.phone);
      })
      .catch((err) => {
        if (handleUnauthorized(err, navigate, clearPatientStorage)) return;
        setMessage(err instanceof Error ? err.message : 'Profile could not be loaded.');
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  const signOut = async () => {
    try {
      await logoutPatient();
    } catch {
      // Local protected state is cleared regardless of logout response availability.
    }
    clearPatientStorage();
    setProfile(null);
    navigate('/sign-in?role=patient', { replace: true });
  };

  const saveProfile = async (event: FormEvent) => {
    event.preventDefault();
    setSaveState('saving');
    setMessage(null);
    try {
      const data = await updatePatientProfile({ email, phone });
      setProfile(data.patient);
      setEmail(data.patient.email || '');
      setPhone(data.patient.phone);
      setSaveState('saved');
      setMessage('Saved');
    } catch (err) {
      if (handleUnauthorized(err, navigate, clearPatientStorage)) return;
      setSaveState('error');
      setMessage(err instanceof Error ? err.message : 'Profile changes could not be saved.');
    }
  };

  if (loading) {
    return (
      <main className="patient-chat-page">
        <section className="patient-profile-shell">
          <div className="chat-loading" role="status" aria-live="polite">
            Restoring your patient profile...
          </div>
        </section>
      </main>
    );
  }

  if (!profile) {
    return (
      <main className="patient-chat-page">
        <section className="patient-profile-shell">
          <div role="alert" className="chat-alert">
            {message || 'Profile could not be loaded.'}
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="patient-chat-page">
      <section className="patient-profile-shell">
        <header className="patient-profile-header">
          <button type="button" className="back-button" onClick={() => navigate('/chat')}>
            <ArrowLeft size={16} aria-hidden />
            <span>Back to scheduling</span>
          </button>
          <PatientAccountMenu profile={profile} onProfile={() => undefined} onSignOut={signOut} />
        </header>

        <section className="patient-profile-card" aria-labelledby="patient-profile-heading">
          <div className="patient-profile-title">
            <div className="patient-profile-initials" aria-hidden>
              {profile.firstName.slice(0, 1)}
              {profile.lastName.slice(0, 1)}
            </div>
            <div>
              <p>Patient profile</p>
              <h1 id="patient-profile-heading">{profile.fullName}</h1>
            </div>
          </div>

          {message && (
            <div role={saveState === 'error' ? 'alert' : 'status'} className={`profile-message profile-message-${saveState}`}>
              {message}
            </div>
          )}

          <dl className="patient-profile-details">
            <ProfileDetail label="First name" value={profile.firstName} />
            <ProfileDetail label="Last name" value={profile.lastName} />
            <ProfileDetail label="Date of birth" value={formatPlainDate(profile.dateOfBirth)} />
            <ProfileDetail label="Insurance provider" value={profile.insuranceProvider || 'Not provided'} />
            <ProfileDetail label="Account created" value={formatDateTime(profile.accountCreatedAt)} />
          </dl>

          <form className="patient-profile-form" onSubmit={saveProfile} aria-busy={saveState === 'saving'}>
            <label>
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                required
              />
            </label>
            <label>
              <span>Phone number</span>
              <input
                type="tel"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                autoComplete="tel"
                required
              />
            </label>
            <button type="submit" disabled={saveState === 'saving'}>
              {saveState === 'saving' ? <Loader2 size={16} className="spin" aria-hidden /> : <Save size={16} aria-hidden />}
              <span>{saveState === 'saving' ? 'Saving' : saveState === 'saved' ? 'Saved' : 'Save changes'}</span>
            </button>
          </form>
        </section>
      </section>
    </main>
  );
}

function ProfileDetail({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function handleUnauthorized(error: unknown, navigate: ReturnType<typeof useNavigate>, clearState: () => void) {
  if (!(error instanceof ApiClientError) || error.status !== 401) return false;
  clearState();
  navigate('/sign-in?role=patient', {
    replace: true,
    state: { notice: error.code === 'SESSION_EXPIRED' ? 'Your session expired because of inactivity.' : undefined },
  });
  return true;
}

function clearPatientStorage() {
  localStorage.removeItem('patientChatSessionId');
}

function formatPlainDate(value: string) {
  return new Date(`${value}T00:00:00Z`).toLocaleDateString([], { dateStyle: 'medium', timeZone: 'UTC' });
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' });
}
