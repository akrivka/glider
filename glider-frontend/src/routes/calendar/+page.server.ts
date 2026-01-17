import { withDb } from '$lib/server/surrealdb';
import type { CalendarEvent } from '$lib/types/calendar';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
	// Get the week offset from URL params (0 = current week)
	const weekOffset = parseInt(url.searchParams.get('week') || '0', 10);

	// Calculate the start and end of the target week
	const today = new Date();
	const currentDayOfWeek = today.getDay();
	// Adjust so Monday is the first day of the week (Sunday = 0, so we shift)
	const mondayOffset = currentDayOfWeek === 0 ? -6 : 1 - currentDayOfWeek;

	const weekStart = new Date(today);
	weekStart.setHours(0, 0, 0, 0);
	weekStart.setDate(today.getDate() + mondayOffset + weekOffset * 7);

	const weekEnd = new Date(weekStart);
	weekEnd.setDate(weekStart.getDate() + 7);
	weekEnd.setHours(23, 59, 59, 999);

	const events = await withDb(async (db) => {
		// Query events that overlap with our week
		// Events where start < weekEnd AND end > weekStart
		const result = await db.query<[CalendarEvent[]]>(
			`SELECT * FROM google_calendar_events 
			 WHERE status != 'cancelled'
			 ORDER BY start.dateTime ASC, start.date ASC`
		);

		return result[0] || [];
	});

	// Filter events that fall within the week (SurrealDB query can't easily compare nested date fields)
	// Also convert to plain objects (SurrealDB returns RecordId objects that aren't serializable)
	const filteredEvents = events
		.filter((event) => {
			const eventStart = getEventDate(event.start);
			const eventEnd = getEventDate(event.end);
			return eventStart < weekEnd && eventEnd > weekStart;
		})
		.map((event) => ({
			id: String(event.id),
			google_id: event.google_id,
			calendar_id: event.calendar_id,
			summary: event.summary,
			start: event.start,
			end: event.end,
			status: event.status,
			html_link: event.html_link,
			location: event.location,
			description: event.description,
			created: event.created,
			updated: event.updated
		}));

	return {
		events: filteredEvents,
		weekStart: weekStart.toISOString(),
		weekEnd: weekEnd.toISOString(),
		weekOffset
	};
};

function getEventDate(time: { dateTime?: string; date?: string }): Date {
	if (time.dateTime) {
		return new Date(time.dateTime);
	}
	if (time.date) {
		return new Date(time.date + 'T00:00:00');
	}
	return new Date();
}
