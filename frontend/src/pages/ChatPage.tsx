import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom';
import {
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  Clock,
  Loader2,
  MapPin,
  Send,
  Stethoscope,
  UserRound,
} from 'lucide-react';
import { ApiClientError, apiRequestAbsolute } from '../api/client';
import { getPatientProfile, logoutPatient, type PatientProfile } from '../api/patientApi';
import { PatientAccountMenu } from '../components/PatientAccountMenu';

interface ChatMessage {
  role: string;
  content: string;
  sequenceNumber?: number;
}

interface Slot {
  id: number;
  starts_at: string;
  ends_at: string;
  display_date?: string;
  display_time?: string;
  display_datetime?: string;
  display_end_time?: string;
  time_zone?: string;
  location: { id: number; code: string; name: string };
}

interface RecommendationLocation {
  clinic_location: string;
  clinic_location_code: string;
  is_preferred: boolean;
  labels: string[];
  available_slots: Slot[];
}

interface Recommendation {
  physician_id: number;
  physician_name: string;
  initials: string;
  specialty: string;
  is_general_orthopedics?: boolean;
  primary_specialty?: string;
  match_explanation: string;
  labels: string[];
  locations: RecommendationLocation[];
  available_slots?: Slot[]; // Legacy support
}

interface Booking {
  id: number;
  doctor: { full_name: string };
  location: { name: string };
  slot: { starts_at: string; ends_at: string; display_datetime?: string; display_time?: string; display_end_time?: string };
  issue_type: string;
  body_part: string;
  patient: { full_name: string; phone: string; email?: string | null };
}

interface ChatSessionResponse {
  sessionId: number;
  status: string;
  currentStep: string;
  messages: ChatMessage[];
  collectedData: Record<string, unknown>;
  routingResult: Record<string, unknown>;
  recommendations: Recommendation[];
  availableSlots: Slot[];
  assistantMessage?: ChatMessage;
  booking?: Booking;
  escalation?: { type: string; reason: string; triggerMessageId?: number } | null;
}

interface ChatRouteState {
  sessionId?: number;
  initialMessages?: ChatMessage[];
}

type ProgressState = 'Completed' | 'Current' | 'Upcoming';

interface ProgressStep {
  label: string;
  state: ProgressState;
}

const sessionKey = 'patientChatSessionId';
const terminalStatuses = new Set(['confirmed', 'escalated', 'care_team_handoff', 'abandoned']);
const workflowSteps = [
  'Patient verified',
  'Reason for visit',
  'Symptoms and severity',
  'Appointment type',
  'Scheduling preferences',
  'Physician recommendation',
  'Appointment confirmation',
];

export function ChatPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const { orgSlug } = useParams<{ orgSlug?: string }>();
  const routeState = location.state as ChatRouteState | null;
  const routeSessionId = routeState?.sessionId;
  const storedSessionId = Number(localStorage.getItem(sessionKey));
  const [sessionId] = useState<number | null>(routeSessionId || (storedSessionId > 0 ? storedSessionId : null));
  const [messages, setMessages] = useState<ChatMessage[]>(routeState?.initialMessages || []);
  const [input, setInput] = useState('');
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [selectedSlot, setSelectedSlot] = useState<Slot | null>(null);
  const [selectedRecommendation, setSelectedRecommendation] = useState<Recommendation | null>(null);
  const [booking, setBooking] = useState<Booking | null>(null);
  const [collectedData, setCollectedData] = useState<Record<string, unknown>>({});
  const [status, setStatus] = useState('');
  const [currentStep, setCurrentStep] = useState('');
  const [escalation, setEscalation] = useState<ChatSessionResponse['escalation']>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(sessionId));
  const [submitting, setSubmitting] = useState(false);
  const [progressOpen, setProgressOpen] = useState(false);
  const [profile, setProfile] = useState<PatientProfile | null>(null);
  const [bookingAnnouncement, setBookingAnnouncement] = useState('');
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const progressRef = useRef<HTMLDivElement | null>(null);
  const progressTriggerRef = useRef<HTMLButtonElement | null>(null);

  const [orgPrecheck, setOrgPrecheck] = useState(Boolean(orgSlug && !sessionId));

  const applySession = useCallback((data: ChatSessionResponse) => {
    // Normalize recommendations to canonical shape: locations[].available_slots[]
    const normalizedRecommendations = (data.recommendations || []).map(rec => {
      const locations = Array.isArray(rec.locations) ? [...rec.locations] : [];

      if (Array.isArray(rec.available_slots) && rec.available_slots.length > 0) {
        const slotsByLoc = new Map<number, Slot[]>();
        rec.available_slots.forEach(slot => {
          if (!slot || !slot.location) return;
          const locId = slot.location.id;
          if (!slotsByLoc.has(locId)) slotsByLoc.set(locId, []);
          slotsByLoc.get(locId)!.push(slot);
        });
        const legacyLocations = Array.from(slotsByLoc.values()).map(slots => {
          const firstSlot = slots[0];
          return {
            clinic_location: firstSlot.location.name,
            clinic_location_code: firstSlot.location.code,
            is_preferred: false,
            labels: [],
            available_slots: slots
          };
        });
        locations.push(...legacyLocations);
      }

      const normalizedLocations = locations.map(loc => ({
        ...loc,
        available_slots: Array.isArray(loc.available_slots) ? loc.available_slots : [],
        labels: Array.isArray(loc.labels) ? loc.labels : []
      }));

      return {
        ...rec,
        locations: normalizedLocations,
        labels: Array.isArray(rec.labels) ? rec.labels : []
      };
    });

    setStatus(data.status);
    setCurrentStep(data.currentStep);
    setMessages(data.messages || []);
    setRecommendations(normalizedRecommendations);
    setCollectedData(data.collectedData || {});
    setEscalation(data.escalation || null);
    setBooking(data.booking || null);
    setError(data.escalation?.reason || null);

    const routing = data.routingResult || {};
    const selectedSlotId = routing.selected_slot_id as number | undefined;
    if (selectedSlotId) {
      const allSlots = data.availableSlots || [];
      const matchedSlot = allSlots.find(s => s.id === selectedSlotId);
      if (matchedSlot) {
        setSelectedSlot(matchedSlot);
      }
    }
    if (routing.selected_recommendation) {
      setSelectedRecommendation(routing.selected_recommendation as Recommendation);
    }
  }, []);

  const clearSensitiveState = useCallback(() => {
    localStorage.removeItem(sessionKey);
    setMessages([]);
    setRecommendations([]);
    setSelectedSlot(null);
    setSelectedRecommendation(null);
    setBooking(null);
    setCollectedData({});
    setProfile(null);
    setStatus('');
    setCurrentStep('');
    setEscalation(null);
    setProgressOpen(false);
    setBookingAnnouncement('');
  }, []);

  const handleUnauthorized = useCallback(
    (err: unknown) => {
      if (!(err instanceof ApiClientError) || err.status !== 401) return false;
      clearSensitiveState();
      navigate('/sign-in?role=patient', {
        replace: true,
        state: {
          notice: err.code === 'SESSION_EXPIRED' ? 'Your session expired because of inactivity.' : undefined,
        },
      });
      return true;
    },
    [clearSensitiveState, navigate],
  );

  useEffect(() => {
    if (!sessionId) {
      if (orgSlug) {
        // Pre-validate org slug before redirecting to sign-in
        apiRequestAbsolute(`/api/v1/organizations/slug/${orgSlug}`)
          .then(() => setOrgPrecheck(false))
          .catch((err) => {
            setError(err instanceof Error ? err.message : 'This clinic link is invalid or inactive.');
          });
      }
      return;
    }
    localStorage.setItem(sessionKey, String(sessionId));
    const sessionUrl = orgSlug
      ? `/api/chat/organizations/${orgSlug}/sessions/${sessionId}`
      : `/api/chat/sessions/${sessionId}`;

    Promise.all([apiRequestAbsolute<ChatSessionResponse>(sessionUrl), getPatientProfile()])
      .then(([sessionData, profileData]) => {
        applySession(sessionData);
        setProfile(profileData.patient);
      })
      .catch((err) => {
        if (handleUnauthorized(err)) return;
        setError(err instanceof Error ? err.message : 'The chat session could not be restored.');
      })
      .finally(() => setLoading(false));
  }, [applySession, handleUnauthorized, sessionId, orgSlug]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, submitting]);

  useEffect(() => {
    if (!progressOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (progressRef.current && !progressRef.current.contains(event.target as Node)) {
        setProgressOpen(false);
      }
    };
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setProgressOpen(false);
        progressTriggerRef.current?.focus();
      }
    };

    document.addEventListener('mousedown', handlePointerDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handlePointerDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [progressOpen]);

  const allSlots = useMemo(
    () => recommendations.flatMap((recommendation) => {
      return recommendation.locations.flatMap(loc => loc.available_slots);
    }),
    [recommendations],
  );
  const progressSteps = useMemo(
    () => buildProgress(status, currentStep, collectedData),
    [status, currentStep, collectedData],
  );
  const statusLabel = workflowStatusLabel(status, escalation?.type);
  const sessionClosed = terminalStatuses.has(status);
  const hasSidebarContent = Boolean((error && !booking) || selectedSlot || recommendations.length > 0 || (!booking && !sessionClosed));

  if (!sessionId) {
    if (orgPrecheck && !error) {
      return (
        <main className="patient-chat-page">
          <section className="patient-chat-shell">
            <div className="chat-loading" role="status" aria-live="polite">
              Verifying clinic link...
            </div>
          </section>
        </main>
      );
    }
    if (error) {
      return (
        <main className="patient-chat-page">
          <section className="patient-chat-shell">
            <div role="alert" className="chat-alert" style={{ margin: '2rem', textAlign: 'center' }}>
              <h2>Unavailable</h2>
              <p>{error}</p>
            </div>
          </section>
        </main>
      );
    }
    return <Navigate to={`/sign-in?role=patient${orgSlug ? `&org=${orgSlug}` : ''}`} replace />;
  }

  const sendMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!input.trim() || submitting) return;
    const message = input;
    const previousMessages = messages;
    setInput('');
    setError(null);
    setSubmitting(true);
    setMessages((previous) => [...previous, { role: 'patient', content: message }]);
    try {
      const msgUrl = orgSlug
        ? `/api/chat/organizations/${orgSlug}/sessions/${sessionId}/messages`
        : `/api/chat/sessions/${sessionId}/messages`;
      const data = await apiRequestAbsolute<ChatSessionResponse>(msgUrl, {
        method: 'POST',
        body: JSON.stringify({ message }),
      });
      applySession(data);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setMessages(previousMessages);
      setInput(message);
      setError(err instanceof Error ? err.message : 'The message could not be sent.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleComposerKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  };

  const chooseSlot = async (_recommendation: Recommendation, slot: Slot) => {
    setSubmitting(true);
    setError(null);
    try {
      const selectUrl = orgSlug
        ? `/api/chat/organizations/${orgSlug}/sessions/${sessionId}/appointments/select`
        : `/api/chat/sessions/${sessionId}/appointments/select`;
      const data = await apiRequestAbsolute<ChatSessionResponse>(selectUrl, {
        method: 'POST',
        body: JSON.stringify({ slotId: slot.id }),
      });
      applySession(data);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      setError(err instanceof ApiClientError ? err.message : 'The appointment could not be selected.');
      setSelectedSlot(null);
      setSelectedRecommendation(null);
    } finally {
      setSubmitting(false);
    }
  };

  const confirmAppointment = async () => {
    if (!selectedSlot || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const confirmUrl = orgSlug
        ? `/api/chat/organizations/${orgSlug}/sessions/${sessionId}/appointments/confirm`
        : `/api/chat/sessions/${sessionId}/appointments/confirm`;
      const data = await apiRequestAbsolute<ChatSessionResponse>(confirmUrl, {
        method: 'POST',
      });
      applySession(data);
      setBookingAnnouncement('Appointment confirmed.');
      setSelectedSlot(null);
      setSelectedRecommendation(null);
    } catch (err) {
      if (handleUnauthorized(err)) return;
      if (err instanceof ApiClientError && err.status === 422 && err.code === 'SLOT_NOT_OFFERED') {
          setSelectedSlot(null);
          setSelectedRecommendation(null);
      }
      setError(err instanceof ApiClientError ? err.message : 'The appointment could not be confirmed.');
    } finally {
      setSubmitting(false);
    }
  };

  const signOut = async () => {
    try {
      await logoutPatient();
    } catch {
      // The local sensitive state is cleared even if the logout response is unavailable.
    }
    clearSensitiveState();
    navigate('/sign-in?role=patient', { replace: true });
  };

  return (
    <main className="patient-chat-page">
      <section className="patient-chat-shell">
        <header className="patient-chat-header">
          <div>
            <p className="patient-chat-kicker">Patient scheduling</p>
            <h1>Appointment intake</h1>
          </div>
          <div className="patient-chat-actions">
            <div className="workflow-menu" ref={progressRef}>
              <button
                type="button"
                ref={progressTriggerRef}
                className="workflow-trigger"
                aria-expanded={progressOpen}
                aria-controls="workflow-progress-menu"
                aria-label={`Scheduling progress: ${statusLabel}`}
                onClick={() => setProgressOpen((open) => !open)}
              >
                <span>{statusLabel}</span>
                <ChevronDown size={16} aria-hidden />
              </button>
              {progressOpen && (
                <div
                  id="workflow-progress-menu"
                  className="workflow-popover"
                  role="dialog"
                  aria-label={booking ? 'Appointment confirmed details' : 'Scheduling progress'}
                >
                  <WorkflowDisclosureContent
                    booking={booking}
                    collectedData={collectedData}
                    escalationReason={escalation?.reason}
                    progressSteps={progressSteps}
                  />
                </div>
              )}
            </div>
            {profile && (
              <PatientAccountMenu
                profile={profile}
                onProfile={() => navigate('/patient/profile')}
                onSignOut={signOut}
              />
            )}
          </div>
        </header>

        {loading ? (
          <div className="chat-loading" role="status" aria-live="polite">
            Restoring your chat session...
          </div>
        ) : (
          <div className={`patient-chat-grid ${hasSidebarContent ? '' : 'patient-chat-grid-single'}`}>
            <section aria-label="Conversation" className="chat-card chat-conversation">
              <div className="chat-card-header">
                <Stethoscope size={20} aria-hidden />
                <strong>Guided intake</strong>
              </div>
              <div className="chat-messages">
                {messages.length === 0 ? (
                  <p className="chat-empty">No messages yet.</p>
                ) : (
                  messages.map((message, index) => (
                    <div
                      key={`${message.sequenceNumber || index}-${message.role}`}
                      className={`message-row ${message.role === 'patient' ? 'message-row-patient' : 'message-row-assistant'}`}
                    >
                      <div className={`message-bubble ${message.role === 'patient' ? 'message-bubble-patient' : 'message-bubble-assistant'}`}>
                        {message.content}
                      </div>
                    </div>
                  ))
                )}
                {submitting && (
                  <div className="message-row message-row-assistant" aria-live="polite">
                    <div className="message-bubble message-bubble-assistant message-bubble-thinking">
                      <Loader2 size={16} className="spin" aria-hidden />
                      <span>Scheduling assistant is thinking...</span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
              <form onSubmit={sendMessage} className="chat-composer">
                <label htmlFor="chat-message" className="sr-only">Message the scheduling assistant</label>
                <textarea
                  id="chat-message"
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  disabled={submitting || sessionClosed}
                  placeholder="Message the scheduling assistant"
                  rows={1}
                  spellCheck
                  autoCorrect="on"
                  autoCapitalize="sentences"
                  aria-label="Message the scheduling assistant"
                />
                <button type="submit" disabled={submitting || !input.trim() || sessionClosed} aria-busy={submitting}>
                  {submitting ? <Loader2 size={17} className="spin" aria-hidden /> : <Send size={17} aria-hidden />}
                  <span>{submitting ? 'Sending' : 'Send'}</span>
                </button>
              </form>
            </section>

            {hasSidebarContent && (
            <aside aria-label="Appointment scheduling" className="chat-sidebar">
              {error && !booking && (
                <div role="alert" className="chat-alert">
                  {error}
                </div>
              )}

              {selectedSlot && selectedRecommendation ? (
                <section className="chat-card review-card">
                  <h2>Review appointment</h2>
                  <Detail label="Physician" value={selectedRecommendation.physician_name} />
                  <Detail label="Specialty" value={selectedRecommendation.specialty} />
                  <Detail label="Clinic" value={selectedSlot.location.name} />
                  <Detail label="Date and time" value={formatDateTime(selectedSlot)} />
                  <Detail label="Appointment type" value={displayValue(collectedData.appointment_type)} />
                  <div className="review-actions">
                    <button type="button" onClick={() => setSelectedSlot(null)}>
                      Change time
                    </button>
                    <button type="button" onClick={confirmAppointment} disabled={submitting}>
                      Confirm appointment
                    </button>
                  </div>
                </section>
              ) : recommendations.length > 0 ? (
                <section className="recommendations-list">
                  <div className="chat-card recommendation-intro">
                    <h2>Recommended physicians</h2>
                    <p>Times shown in clinic local time.</p>
                  </div>
                  {recommendations.map((recommendation) => (
                    <article key={recommendation.physician_id} className="chat-card recommendation-card">
                      <div className="recommendation-heading">
                        <div aria-hidden className="recommendation-initials">
                          {recommendation.initials}
                        </div>
                        <div>
                          <h3>{recommendation.physician_name}</h3>
                          <p>{recommendation.specialty}</p>
                        </div>
                      </div>
                      <p className="recommendation-explanation">{recommendation.match_explanation}</p>
                      <div className="recommendation-labels">
                        {recommendation.labels.map((label) => (
                          <span key={label}>{label}</span>
                        ))}
                      </div>
                      <div className="recommendation-locations">
                        {recommendation.locations.map((loc) => (
                          <div key={loc.clinic_location_code} className="recommendation-location-group">
                            <h4 className="recommendation-location-title">
                              <MapPin size={16} aria-hidden /> {loc.clinic_location}
                              <span className="location-label">— {loc.is_preferred ? 'Preferred location' : 'Alternative location'}</span>
                            </h4>
                            <div className="recommendation-labels">
                              {(loc.labels || []).map((label) => (
                                <span key={label} className="location-sub-label">{label}</span>
                              ))}
                            </div>
                            <div className="slot-buttons">
                              {loc.available_slots.map((slot) => (
                                <button
                                  key={slot.id}
                                  type="button"
                                  onClick={() => chooseSlot(recommendation, slot)}
                                >
                                  <span>
                                    <Clock size={15} aria-hidden /> {formatTime(slot)}
                                  </span>
                                  <span>
                                    <CalendarDays size={14} aria-hidden /> {formatDate(slot)}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </article>
                  ))}
                </section>
              ) : (
                <section className="chat-card intake-placeholder">
                  <h2>
                    <UserRound size={20} aria-hidden /> Intake in progress
                  </h2>
                  <p>Recommendations will appear after the required scheduling details are collected.</p>
                  {allSlots.length === 0 ? null : <p>{allSlots.length} slots loaded.</p>}
                </section>
              )}
            </aside>
            )}
          </div>
        )}
        <div className="sr-only" role="status" aria-live="polite">
          {bookingAnnouncement}
        </div>
      </section>
    </main>
  );
}

function WorkflowDisclosureContent({
  booking,
  collectedData,
  escalationReason,
  progressSteps,
}: {
  booking: Booking | null;
  collectedData: Record<string, unknown>;
  escalationReason?: string;
  progressSteps: ProgressStep[];
}) {
  return (
    <div className="workflow-disclosure-content">
      {booking ? (
        <section aria-labelledby="appointment-confirmed-heading" className="workflow-confirmation">
          <h2 id="appointment-confirmed-heading">
            <CheckCircle2 size={18} aria-hidden /> Appointment confirmed
          </h2>
          <Detail label="Confirmation ID" value={`Appointment ${booking.id}`} />
          <Detail label="Physician" value={booking.doctor.full_name} />
          <Detail label="Specialty" value={`${booking.body_part} ${booking.issue_type}`} />
          <Detail label="Clinic" value={booking.location.name} />
          <Detail label="Date and time" value={formatDateTime(booking.slot)} />
          <Detail label="Appointment type" value={displayValue(collectedData.appointment_type)} />
          <Detail label="Visit reason" value={`${booking.body_part} ${booking.issue_type}`} />
          <Detail label="Patient" value={booking.patient.full_name} />
          <Detail label="Contact" value={[booking.patient.phone, booking.patient.email].filter(Boolean).join(' / ')} />
        </section>
      ) : (
        <section aria-labelledby="scheduling-progress-heading">
          <h2 id="scheduling-progress-heading" className="workflow-popover-title">
            Scheduling progress
          </h2>
          {escalationReason && <p className="workflow-escalation-reason">{escalationReason}</p>}
        </section>
      )}
      <ol aria-label="Scheduling progress checklist">
        {progressSteps.map((step) => (
          <li key={step.label} className={`workflow-step workflow-step-${step.state.toLowerCase()}`}>
            <span>{step.label}</span>
            <strong>{step.state}</strong>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="chat-detail">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function workflowStatusLabel(status: string, escalationType?: string) {
  const labels: Record<string, string> = {
    active: 'Patient verification',
    patient_access: 'Patient verification',
    collecting_intake: 'Intake in progress',
    routing: 'Finding the right physician',
    selecting_appointment: 'Choose an appointment',
    awaiting_slot_selection: 'Choose an appointment',
    awaiting_confirmation: 'Review appointment',
    booked: 'Appointment confirmed',
    completed: 'Appointment confirmed',
    confirmed: 'Appointment confirmed',
    care_team_handoff: 'Care team follow-up',
    escalated_human: 'Care team follow-up',
    escalated_emergency: 'Urgent safety guidance',
    abandoned: 'Care team follow-up',
  };
  if (status === 'escalated' && escalationType === 'emergency') return 'Urgent safety guidance';
  if (status === 'escalated') return 'Care team follow-up';
  return labels[status] || 'Patient verification';
}

function buildProgress(status: string, currentStep: string, data: Record<string, unknown>): ProgressStep[] {
  const currentIndex = workflowIndex(status, currentStep, data);
  const terminalConfirmed = ['confirmed', 'booked', 'completed'].includes(status);
  return workflowSteps.map((label, index) => {
    let state: ProgressState = index < currentIndex ? 'Completed' : index === currentIndex ? 'Current' : 'Upcoming';
    if (terminalConfirmed) state = 'Completed';
    return { label, state };
  });
}

function workflowIndex(status: string, currentStep: string, data: Record<string, unknown>) {
  if (['confirmed', 'booked', 'completed'].includes(status)) return workflowSteps.length - 1;
  if (['selecting_appointment', 'awaiting_slot_selection', 'awaiting_confirmation'].includes(status)) return 6;
  if (status === 'routing' || currentStep === 'routing_recommendation') return 5;
  if (status === 'patient_access' || currentStep === 'identify_patient') return 0;
  if (status === 'care_team_handoff' || status === 'escalated') return Math.max(1, intakeIndex(data));
  return intakeIndex(data);
}

function intakeIndex(data: Record<string, unknown>) {
  if (!data.chief_complaint || !data.body_part || !data.issue_type) return 1;
  if (!data.symptom_duration || !data.severity) return 2;
  if (!data.appointment_type) return 3;
  if (!data.preferred_location || !data.preferred_date_or_time || !data.preferred_time_of_day) return 4;
  return 5;
}

function formatDateTime(slot: { starts_at: string; display_datetime?: string }) {
  if (slot.display_datetime) return slot.display_datetime;
  return new Date(slot.starts_at).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'America/Los_Angeles',
  });
}

function formatDate(value: string | Slot) {
  if (typeof value !== 'string' && value.display_date) return value.display_date;
  const raw = typeof value === 'string' ? value : value.starts_at;
  return new Date(raw).toLocaleDateString([], { month: 'short', day: 'numeric', timeZone: 'America/Los_Angeles' });
}

function formatTime(value: string | Slot) {
  if (typeof value !== 'string' && value.display_time) return value.display_time;
  const raw = typeof value === 'string' ? value : value.starts_at;
  return new Date(raw).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', timeZone: 'America/Los_Angeles' });
}

function displayValue(value: unknown) {
  if (!value) return 'Appointment';
  return String(value).replaceAll('_', ' ');
}
