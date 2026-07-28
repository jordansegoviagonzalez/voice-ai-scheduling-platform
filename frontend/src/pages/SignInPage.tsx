import { FormEvent, useEffect, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import {
  Activity,
  ArrowLeft,
  Eye,
  EyeOff,
  Lock,
  LogIn,
  ShieldCheck,
  UserPlus,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { apiRequestAbsolute } from '../api/client';

interface ChatMessage {
  role: string;
  content: string;
  sequenceNumber?: number;
}

interface ChatSessionResponse {
  sessionId: number;
  assistantMessage?: ChatMessage;
}

type EntryView = 'choice' | 'returning' | 'new' | 'admin';

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export function SignInPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [view, setView] = useState<EntryView>(searchParams.get('role') === 'admin' ? 'admin' : 'choice');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [dateOfBirth, setDateOfBirth] = useState('');
  const [phone, setPhone] = useState('');
  const [registrationEmail, setRegistrationEmail] = useState('');
  const [registrationPassword, setRegistrationPassword] = useState('');
  const [confirmRegistrationPassword, setConfirmRegistrationPassword] = useState('');
  const [showRegistrationPassword, setShowRegistrationPassword] = useState(false);
  const [showConfirmRegistrationPassword, setShowConfirmRegistrationPassword] = useState(false);
  const [insuranceProvider, setInsuranceProvider] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(() => signInNotice(location.state));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const errorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setView(searchParams.get('role') === 'admin' ? 'admin' : 'choice');
  }, [searchParams]);

  useEffect(() => {
    setNotice(signInNotice(location.state));
  }, [location.state]);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  if (user) {
    return <Navigate to="/" replace />;
  }

  const beginView = (nextView: EntryView) => {
    setError(null);
    setNotice(null);
    clearPasswordFields();
    setView(nextView);
  };

  const clearPasswordFields = () => {
    setPassword('');
    setRegistrationPassword('');
    setConfirmRegistrationPassword('');
    setShowPassword(false);
    setShowRegistrationPassword(false);
    setShowConfirmRegistrationPassword(false);
  };

  const handleAdminSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const data = await apiRequestAbsolute<{ authenticated: boolean; name: string; email: string; role: string }>(
        '/api/auth/admin/login',
        {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        },
      );
      login(data);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      setError(errorMessage(err, 'Admin sign-in could not be completed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReturningSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const data = await apiRequestAbsolute<ChatSessionResponse>('/api/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({ patientMode: 'returning', email, password }),
      });
      localStorage.setItem('patientChatSessionId', String(data.sessionId));
      navigate('/chat', {
        state: { sessionId: data.sessionId, initialMessages: data.assistantMessage ? [data.assistantMessage] : [] },
      });
    } catch (err: unknown) {
      setError(errorMessage(err, 'Patient sign-in could not be completed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNewPatientSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    const dateValidationError = dateOfBirthValidationError(dateOfBirth);
    if (dateValidationError) {
      setError(dateValidationError);
      return;
    }
    const validationError = registrationPasswordError(registrationPassword, confirmRegistrationPassword);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSubmitting(true);
    try {
      const data = await apiRequestAbsolute<ChatSessionResponse>('/api/chat/sessions', {
        method: 'POST',
        body: JSON.stringify({
          patientMode: 'new',
          firstName,
          lastName,
          dateOfBirth,
          phone,
          email: registrationEmail,
          password: registrationPassword,
          confirmPassword: confirmRegistrationPassword,
          insuranceProvider,
        }),
      });
      clearPasswordFields();
      localStorage.setItem('patientChatSessionId', String(data.sessionId));
      navigate('/chat', {
        state: { sessionId: data.sessionId, initialMessages: data.assistantMessage ? [data.assistantMessage] : [] },
      });
    } catch (err: unknown) {
      setError(errorMessage(err, 'Registration could not be completed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="signin-page">
      <section className="signin-panel" aria-label="Scheduling overview">
        <div>
          <div className="signin-brand">
            <div className="signin-brand-icon">
              <Activity size={24} aria-hidden />
            </div>
            <div>
              <strong>Voice AI Scheduling Platform</strong>
              <span>Orthopedic scheduling</span>
            </div>
          </div>

          <h1>
            The right appointment,
            <span> routed with confidence.</span>
          </h1>
          <p>Physician protocol matching and secure appointment scheduling for patients and care teams.</p>
        </div>

        <div className="signin-security-note">
          <Lock size={14} aria-hidden />
          <span>Synthetic demonstration data only</span>
        </div>
      </section>

      <section className="signin-form-area" aria-label="Account entry">
        <div className="signin-form-card">
          <header className="signin-card-header">
            <p>Secure scheduling entry</p>
            <h2>{titleForView(view)}</h2>
          </header>

          {error && (
            <div ref={errorRef} role="alert" tabIndex={-1} className="signin-error">
              {error}
            </div>
          )}

          {notice && (
            <div role="status" className="signin-notice">
              {notice}
            </div>
          )}

          {view === 'choice' && (
            <div className="patient-entry-actions">
              <button type="button" onClick={() => beginView('new')} className="entry-choice-button">
                <UserPlus size={20} aria-hidden />
                <span>New patient</span>
              </button>
              <button type="button" onClick={() => beginView('returning')} className="entry-choice-button">
                <LogIn size={20} aria-hidden />
                <span>Returning patient</span>
              </button>
              <button type="button" onClick={() => beginView('admin')} className="staff-access-button">
                <ShieldCheck size={16} aria-hidden />
                <span>Clinic staff access</span>
              </button>
            </div>
          )}

          {view === 'returning' && (
            <form onSubmit={handleReturningSubmit} className="signin-form" aria-busy={isSubmitting}>
              <BackButton onClick={() => beginView('choice')} />
              <EmailField value={email} onChange={setEmail} />
              <PasswordField
                label="Password"
                value={password}
                onChange={setPassword}
                showPassword={showPassword}
                onToggle={() => setShowPassword((visible) => !visible)}
                autoComplete="current-password"
              />
              <button type="submit" disabled={isSubmitting} className="primary-submit-button">
                {isSubmitting ? 'Verifying...' : 'Continue to scheduling chat'}
              </button>
            </form>
          )}

          {view === 'new' && (
            <form onSubmit={handleNewPatientSubmit} className="signin-form" aria-busy={isSubmitting}>
              <BackButton onClick={() => beginView('choice')} />
              <p className="signin-helper">Use this email and password to return to your scheduling account later.</p>
              <div className="field-grid">
                <TextField label="First name" value={firstName} onChange={setFirstName} autoComplete="given-name" />
                <TextField label="Last name" value={lastName} onChange={setLastName} autoComplete="family-name" />
              </div>
              <TextField
                label="Date of birth"
                value={dateOfBirth}
                onChange={setDateOfBirth}
                type="date"
                autoComplete="bday"
                max={todayDateValue()}
              />
              {dateOfBirthValidationError(dateOfBirth) && (
                <p className="signin-field-error" role="alert">{dateOfBirthValidationError(dateOfBirth)}</p>
              )}
              <TextField label="Contact number" value={phone} onChange={setPhone} type="tel" autoComplete="tel" />
              <TextField
                label="Email"
                value={registrationEmail}
                onChange={setRegistrationEmail}
                type="email"
                autoComplete="email"
              />
              <TextField
                label="Insurance provider"
                value={insuranceProvider}
                onChange={setInsuranceProvider}
                autoComplete="organization"
              />
              <PasswordField
                label="Password"
                value={registrationPassword}
                onChange={setRegistrationPassword}
                showPassword={showRegistrationPassword}
                onToggle={() => setShowRegistrationPassword((visible) => !visible)}
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
              />
              <PasswordField
                label="Confirm password"
                value={confirmRegistrationPassword}
                onChange={setConfirmRegistrationPassword}
                showPassword={showConfirmRegistrationPassword}
                onToggle={() => setShowConfirmRegistrationPassword((visible) => !visible)}
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
              />
              {registrationPassword && confirmRegistrationPassword && registrationPassword !== confirmRegistrationPassword && (
                <p className="signin-field-error" role="alert">Passwords do not match.</p>
              )}
              <button
                type="submit"
                disabled={
                  isSubmitting ||
                  Boolean(dateOfBirthValidationError(dateOfBirth)) ||
                  Boolean(registrationPasswordError(registrationPassword, confirmRegistrationPassword))
                }
                className="primary-submit-button"
              >
                {isSubmitting ? 'Registering...' : 'Continue to scheduling chat'}
              </button>
            </form>
          )}

          {view === 'admin' && (
            <form onSubmit={handleAdminSubmit} className="signin-form" aria-busy={isSubmitting}>
              <BackButton onClick={() => beginView('choice')} />
              <EmailField value={email} onChange={setEmail} />
              <PasswordField
                label="Password"
                value={password}
                onChange={setPassword}
                showPassword={showPassword}
                onToggle={() => setShowPassword((visible) => !visible)}
                autoComplete="current-password"
              />
              <button type="submit" disabled={isSubmitting} className="primary-submit-button">
                {isSubmitting ? 'Signing in...' : 'Sign in to operations console'}
              </button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}

function titleForView(view: EntryView) {
  if (view === 'returning') return 'Returning patient';
  if (view === 'new') return 'New patient registration';
  if (view === 'admin') return 'Clinic staff access';
  return 'Start scheduling';
}

function signInNotice(state: unknown) {
  if (typeof state !== 'object' || state === null || !('notice' in state)) return null;
  const notice = (state as { notice?: unknown }).notice;
  return typeof notice === 'string' && notice.trim() ? notice : null;
}

function BackButton({ onClick }: { onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} className="back-button">
      <ArrowLeft size={16} aria-hidden />
      <span>Back</span>
    </button>
  );
}

function EmailField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <TextField label="Email address" value={value} onChange={onChange} type="email" autoComplete="email" />;
}

function PasswordField({
  label,
  value,
  onChange,
  showPassword,
  onToggle,
  autoComplete,
  minLength,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  showPassword: boolean;
  onToggle: () => void;
  autoComplete: string;
  minLength?: number;
  maxLength?: number;
}) {
  const id = label.toLowerCase().replaceAll(' ', '-');
  return (
    <label className="signin-field" htmlFor={id}>
      <span>{label}</span>
      <div className="password-input-wrap">
        <input
          id={id}
          type={showPassword ? 'text' : 'password'}
          required
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          minLength={minLength}
          maxLength={maxLength}
        />
        <button type="button" onClick={onToggle} aria-label={showPassword ? 'Hide password' : 'Show password'}>
          {showPassword ? <EyeOff size={18} aria-hidden /> : <Eye size={18} aria-hidden />}
        </button>
      </div>
    </label>
  );
}

function registrationPasswordError(passwordValue: string, confirmationValue: string) {
  if (!passwordValue || !confirmationValue) return 'Password and confirm password are required.';
  if (!passwordValue.trim()) return 'Password is required.';
  if (passwordValue.length < 12) return 'Use at least 12 characters.';
  if (passwordValue.length > 128) return 'Use no more than 128 characters.';
  if (passwordValue !== confirmationValue) return 'Passwords do not match.';
  return null;
}

function dateOfBirthValidationError(value: string) {
  if (!value) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return 'Enter a valid date of birth.';
  if (value > todayDateValue()) return 'Date of birth cannot be in the future.';
  return null;
}

function todayDateValue() {
  return new Date().toISOString().slice(0, 10);
}

function TextField({
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  max,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  autoComplete?: string;
  max?: string;
}) {
  const id = label.toLowerCase().replaceAll(' ', '-');
  return (
    <label className="signin-field" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        type={type}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        max={max}
      />
    </label>
  );
}
