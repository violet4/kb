import type { Event } from './types';

// /api (not http://127.0.0.1:25690) so requests go through Vite's dev
// proxy (see vite.config.ts) and stay same-origin.
const API_BASE = '/api';

export interface EventOccurrence {
  event: Event;
  occurs_at: string;
}

export async function fetchEvents(upcomingOnly: boolean): Promise<Event[]> {
  const response = await fetch(`${API_BASE}/events?upcoming_only=${upcomingOnly}`);
  if (!response.ok) throw new Error(`Failed to load events: ${response.status} ${await response.text()}`);
  return response.json();
}

export async function fetchEventsInRange(start: Date, end: Date): Promise<EventOccurrence[]> {
  const params = new URLSearchParams({ start: start.toISOString(), end: end.toISOString() });
  const response = await fetch(`${API_BASE}/events/range?${params}`);
  if (!response.ok) throw new Error(`Failed to load events: ${response.status} ${await response.text()}`);
  return response.json();
}

export interface NewEvent {
  title: string;
  starts_at: string;
  is_all_day: boolean;
  recurrence: string | null;
  notes: string | null;
}

export async function createEvent(input: NewEvent): Promise<Event> {
  const response = await fetch(`${API_BASE}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!response.ok) throw new Error(`Failed to create event: ${response.status} ${await response.text()}`);
  return response.json();
}
