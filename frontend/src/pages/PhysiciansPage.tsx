import { useQuery } from '@tanstack/react-query';
import { MapPin } from 'lucide-react';
import { schedulingApi } from '../api/schedulingApi';
import { PageHeader } from '../components/PageHeader';
import { ErrorState, LoadingState } from '../components/States';

export function PhysiciansPage() {
  const query = useQuery({ queryKey: ['doctors'], queryFn: schedulingApi.doctors });
  if (query.isLoading) return <LoadingState label="Loading physician protocol" />;
  if (query.isError || !query.data) return <ErrorState message={query.error?.message ?? 'Unknown error'} />;
  return (
    <>
      <PageHeader title="Physicians" subtitle="Read-only protocol source of truth encoded in normalized database rows" />
      <section className="physician-grid">
        {query.data.doctors.map((doctor) => (
          <article className="physician-card" key={doctor.id}>
            <div className="physician-head"><div className="doctor-avatar">{doctor.first_name[0]}{doctor.last_name[0]}</div><div><h2>{doctor.full_name}</h2><span className={doctor.accepts_new_patients ? 'accepts-new' : 'returning-only'}>{doctor.accepts_new_patients ? 'Accepts new patients' : 'Returning patients only'}</span></div></div>
            <div className="location-list"><MapPin size={16} />{doctor.locations.map((location) => <span key={location.id}>{location.name}</span>)}</div>
            <div className="capability-groups">
              {[...new Set(doctor.capabilities.map((item) => item.body_part))].map((bodyPart) => <div key={bodyPart}><strong>{bodyPart}</strong><div>{doctor.capabilities.filter((item) => item.body_part === bodyPart).map((item) => <span className="capability-chip" key={item.issue_type}>{item.issue_type}</span>)}</div></div>)}
            </div>
          </article>
        ))}
      </section>
    </>
  );
}
