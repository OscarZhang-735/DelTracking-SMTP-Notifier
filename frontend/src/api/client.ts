export interface Admin {
  id: number
  username: string
  csrf_token?: string | null
}

export interface Recipient {
  id: number
  name: string
  email: string
  enabled: boolean
  tracking_count: number
}

export interface TraceEvent {
  id: number
  time_raw: string
  info: string
}

export interface Tracking {
  id: number
  tracking_number: string
  enabled: boolean
  notes: string | null
  baseline_initialized: boolean
  shipment_id: string | null
  client_reference: string | null
  outer_carrier_code: string | null
  outer_carrier_tracking_number: string | null
  shipment_status: string | null
  localized_status: string
  country: string | null
  postcode: string | null
  parcel_count: number | null
  last_checked_at: string | null
  last_success_at: string | null
  last_error: string | null
  recipients: Recipient[]
  traces: TraceEvent[]
}

export interface TrackingList {
  items: Tracking[]
  total: number
  page: number
  page_size: number
}

export interface RunSummary {
  id: number
  trigger: string
  status: string
  started_at: string
  finished_at: string | null
  total_count: number
  success_count: number
  failure_count: number
  changed_count: number
  error_summary: string | null
}

export interface RunItem {
  id: number
  tracking_item_id: number | null
  tracking_number: string
  status: string
  changed: boolean
  added_event_count: number
  previous_status: string | null
  current_status: string | null
  error: string | null
  checked_at: string
}

export interface Notification {
  id: number
  recipient_email: string
  subject: string
  status: string
  attempt_count: number
  next_attempt_at: string | null
  last_error: string | null
  created_at: string
  sent_at: string | null
}

export interface RunDetail extends RunSummary {
  items: RunItem[]
  notifications: Notification[]
}

export interface RunList {
  items: RunSummary[]
  total: number
  page: number
  page_size: number
}

export interface ScheduleSettings {
  enabled: boolean
  interval_minutes: number
  timezone: string
}

export interface SmtpSettings {
  host: string | null
  port: number | null
  security: 'ssl' | 'starttls' | 'none' | null
  username: string | null
  sender_name: string | null
  sender_email: string | null
  password_configured: boolean
}

export interface QueryResult {
  job_run_id: number
  status: string
  total_count: number
  success_count: number
  failure_count: number
  changed_count: number
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
  }
}

let csrfToken = ''

export function setCsrfToken(token?: string | null) {
  csrfToken = token ?? ''
}

async function ensureCsrfToken(): Promise<string> {
  if (csrfToken) return csrfToken
  const response = await request<{ csrf_token: string }>('/auth/csrf')
  csrfToken = response.csrf_token
  return csrfToken
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: 'same-origin',
    ...options,
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  })
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const payload = (await response.json()) as { detail?: string | Array<{ msg: string }> }
      if (typeof payload.detail === 'string') message = payload.detail
      else if (Array.isArray(payload.detail)) message = payload.detail[0]?.msg ?? message
    } catch {
      // Keep the status-based fallback when the server did not return JSON.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path)
}

export async function apiMutation<T>(
  path: string,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  body?: unknown,
): Promise<T> {
  const token = await ensureCsrfToken()
  return request<T>(path, {
    method,
    headers: { 'X-CSRF-Token': token },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export async function login(username: string, password: string): Promise<Admin> {
  const token = await ensureCsrfToken()
  const admin = await request<Admin>('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
    body: JSON.stringify({ username, password }),
  })
  setCsrfToken(admin.csrf_token)
  return admin
}

export async function logout(): Promise<void> {
  await apiMutation('/auth/logout', 'POST')
  setCsrfToken()
}
