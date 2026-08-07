import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query';
import {
  Building2,
  ChevronRight,
  Filter,
  Pencil,
  Plus,
  Search,
  Stethoscope,
  UsersRound,
} from 'lucide-react';
import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { schedulingApi } from '../api/schedulingApi';
import { DataTable } from '../components/DataTable';
import { EmptyState, ErrorState, LoadingState } from '../components/States';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';
import type { Doctor, DoctorInput, Organization, OrganizationInput, OrganizationStatus } from '../types/api';

const DEFAULT_TIMEZONE = 'America/Los_Angeles';
const ORGANIZATION_TABS = ['Details', 'Doctors', 'Settings', 'Activity'] as const;
const CAPABILITY_AREA_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'General', label: 'General' },
  { value: 'Primary Care', label: 'Primary Care' },
  { value: 'Heart/Circulation', label: 'Cardiology / Heart & Circulation' },
  { value: 'Lungs/Breathing', label: 'Pulmonology / Lungs & Breathing' },
  { value: 'Mouth/Teeth/Tongue', label: 'Dental / Mouth, Teeth & Tongue' },
  { value: 'Ear/Nose/Throat', label: 'ENT / Ear, Nose & Throat' },
  { value: 'Eyes/Vision', label: 'Eyes & Vision' },
  { value: 'Skin/Hair/Nails', label: 'Dermatology / Skin, Hair & Nails' },
  { value: 'Digestive/Abdomen', label: 'Gastroenterology / Digestive & Abdomen' },
  { value: 'Brain/Nerves', label: 'Neurology / Brain & Nerves' },
  { value: 'Kidneys/Urinary', label: 'Urology / Kidneys & Urinary' },
  { value: 'Reproductive/Pelvic', label: 'OB/GYN / Reproductive & Pelvic' },
  { value: 'Pediatrics', label: 'Pediatrics' },
  { value: 'Diabetes/Thyroid', label: 'Endocrine / Diabetes & Thyroid' },
  { value: 'Mental Health', label: 'Mental Health & Behavior' },
  { value: 'Injury/Wounds', label: 'Injury & Wounds' },
  { value: 'Bones/Joints/Muscles', label: 'Bones / Joints / Muscles' },
  { value: 'Knee', label: 'Knee' },
  { value: 'Hip', label: 'Hip' },
  { value: 'Shoulder', label: 'Shoulder' },
  { value: 'Upper Arm', label: 'Upper Arm' },
  { value: 'Elbow', label: 'Elbow' },
  { value: 'Forearm', label: 'Forearm' },
  { value: 'Hand/Wrist', label: 'Hand/Wrist' },
  { value: 'Upper Leg', label: 'Upper Leg' },
  { value: 'Lower Leg', label: 'Lower Leg' },
  { value: 'Foot/Ankle', label: 'Foot/Ankle' },
  { value: 'Spine', label: 'Spine' },
] as const;
const VISIT_REASON_OPTIONS = [
  { value: '', label: 'None' },
  { value: 'General', label: 'General' },
  { value: 'Pain', label: 'Pain' },
  { value: 'Swelling', label: 'Swelling' },
  { value: 'Injury', label: 'Injury' },
  { value: 'Fracture', label: 'Fracture' },
  { value: 'Bleeding', label: 'Bleeding' },
  { value: 'Rash/Itching', label: 'Rash / Itching' },
  { value: 'Infection', label: 'Infection' },
  { value: 'Numbness/Tingling', label: 'Numbness / Tingling' },
  { value: 'Weakness', label: 'Weakness' },
  { value: 'Breathing Concern', label: 'Breathing concern' },
  { value: 'Follow-up', label: 'Follow-up' },
  { value: 'Routine Consult', label: 'Routine consult' },
  { value: 'Preventive/Wellness', label: 'Preventive / wellness' },
  { value: 'Medication/Refill', label: 'Medication / refill' },
  { value: 'Lab/Test Result', label: 'Lab / test result' },
  { value: 'Sports Medicine', label: 'Sports Medicine' },
  { value: 'Joint Replacement', label: 'Joint Replacement' },
] as const;

type OrganizationTab = (typeof ORGANIZATION_TABS)[number];
type CreateOrganizationMutation = UseMutationResult<{ organization: Organization }, Error, OrganizationInput>;
type UpdateOrganizationMutation = UseMutationResult<
  { organization: Organization },
  Error,
  { id: number; body: Partial<OrganizationInput> }
>;
type CreateDoctorMutation = UseMutationResult<
  { doctor: Doctor },
  Error,
  { organizationId: number; body: DoctorInput }
>;
type UpdateDoctorMutation = UseMutationResult<
  { doctor: Doctor },
  Error,
  { organizationId: number; doctorId: number; body: Partial<DoctorInput> }
>;

export function OrganizationsPage() {
  const queryClient = useQueryClient();
  const organizationsQuery = useQuery({ queryKey: ['organizations'], queryFn: schedulingApi.organizations });
  const organizations = useMemo(() => organizationsQuery.data?.organizations ?? [], [organizationsQuery.data]);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState<number | null>(null);
  const [organizationSearch, setOrganizationSearch] = useState('');
  const [activeTab, setActiveTab] = useState<OrganizationTab>('Doctors');
  const [createPanelOpen, setCreatePanelOpen] = useState(false);

  useEffect(() => {
    if (organizations.length === 0) {
      setSelectedOrganizationId(null);
      return;
    }
    if (!selectedOrganizationId || !organizations.some((organization) => organization.id === selectedOrganizationId)) {
      setSelectedOrganizationId(organizations[0].id);
    }
  }, [organizations, selectedOrganizationId]);

  const selectedOrganization =
    organizations.find((organization) => organization.id === selectedOrganizationId) ?? null;
  const doctorsQuery = useQuery({
    queryKey: ['organization-doctors', selectedOrganizationId],
    queryFn: () => schedulingApi.organizationDoctors(selectedOrganizationId as number),
    enabled: selectedOrganizationId !== null,
  });
  const selectedDoctors = useMemo(() => {
    if (!selectedOrganization) return [];
    return (doctorsQuery.data?.doctors ?? []).filter((doctor) => doctor.organization_id === selectedOrganization.id);
  }, [doctorsQuery.data, selectedOrganization]);
  const selectedDoctorCount = doctorsQuery.isSuccess
    ? selectedDoctors.length
    : selectedOrganization?.doctor_count ?? selectedDoctors.length;
  const totalDoctors = organizations.reduce((total, organization) => {
    if (organization.id === selectedOrganization?.id) return total + selectedDoctorCount;
    return total + (organization.doctor_count ?? 0);
  }, 0);
  const activeOrganizations = organizations.filter((organization) => organization.active).length;
  const activePercent = organizations.length === 0 ? '0%' : `${Math.round((activeOrganizations / organizations.length) * 100)}%`;

  const createOrganization = useMutation({
    mutationFn: schedulingApi.createOrganization,
    onSuccess: async (data) => {
      setSelectedOrganizationId(data.organization.id);
      setCreatePanelOpen(false);
      setActiveTab('Settings');
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
    },
  });

  const updateOrganization = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<OrganizationInput> }) =>
      schedulingApi.updateOrganization(id, body),
    onSuccess: async (data) => {
      setSelectedOrganizationId(data.organization.id);
      await queryClient.invalidateQueries({ queryKey: ['organizations'] });
    },
  });

  const createDoctor = useMutation({
    mutationFn: ({ organizationId, body }: { organizationId: number; body: DoctorInput }) =>
      schedulingApi.createOrganizationDoctor(organizationId, body),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['organization-doctors', variables.organizationId] }),
        queryClient.invalidateQueries({ queryKey: ['organizations'] }),
      ]);
    },
  });

  const updateDoctor = useMutation({
    mutationFn: ({ organizationId, doctorId, body }: { organizationId: number; doctorId: number; body: Partial<DoctorInput> }) =>
      schedulingApi.updateOrganizationDoctor(organizationId, doctorId, body),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: ['organization-doctors', variables.organizationId] });
    },
  });

  if (organizationsQuery.isLoading) {
    return (
      <>
        <OrganizationsHeader onCreate={() => setCreatePanelOpen(true)} />
        <LoadingState label="Loading organizations" />
      </>
    );
  }

  if (organizationsQuery.isError || !organizationsQuery.data) {
    return (
      <>
        <OrganizationsHeader onCreate={() => setCreatePanelOpen(true)} />
        <ErrorState message={organizationsQuery.error?.message ?? 'Unable to load organizations.'} />
      </>
    );
  }

  return (
    <div className="organizations-page">
      <OrganizationsHeader onCreate={() => setCreatePanelOpen(true)} />
      <OrganizationKpis
        totalOrganizations={organizations.length}
        activeOrganizations={activeOrganizations}
        activePercent={activePercent}
        totalDoctors={totalDoctors}
      />
      <section className="organization-workspace">
        <OrganizationDirectory
          organizations={organizations}
          selectedOrganizationId={selectedOrganizationId}
          search={organizationSearch}
          createPanelOpen={createPanelOpen}
          createMutation={createOrganization}
          onSearchChange={setOrganizationSearch}
          onCreateToggle={() => setCreatePanelOpen((current) => !current)}
          onSelect={(organizationId) => {
            setSelectedOrganizationId(organizationId);
            setActiveTab('Doctors');
          }}
        />
        <div className="organization-detail-column">
          {selectedOrganization ? (
            <>
              <SelectedOrganizationWorkspace
                organization={selectedOrganization}
                doctors={selectedDoctors}
                doctorCount={selectedDoctorCount}
                doctorsLoading={doctorsQuery.isLoading}
                doctorsError={doctorsQuery.isError ? doctorsQuery.error.message : null}
                activeTab={activeTab}
                updateOrganization={updateOrganization}
                createDoctor={createDoctor}
                updateDoctor={updateDoctor}
                onTabChange={setActiveTab}
              />
            </>
          ) : (
            <section className="panel organization-empty-panel">
              <EmptyState
                title="No organization selected"
                detail="Create an organization to begin configuring doctors and patient intake."
              />
            </section>
          )}
        </div>
      </section>
    </div>
  );
}

function OrganizationsHeader({ onCreate }: { onCreate: () => void }) {
  return (
    <PageHeader
      title="Organizations"
      subtitle="Create and manage client organizations, doctors, and scheduling settings."
      actions={
        <button className="button primary" type="button" onClick={onCreate}>
          <Plus size={16} />
          New organization
        </button>
      }
    />
  );
}

function OrganizationKpis({
  totalOrganizations,
  activeOrganizations,
  activePercent,
  totalDoctors,
}: {
  totalOrganizations: number;
  activeOrganizations: number;
  activePercent: string;
  totalDoctors: number;
}) {
  return (
    <section className="organization-kpis" aria-label="Organization metrics">
      <MetricCard icon={<Building2 size={21} />} tone="blue" label="Total organizations" value={totalOrganizations} detail="All time" />
      <MetricCard icon={<UsersRound size={21} />} tone="green" label="Active organizations" value={activeOrganizations} detail={`${activePercent} of total`} />
      <MetricCard icon={<Stethoscope size={21} />} tone="violet" label="Total doctors" value={totalDoctors} detail="Across all organizations" />
    </section>
  );
}

function MetricCard({
  icon,
  tone,
  label,
  value,
  detail,
}: {
  icon: ReactNode;
  tone: 'blue' | 'green' | 'violet';
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <article className="organization-kpi-card">
      <span className={`organization-kpi-icon ${tone}`}>{icon}</span>
      <span className="organization-kpi-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </span>
    </article>
  );
}

function OrganizationDirectory({
  organizations,
  selectedOrganizationId,
  search,
  createPanelOpen,
  createMutation,
  onSearchChange,
  onCreateToggle,
  onSelect,
}: {
  organizations: Organization[];
  selectedOrganizationId: number | null;
  search: string;
  createPanelOpen: boolean;
  createMutation: CreateOrganizationMutation;
  onSearchChange: (value: string) => void;
  onCreateToggle: () => void;
  onSelect: (organizationId: number) => void;
}) {
  const normalizedSearch = search.trim().toLowerCase();
  const filteredOrganizations = organizations.filter((organization) => {
    if (!normalizedSearch) return true;
    return [organization.name, organization.slug, organizationType(organization)]
      .join(' ')
      .toLowerCase()
      .includes(normalizedSearch);
  });

  return (
    <aside className="panel organization-directory" aria-label="Organization directory">
      <div className="panel-head">
        <div>
          <h2>Organization directory</h2>
          <p>Select an organization to manage its settings and resources.</p>
        </div>
      </div>
      <div className="organization-search-row">
        <label className="search-input">
          <Search size={16} aria-hidden="true" />
          <span className="sr-only">Search organizations</span>
          <input
            aria-label="Search organizations"
            value={search}
            placeholder="Search organizations..."
            onChange={(event) => onSearchChange(event.target.value)}
          />
        </label>
        <button className="icon-button" type="button" title="Filter organizations" aria-label="Filter organizations">
          <Filter size={16} />
        </button>
      </div>
      {createPanelOpen ? <OrganizationCreatePanel mutation={createMutation} /> : null}
      {organizations.length === 0 ? (
        <EmptyState title="No organizations" detail="Create the first organization to continue setup." />
      ) : filteredOrganizations.length === 0 ? (
        <EmptyState title="No matching organizations" detail="Adjust the directory search and try again." />
      ) : (
        <div className="organization-list" role="list" aria-label="Organizations">
          {filteredOrganizations.map((organization) => (
            <button
              className={organization.id === selectedOrganizationId ? 'organization-option active' : 'organization-option'}
              key={organization.id}
              type="button"
              onClick={() => onSelect(organization.id)}
            >
              <span className="organization-option-icon"><Building2 size={20} /></span>
              <span className="organization-option-copy">
                <strong>{organization.name}</strong>
                <small>{organizationType(organization)}</small>
                <small>{organization.slug}</small>
              </span>
              <span className="organization-option-meta">
                <StatusBadge status={organization.status} />
                <ChevronRight size={16} />
              </span>
            </button>
          ))}
        </div>
      )}
      <button className="button secondary full-width" type="button" onClick={onCreateToggle} aria-expanded={createPanelOpen}>
        <Plus size={15} />
        Create organization
      </button>
    </aside>
  );
}

function OrganizationCreatePanel({ mutation }: { mutation: CreateOrganizationMutation }) {
  return (
    <div className="organization-inline-form">
      <OrganizationForm
        mode="create"
        submitLabel={mutation.isPending ? 'Creating...' : 'Create organization'}
        disabled={mutation.isPending}
        onSubmit={(body, form) => {
          mutation.mutate(body, { onSuccess: () => form.reset() });
        }}
      />
      {mutation.isError ? <div className="alert-box error"><p>{mutation.error.message}</p></div> : null}
    </div>
  );
}

function SelectedOrganizationWorkspace({
  organization,
  doctors,
  doctorCount,
  doctorsLoading,
  doctorsError,
  activeTab,
  updateOrganization,
  createDoctor,
  updateDoctor,
  onTabChange,
}: {
  organization: Organization;
  doctors: Doctor[];
  doctorCount: number;
  doctorsLoading: boolean;
  doctorsError: string | null;
  activeTab: OrganizationTab;
  updateOrganization: UpdateOrganizationMutation;
  createDoctor: CreateDoctorMutation;
  updateDoctor: UpdateDoctorMutation;
  onTabChange: (tab: OrganizationTab) => void;
}) {
  return (
    <section className="panel organization-selected-panel">
      <div className="organization-selected-header">
        <div className="organization-selected-identity">
          <span className="organization-selected-icon"><Building2 size={26} /></span>
          <div>
            <div className="organization-title-line">
              <h2>{organization.name}</h2>
              <StatusBadge status={organization.status} />
            </div>
            <p>{organization.slug} - {organization.timezone}</p>
          </div>
        </div>
        <button className="button secondary" type="button" onClick={() => onTabChange('Settings')}>
          <Pencil size={15} />
          Edit organization
        </button>
      </div>
      <dl className="organization-summary">
        <SummaryTile label="Organization ID" value={organization.id} />
        <SummaryTile label="Timezone" value={organization.timezone} />
        <SummaryTile label="Doctors" value={doctorCount} />
      </dl>
      <div className="organization-tabs" role="tablist" aria-label="Organization sections">
        {ORGANIZATION_TABS.map((tab) => (
          <button
            aria-selected={activeTab === tab}
            className={activeTab === tab ? 'active' : ''}
            key={tab}
            role="tab"
            type="button"
            onClick={() => onTabChange(tab)}
          >
            {tab}
          </button>
        ))}
      </div>
      {activeTab === 'Details' ? <OrganizationDetailsTab organization={organization} doctorCount={doctorCount} /> : null}
      {activeTab === 'Doctors' ? (
        <DoctorsTab
          organization={organization}
          doctors={doctors}
          loading={doctorsLoading}
          error={doctorsError}
          createMutation={createDoctor}
          updateMutation={updateDoctor}
        />
      ) : null}
      {activeTab === 'Settings' ? (
        <OrganizationSettingsTab organization={organization} mutation={updateOrganization} />
      ) : null}
      {activeTab === 'Activity' ? (
        <EmptyState title="No activity events" detail="Activity will appear here when backend audit events are available." />
      ) : null}
    </section>
  );
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: string | number;
  tone?: 'success';
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={tone ? `summary-status ${tone}` : undefined}>{value}</dd>
    </div>
  );
}

function OrganizationDetailsTab({ organization, doctorCount }: { organization: Organization; doctorCount: number }) {
  return (
    <div className="organization-tab-panel">
      <div className="organization-details-grid">
        <DetailItem label="Organization" value={organization.name} />
        <DetailItem label="Type" value={organizationType(organization)} />
        <DetailItem label="Organization link name" value={organization.slug} />
        <DetailItem label="Status" value={organization.status} />
        <DetailItem label="Timezone" value={organization.timezone} />
        <DetailItem label="Doctor records" value={doctorCount} />
      </div>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="organization-detail-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DoctorsTab({
  organization,
  doctors,
  loading,
  error,
  createMutation,
  updateMutation,
}: {
  organization: Organization;
  doctors: Doctor[];
  loading: boolean;
  error: string | null;
  createMutation: CreateDoctorMutation;
  updateMutation: UpdateDoctorMutation;
}) {
  const [doctorSearch, setDoctorSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editingDoctor, setEditingDoctor] = useState<Doctor | null>(null);

  useEffect(() => {
    setDoctorSearch('');
    setCreateOpen(false);
    setEditingDoctor(null);
  }, [organization.id]);

  const filteredDoctors = useMemo(() => {
    const normalizedSearch = doctorSearch.trim().toLowerCase();
    if (!normalizedSearch) return doctors;
    return doctors.filter((doctor) => doctorMatchesSearch(doctor, normalizedSearch));
  }, [doctors, doctorSearch]);

  if (loading) {
    return <LoadingState label="Loading organization doctors" />;
  }

  if (error) {
    return <ErrorState message={error} />;
  }

  return (
    <div className="organization-tab-panel doctors-tab">
      <div className="tab-toolbar">
        <div>
          <h3>Doctors</h3>
          <p>Manage physicians and their capabilities for this organization.</p>
        </div>
        <div className="tab-toolbar-actions">
          <label className="search-input compact">
            <Search size={15} aria-hidden="true" />
            <span className="sr-only">Search doctors</span>
            <input
              aria-label="Search doctors"
              value={doctorSearch}
              placeholder="Search doctors..."
              onChange={(event) => setDoctorSearch(event.target.value)}
            />
          </label>
          <button
            className="button primary"
            type="button"
            onClick={() => {
              setCreateOpen((current) => !current);
              setEditingDoctor(null);
            }}
          >
            <Plus size={15} />
            Add doctor
          </button>
        </div>
      </div>
      {createOpen ? (
        <div className="organization-inline-form wide">
          <DoctorForm
            formId="new-doctor"
            submitLabel={createMutation.isPending ? 'Creating...' : 'Create doctor'}
            disabled={createMutation.isPending}
            onSubmit={(body, form) => {
              createMutation.mutate(
                { organizationId: organization.id, body },
                {
                  onSuccess: () => {
                    form.reset();
                    setCreateOpen(false);
                  },
                },
              );
            }}
          />
          {createMutation.isError ? <div className="alert-box error"><p>{createMutation.error.message}</p></div> : null}
        </div>
      ) : null}
      {editingDoctor ? (
        <div className="organization-inline-form wide">
          <div className="inline-form-header">
            <strong>Edit {editingDoctor.full_name}</strong>
            <button className="button secondary compact-button" type="button" onClick={() => setEditingDoctor(null)}>
              Cancel
            </button>
          </div>
          <DoctorForm
            formId="edit-doctor"
            doctor={editingDoctor}
            submitLabel={updateMutation.isPending ? 'Saving...' : 'Save doctor'}
            disabled={updateMutation.isPending}
            onSubmit={(body) => {
              updateMutation.mutate(
                { organizationId: organization.id, doctorId: editingDoctor.id, body },
                { onSuccess: () => setEditingDoctor(null) },
              );
            }}
          />
          {updateMutation.isError ? <div className="alert-box error"><p>{updateMutation.error.message}</p></div> : null}
        </div>
      ) : null}
      {doctors.length === 0 ? (
        <EmptyState title="No doctors" detail="Add a doctor for this organization." />
      ) : filteredDoctors.length === 0 ? (
        <EmptyState title="No matching doctors" detail="Adjust the doctor search and try again." />
      ) : (
        <DataTable label="Organization doctors" headers={['Physician', 'Status', 'New patients', 'Locations', 'Capabilities', 'Actions']}>
          {filteredDoctors.map((doctor) => (
            <tr key={doctor.id}>
              <td>
                <span className="doctor-cell">
                  <span className="doctor-avatar">{doctorInitials(doctor)}</span>
                  <span>
                    <strong>{doctor.full_name}</strong>
                    <small className="cell-subtitle">{doctor.primary_specialty}</small>
                  </span>
                </span>
              </td>
              <td><StatusBadge status={doctor.active ? 'ACTIVE' : 'INACTIVE'} /></td>
              <td>{doctor.accepts_new_patients ? 'Yes' : 'No'}</td>
              <td>{formatLocations(doctor)}</td>
              <td>{formatCapabilities(doctor)}</td>
              <td>
                <span className="table-actions">
                  <button className="button secondary compact-button" type="button" onClick={() => setEditingDoctor(doctor)}>
                    <Pencil size={14} />
                    Edit
                  </button>
                </span>
              </td>
            </tr>
          ))}
        </DataTable>
      )}
    </div>
  );
}

function OrganizationSettingsTab({
  organization,
  mutation,
}: {
  organization: Organization;
  mutation: UpdateOrganizationMutation;
}) {
  return (
    <div className="organization-tab-panel">
      <OrganizationForm
        key={organization.id}
        organization={organization}
        mode="edit"
        submitLabel={mutation.isPending ? 'Saving...' : 'Save organization'}
        disabled={mutation.isPending}
        onSubmit={(body) => {
          mutation.mutate({ id: organization.id, body });
        }}
      />
      {mutation.isError ? <div className="alert-box error"><p>{mutation.error.message}</p></div> : null}
    </div>
  );
}

function OrganizationForm({
  organization,
  mode,
  submitLabel,
  disabled,
  onSubmit,
}: {
  organization?: Organization;
  mode: 'create' | 'edit';
  submitLabel: string;
  disabled: boolean;
  onSubmit: (body: OrganizationInput, form: HTMLFormElement) => void;
}) {
  const prefix = mode === 'create' ? 'new-organization' : 'organization';
  const nameLabel = mode === 'create' ? 'New organization name' : 'Organization name';
  const timezoneLabel = mode === 'create' ? 'New organization timezone' : 'Organization timezone';

  return (
    <form
      className="organization-form"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        onSubmit(toOrganizationInput(form, mode === 'edit'), event.currentTarget);
      }}
    >
      <label htmlFor={`${prefix}-name`}>
        {nameLabel}
        <input
          id={`${prefix}-name`}
          name="name"
          defaultValue={organization?.name ?? ''}
          required
          maxLength={160}
        />
      </label>
      {mode === 'edit' ? (
        <label htmlFor={`${prefix}-slug`} className="advanced-field">
          Organization link name <span>advanced</span>
          <input id={`${prefix}-slug`} name="slug" defaultValue={organization?.slug ?? ''} maxLength={80} />
        </label>
      ) : null}
      <label htmlFor={`${prefix}-timezone`}>
        {timezoneLabel}
        <input id={`${prefix}-timezone`} name="timezone" defaultValue={organization?.timezone ?? DEFAULT_TIMEZONE} required maxLength={64} />
      </label>
      {mode === 'edit' ? (
        <label htmlFor={`${prefix}-status`}>
          Organization status
          <select id={`${prefix}-status`} name="status" defaultValue={organization?.status ?? 'ACTIVE'}>
            <option value="ACTIVE">ACTIVE</option>
            <option value="INACTIVE">INACTIVE</option>
          </select>
        </label>
      ) : null}
      <button className="button primary" type="submit" disabled={disabled}>{submitLabel}</button>
    </form>
  );
}

function DoctorForm({
  doctor,
  formId,
  submitLabel,
  disabled,
  onSubmit,
}: {
  doctor?: Doctor;
  formId: string;
  submitLabel: string;
  disabled: boolean;
  onSubmit: (body: DoctorInput, form: HTMLFormElement) => void;
}) {
  const initialCapability = doctor?.capabilities[0];

  return (
    <form
      className="doctor-form"
      onSubmit={(event) => {
        event.preventDefault();
        const form = new FormData(event.currentTarget);
        onSubmit(toDoctorInput(form), event.currentTarget);
      }}
    >
      <label htmlFor={`${formId}-first-name`}>
        Doctor first name
        <input id={`${formId}-first-name`} name="first_name" defaultValue={doctor?.first_name ?? ''} required maxLength={100} />
      </label>
      <label htmlFor={`${formId}-last-name`}>
        Doctor last name
        <input id={`${formId}-last-name`} name="last_name" defaultValue={doctor?.last_name ?? ''} required maxLength={100} />
      </label>
      <label htmlFor={`${formId}-new-patients`}>
        New patients
        <select id={`${formId}-new-patients`} name="accepts_new_patients" defaultValue={doctor?.accepts_new_patients === false ? 'false' : 'true'}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      <label htmlFor={`${formId}-active`}>
        Doctor active
        <select id={`${formId}-active`} name="active" defaultValue={doctor?.active === false ? 'false' : 'true'}>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      </label>
      <label htmlFor={`${formId}-body-part`}>
        Capability area
        <select id={`${formId}-body-part`} name="body_part" defaultValue={initialCapability?.body_part ?? ''}>
          {CAPABILITY_AREA_OPTIONS.map((option) => (
            <option key={option.value || 'none'} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
      <label htmlFor={`${formId}-issue-type`}>
        Visit reason / issue type
        <select id={`${formId}-issue-type`} name="issue_type" defaultValue={initialCapability?.issue_type ?? ''}>
          {VISIT_REASON_OPTIONS.map((option) => (
            <option key={option.value || 'none'} value={option.value}>{option.label}</option>
          ))}
        </select>
      </label>
      <button className="button primary" type="submit" disabled={disabled}>{submitLabel}</button>
    </form>
  );
}

function toOrganizationInput(form: FormData, includeStatus = false): OrganizationInput {
  const body: OrganizationInput = {
    name: formValue(form, 'name'),
    timezone: formValue(form, 'timezone') || DEFAULT_TIMEZONE,
  };
  const slug = formValue(form, 'slug');
  if (slug) body.slug = slug;
  if (includeStatus) body.status = formValue(form, 'status') as OrganizationStatus;
  return body;
}

function toDoctorInput(form: FormData): DoctorInput {
  const body: DoctorInput = {
    first_name: formValue(form, 'first_name'),
    last_name: formValue(form, 'last_name'),
    accepts_new_patients: formValue(form, 'accepts_new_patients') === 'true',
    active: formValue(form, 'active') === 'true',
  };
  const bodyPart = formValue(form, 'body_part');
  const issueType = formValue(form, 'issue_type');
  if (bodyPart && issueType) {
    body.capabilities = [{ body_part: bodyPart, issue_type: issueType }];
  }
  return body;
}

function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === 'string' ? value.trim() : '';
}

function organizationType(organization: Organization): string {
  return organization.organization_type?.trim() || 'Medical organization';
}

function doctorInitials(doctor: Doctor): string {
  return `${doctor.first_name[0] ?? ''}${doctor.last_name[0] ?? ''}`.toUpperCase() || 'DR';
}

function formatLocations(doctor: Doctor): string {
  return doctor.locations.map((location) => location.name).join(', ') || 'None';
}

function formatCapabilities(doctor: Doctor): string {
  if (doctor.capabilities.length === 0) return 'None';
  return doctor.capabilities.map((item) => `${item.body_part}, ${item.issue_type}`).join('; ');
}

function doctorMatchesSearch(doctor: Doctor, query: string): boolean {
  return [
    doctor.full_name,
    doctor.first_name,
    doctor.last_name,
    doctor.primary_specialty,
    ...doctor.locations.map((location) => location.name),
    ...doctor.capabilities.map((capability) => `${capability.body_part} ${capability.issue_type}`),
  ]
    .join(' ')
    .toLowerCase()
    .includes(query);
}
