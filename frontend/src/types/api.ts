export type CallStatus = 'SCHEDULED' | 'REDIRECTED' | 'ABANDONED' | 'FAILED' | 'IN_PROGRESS';

export interface Location {
  id: number;
  code: string;
  name: string;
}

export interface Capability {
  body_part: string;
  issue_type: string;
}

export interface Doctor {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  accepts_new_patients: boolean;
  active: boolean;
  locations: Location[];
  capabilities: Capability[];
}

export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  date_of_birth: string;
  phone: string;
  email: string | null;
}

export interface Slot {
  id: number;
  starts_at: string;
  ends_at: string;
  status: string;
  location: Location;
}

export interface Appointment {
  id: number;
  patient: Patient;
  doctor: Doctor;
  location: Location;
  slot: Slot;
  body_part: string;
  issue_type: string;
  status: string;
  booking_source: string;
  call_id: number | null;
  created_at: string;
}

export interface BookingConfirmation {
  id: number;
  confirmation_token: string;
  call_id: number;
  patient_id: number;
  slot_id: number;
  doctor: Doctor;
  location: Location;
  body_part: string;
  issue_type: string;
  starts_at: string;
  ends_at: string;
  status: string;
  source: string;
  confirmed_at: string;
  expires_at: string;
  used_at: string | null;
  appointment_id: number | null;
}

export interface TranscriptTurn {
  id: number;
  sequence_number: number;
  speaker: 'AI' | 'HUMAN';
  text: string;
  occurred_at: string;
}

export interface RoutingDecision {
  id: number;
  call_id: number | null;
  patient_id: number | null;
  doctor: Doctor | null;
  decision: 'ACCEPTED' | 'REJECTED';
  reason_code: string;
  human_readable_reason: string;
  request_context: Record<string, unknown>;
  created_at: string;
}

export interface Call {
  id: number;
  external_call_id: string | null;
  status: CallStatus;
  caller_phone: string;
  patient_status: 'NEW' | 'RETURNING' | null;
  requested_body_part: string | null;
  requested_issue_type: string | null;
  started_at: string;
  ended_at: string | null;
  patient: Patient | null;
  preferred_doctor: Doctor | null;
  preferred_location: Location | null;
  appointment: Appointment | null;
  failure_reason: string | null;
  redirect_summary: string | null;
  transcript?: TranscriptTurn[];
  routing_decisions?: RoutingDecision[];
}

export interface OverviewResponse {
  metrics: {
    total_calls: number;
    scheduled: number;
    redirected: number;
    abandoned: number;
    failed: number;
    in_progress: number;
    conversion_rate: number;
  };
  outcomes: { status: CallStatus; count: number }[];
  recent_calls: Call[];
  upcoming_appointments: Appointment[];
  routing_exceptions: RoutingDecision[];
  integration_statuses: IntegrationStatus[];
}

export interface IntegrationStatus {
  id: string;
  label: string;
  state: string;
  status_label: string;
  detail: string;
  checked_at: string;
  last_success_at: string | null;
  metadata: Record<string, unknown>;
}

export interface RoutingDoctorResult {
  doctor: Doctor;
  available_slots: Slot[];
  is_preferred_doctor: boolean;
  preferred_location_match: boolean | null;
  has_patient_history?: boolean;
}

export interface RoutingResponse {
  caller_safe_summary: string;
  fallback_explanation: string | null;
  eligible_doctors: RoutingDoctorResult[];
  rejected_doctors: Array<{
    doctor: Doctor;
    reason_code: string;
    reason: string;
    is_preferred_doctor: boolean;
  }>;
  availability_exceptions: Array<{ doctor: Doctor; reason_code: string; reason: string }>;
  ranked_recommendations: RoutingDoctorResult[];
  recommended: RoutingDoctorResult | null;
  normalized_request: Record<string, unknown>;
}

export interface ProtocolResponse {
  doctors: Doctor[];
  locations: Location[];
  body_parts: string[];
  issue_types: string[];
}
