import type { RoutingDecision } from '../types/api';
import { StatusBadge } from './StatusBadge';

export function RoutingTimeline({ decisions }: { decisions: RoutingDecision[] }) {
  return (
    <div className="routing-list">
      {decisions.map((decision) => (
        <article key={decision.id} className="routing-item">
          <div className="routing-item-head">
            <div><strong>{decision.doctor?.full_name ?? 'Routing engine'}</strong><small>{decision.reason_code.replaceAll('_', ' ')}</small></div>
            <StatusBadge status={decision.decision} />
          </div>
          <p>{decision.human_readable_reason}</p>
        </article>
      ))}
    </div>
  );
}
