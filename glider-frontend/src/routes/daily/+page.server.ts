import { withDb } from '$lib/server/surrealdb';
import type { CalendarEvent, SpotifyListeningEvent } from '$lib/types/calendar';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ url }) => {
	// Get the day offset from URL params (0 = today)
	const dayOffset = parseInt(url.searchParams.get('day') || '0', 10);

	// Calculate the target day
	const targetDate = new Date();
	targetDate.setDate(targetDate.getDate() + dayOffset);
	targetDate.setHours(0, 0, 0, 0);

	const dayStart = new Date(targetDate);
	const dayEnd = new Date(targetDate);
	dayEnd.setHours(23, 59, 59, 999);

	// Fetch calendar events and Spotify listening history in parallel
	const [events, listeningHistory] = await withDb(async (db) => {
		const eventsResult = await db.query<[CalendarEvent[]]>(
			`SELECT * FROM google_calendar_events
			 WHERE status != 'cancelled'
			 ORDER BY start.dateTime ASC, start.date ASC`
		);

		const listeningResult = await db.query<[SpotifyListeningEvent[]]>(
			`SELECT * FROM spotify_listening_history
			 ORDER BY listened_at ASC`
		);

		return [eventsResult[0] || [], listeningResult[0] || []];
	});

	// Filter events that fall within the day
	const filteredEvents = events
		.filter((event) => {
			const eventStart = getEventDate(event.start);
			const eventEnd = getEventDate(event.end);
			return eventStart < dayEnd && eventEnd > dayStart;
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

	// Filter listening history for the target day
	const filteredListening = listeningHistory
		.filter((event) => {
			const listenedAt = new Date(event.listened_at);
			return listenedAt >= dayStart && listenedAt <= dayEnd;
		})
		.map((event) => ({
			id: String(event.id),
			spotify_track_id: event.spotify_track_id,
			track_name: event.track_name,
			artist_names: event.artist_names || [],
			artist_ids: event.artist_ids || [],
			album_name: event.album_name,
			album_id: event.album_id,
			duration_ms: event.duration_ms,
			listened_at: event.listened_at,
			progress_reached_ms: event.progress_reached_ms,
			percentage_listened: event.percentage_listened,
			explicit: event.explicit,
			popularity: event.popularity
		}));

	return {
		events: filteredEvents,
		listeningHistory: filteredListening,
		targetDate: targetDate.toISOString(),
		dayOffset
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
