import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, MessageSquare } from 'lucide-react';
import { apiRequest } from '../api/client';
import { PageHeader } from '../components/PageHeader';
import { AppointmentSummary } from '../components/AppointmentSummary';
import type { Appointment } from '../types/api';

interface ChatSessionListItem {
  id: number;
  created_at: string;
  updated_at: string;
  status: string;
  patient: { full_name: string; is_new_patient?: boolean } | null;
  collected_data: {
    chief_complaint?: string | null;
    body_part?: string | null;
    side?: string | null;
    symptom_duration?: string | null;
    severity?: string | number | null;
    appointment_type?: string | null;
    preferred_location?: string | null;
    preferred_date_or_time?: string | null;
    insurance?: string | null;
    [key: string]: unknown;
  };
  routing_result?: {
    web_recommendations?: Array<{ physician_name: string; match_explanation: string }>;
  } | null;
  appointment?: {
    id: number;
    doctor: { full_name: string };
    location: { name: string };
    slot: { starts_at: string; display_datetime?: string };
  } | null;
  escalation_type?: string | null;
}

interface ChatSessionDetail extends ChatSessionListItem {
  messages: Array<{ id: number; role: string; content: string; sequence_number: number; created_at: string }>;
  events: Array<{ id: number; event_type: string; event_data: Record<string, unknown> | null; created_at: string }>;
  escalation_reason?: string | null;
  escalation_trigger_message?: { content: string; sequence_number: number } | null;
}

export function WebChatSessionsPage() {
  const { sessionId } = useParams();
  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  const [selected, setSelected] = useState<ChatSessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<{ chat_sessions: ChatSessionListItem[] }>('/dashboard/chat-sessions')
      .then((data) => setSessions(data.chat_sessions || []))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load sessions.'));
  }, []);

  useEffect(() => {
    if (sessionId) {
      loadDetail(Number(sessionId));
    } else {
      setSelected(null);
    }
  }, [sessionId]);

  const loadDetail = (id: number) => {
    apiRequest<{ chat_session: ChatSessionDetail }>(`/dashboard/chat-sessions/${id}`)
      .then((data) => setSelected(data.chat_session))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load session detail.'));
  };

  if (sessionId) {
    if (error) {
      return (
        <div>
          <PageHeader title="Web Chat Sessions" subtitle="Review patient intake chat sessions." />
          <div role="alert" style={{ margin: '1rem', padding: '0.75rem', border: '1px solid #f59e0b', borderRadius: '8px' }}>{error}</div>
        </div>
      );
    }
    if (!selected) {
      return <div style={{ padding: '2rem' }}>Loading session detail...</div>;
    }

    return (
      <>
        <Link to="/web-chat-sessions" className="back-link"><ArrowLeft size={16} /> Back to web chat sessions</Link>
        <PageHeader 
          title={`Web Chat Session #${selected.id}`} 
          subtitle={`${new Date(selected.created_at).toLocaleString([], { dateStyle: 'long', timeStyle: 'short', timeZone: 'America/Los_Angeles' })} · Source: Web chat`} 
        />
        <section className="detail-grid">
          <div className="detail-main">
            {selected.appointment ? (
              <AppointmentSummary appointment={selected.appointment as unknown as Appointment} />
            ) : (
              <div style={{ marginBottom: '1.5rem', padding: '1rem', background: 'white', border: '1px solid #d9e2ec', borderRadius: '8px' }}>
                <h3 style={{ marginTop: 0, fontSize: '1rem' }}>Booking status</h3>
                <p style={{ margin: 0, color: '#334155' }}>{selected.status}</p>
              </div>
            )}
            
            <article className="panel">
              <div className="panel-head">
                <div>
                  <h2>Full transcript</h2>
                  <p>Speaker-labeled conversation stored by the scheduling API</p>
                </div>
                <MessageSquare size={19} />
              </div>
              <div className="transcript-container">
                <ol className="transcript-list">
                  {selected.messages.map((m, index) => {
                    const speakerLabel = m.role === 'assistant' ? 'Scheduling Assistant' : 'Patient';
                    const isAssistant = m.role === 'assistant';
                    return (
                      <li key={index} className={`transcript-turn ${isAssistant ? 'assistant-turn' : 'user-turn'}`}>
                        <div className="turn-speaker">{speakerLabel}</div>
                        <div className="turn-text">{m.content}</div>
                      </li>
                    );
                  })}
                </ol>
              </div>
            </article>
          </div>
          <aside className="detail-sidebar">
            <article className="panel">
              <div className="panel-head">
                <div><h2>Patient & Intake</h2><p>Structured summary</p></div>
              </div>
              <div className="sidebar-section">
                <div className="data-row"><span>Patient</span><strong>{selected.patient?.full_name ?? 'Unidentified'}</strong></div>
                <div className="data-row"><span>Status</span><strong>{selected.patient?.is_new_patient ? 'New patient' : 'Returning patient'}</strong></div>
                <div className="data-row"><span>Complaint</span><strong>{String(selected.collected_data?.chief_complaint || '-')}</strong></div>
                <div className="data-row"><span>Body part</span><strong>{`${selected.collected_data?.body_part || '-'} ${selected.collected_data?.side || ''}`}</strong></div>
                <div className="data-row"><span>Duration</span><strong>{selected.collected_data?.symptom_duration ? String(selected.collected_data.symptom_duration) : 'Not captured'}</strong></div>
                <div className="data-row"><span>Severity</span><strong>{String(selected.collected_data?.severity || '-')}</strong></div>
                <div className="data-row"><span>Appt type</span><strong>{String(selected.collected_data?.appointment_type || '-')}</strong></div>
                <div className="data-row"><span>Pref. Location</span><strong>{String(selected.collected_data?.preferred_location || '-')}</strong></div>
                <div className="data-row"><span>Pref. Time</span><strong>{String(selected.collected_data?.preferred_date_or_time || '-')}</strong></div>
                {selected.collected_data?.insurance && (
                  <div className="data-row"><span>Insurance</span><strong>{String(selected.collected_data.insurance)}</strong></div>
                )}
              </div>
            </article>

            {(selected.routing_result?.web_recommendations?.[0] || selected.escalation_type) && (
              <article className="panel">
                <div className="panel-head">
                  <div><h2>Routing result</h2><p>Decision path</p></div>
                </div>
                <div className="sidebar-section">
                  {selected.routing_result?.web_recommendations?.[0] && (
                    <>
                      <div className="data-row"><span>Matched physician</span><strong>{selected.routing_result.web_recommendations[0].physician_name}</strong></div>
                      <div className="routing-explanation" style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#f8fafc', borderRadius: '6px', fontSize: '0.85rem' }}>
                        {selected.routing_result.web_recommendations[0].match_explanation}
                      </div>
                    </>
                  )}
                  {selected.escalation_type && (
                    <div style={{ marginTop: '1rem', padding: '0.75rem', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: '6px', fontSize: '0.85rem' }}>
                      <strong style={{ color: '#9a3412', display: 'block', marginBottom: '0.25rem' }}>Escalation: {selected.escalation_type}</strong>
                      <p style={{ margin: 0, color: '#9a3412' }}>{selected.escalation_reason}</p>
                      {selected.escalation_trigger_message && (
                        <p style={{ margin: '0.5rem 0 0 0', color: '#9a3412', fontStyle: 'italic' }}>"{selected.escalation_trigger_message.content}"</p>
                      )}
                    </div>
                  )}
                </div>
              </article>
            )}
          </aside>
        </section>
      </>
    );
  }

  return (
    <div>
      <PageHeader title="Web Chat Sessions" subtitle="Review patient intake chat sessions." />
      {error && <div role="alert" style={{ margin: '1rem', padding: '0.75rem', border: '1px solid #f59e0b', borderRadius: '8px' }}>{error}</div>}
      <div style={{ padding: '1rem', display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: '1rem' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', background: 'white' }}>
          <thead>
            <tr>
              <th style={headerCell}>Date</th>
              <th style={headerCell}>Patient</th>
              <th style={headerCell}>Status</th>
              <th style={headerCell}>Complaint</th>
              <th style={headerCell}>Matched physician</th>
              <th style={headerCell}>Booking</th>
              <th style={headerCell}>Review</th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 ? (
              <tr><td colSpan={7} style={bodyCell}>No web chat sessions found.</td></tr>
            ) : sessions.map((session) => {
              const recommendation = session.routing_result?.web_recommendations?.[0];
              return (
                <tr key={session.id}>
                  <td style={bodyCell}>{new Date(session.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short', timeZone: 'America/Los_Angeles' })}</td>
                  <td style={bodyCell}>{session.patient ? session.patient.full_name : 'Unidentified'}</td>
                  <td style={bodyCell}>{session.status}</td>
                  <td style={bodyCell}>{session.collected_data?.chief_complaint || '-'}</td>
                  <td style={bodyCell}>{recommendation?.physician_name || '-'}</td>
                  <td style={bodyCell}>{session.appointment ? `Appointment ${session.appointment.id}` : session.escalation_type || '-'}</td>
                  <td style={bodyCell}>
                    <Link to={`/web-chat-sessions/${session.id}`} style={buttonStyle}>Open</Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const headerCell = { textAlign: 'left' as const, borderBottom: '1px solid #cbd5e1', padding: '0.75rem' };
const bodyCell = { padding: '0.75rem', borderBottom: '1px solid #e2e8f0', verticalAlign: 'top' as const };
const buttonStyle = { border: '1px solid #155eef', color: '#155eef', background: 'white', borderRadius: '6px', padding: '0.4rem 0.7rem', fontWeight: 700 };
