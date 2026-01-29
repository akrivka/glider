import { withDb } from '$lib/server/surrealdb';
import type { CalendarEvent, SpotifyListeningEvent, OuraHeartrateSample, OuraDailyStress } from '$lib/types/calendar';

export function getEventDate(time: { dateTime?: string; date?: string }): Date {
	if (time.dateTime) {
		return new Date(time.dateTime);
	}
	if (time.date) {
		return new Date(time.date + 'T00:00:00');
	}
	return new Date();
}

export async function fetchEventsAndListening(): Promise<[CalendarEvent[], SpotifyListeningEvent[], OuraHeartrateSample[], OuraDailyStress[]]> {
	return await withDb(async (db) => {
		const eventsResult = await db.query<[CalendarEvent[]]>(
			`SELECT * FROM google_calendar_events
			 WHERE status != 'cancelled'
			 ORDER BY start.dateTime ASC, start.date ASC`
		);

		const listeningResult = await db.query<[SpotifyListeningEvent[]]>(
			`SELECT * FROM spotify_listening_history
			 ORDER BY played_at ASC`
		);

		const heartrateResult = await db.query<[OuraHeartrateSample[]]>(
			`SELECT * FROM oura_heartrate
			 ORDER BY timestamp ASC`
		);

		const stressResult = await db.query<[OuraDailyStress[]]>(
			`SELECT * FROM oura_daily_stress
			 ORDER BY day ASC`
		);

		return [
			eventsResult[0] || [],
			listeningResult[0] || [],
			heartrateResult[0] || [],
			stressResult[0] || []
		] as [CalendarEvent[], SpotifyListeningEvent[], OuraHeartrateSample[], OuraDailyStress[]];
	});
}

export function filterAndSerializeEvents(
	events: CalendarEvent[],
	startDate: Date,
	endDate: Date
) {
	return events
		.filter((event) => {
			const eventStart = getEventDate(event.start);
			const eventEnd = getEventDate(event.end);
			return eventStart < endDate && eventEnd > startDate;
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
}

export function filterAndSerializeListening(
	listeningHistory: SpotifyListeningEvent[],
	startDate: Date,
	endDate: Date
) {
	return listeningHistory
		.filter((event) => {
			// Database stores played_at, not listened_at
			const playedAt = (event as unknown as { played_at: string }).played_at;
			if (!playedAt) return false;
			const listenedAt = new Date(playedAt);
			return listenedAt >= startDate && listenedAt <= endDate;
		})
		.map((event) => {
			// Map played_at to listened_at, use duration_ms as progress (assume full track listened)
			const playedAt = (event as unknown as { played_at: string }).played_at;
			const durationMs = event.duration_ms || 0;
			return {
				id: String(event.id),
				spotify_track_id: event.spotify_track_id,
				track_name: event.track_name,
				artist_names: event.artist_names || [],
				artist_ids: event.artist_ids || [],
				album_name: event.album_name,
				album_id: event.album_id,
				duration_ms: durationMs,
				listened_at: playedAt,
				progress_reached_ms: durationMs, // Assume full track was listened
				percentage_listened: 100, // Assume full track was listened
				explicit: event.explicit,
				popularity: event.popularity
			};
		});
}

export function filterAndSerializeHeartrate(
	heartrateSamples: OuraHeartrateSample[],
	startDate: Date,
	endDate: Date
) {
	return heartrateSamples
		.filter((sample) => {
			const timestamp = new Date(sample.timestamp);
			return timestamp >= startDate && timestamp <= endDate;
		})
		.map((sample) => ({
			id: String(sample.id),
			timestamp: sample.timestamp,
			bpm: sample.bpm,
			source: sample.source
		}));
}

export function filterAndSerializeStress(
	stressRecords: OuraDailyStress[],
	startDate: Date,
	endDate: Date
) {
	return stressRecords
		.filter((record) => {
			const day = new Date(record.day + 'T00:00:00');
			return day >= startDate && day <= endDate;
		})
		.map((record) => ({
			id: String(record.id),
			day: record.day,
			stress_high: record.stress_high,
			recovery_high: record.recovery_high,
			day_summary: record.day_summary
		}));
}
