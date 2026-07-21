import type { TranscriptTurn } from '../types/api';

export function TranscriptTimeline({ turns }: { turns: TranscriptTurn[] }) {
  return (
    <div className="timeline transcript-timeline">
      {turns.map((turn) => (
        <article key={turn.id ?? turn.sequence_number} className={`timeline-item speaker-${turn.speaker.toLowerCase()}`}>
          <div className="timeline-dot" />
          <div className="timeline-card">
            <div className="timeline-meta"><strong>{turn.speaker === 'AI' ? 'Scheduling Assistant' : 'Caller'}</strong><span>{new Date(turn.occurred_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span></div>
            <p>{turn.text}</p>
          </div>
        </article>
      ))}
    </div>
  );
}
