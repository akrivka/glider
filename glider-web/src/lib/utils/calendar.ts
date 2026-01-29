import type { CalendarEvent, ProcessedEvent, SpotifyListeningEvent, ProcessedListeningSegment } from '$lib/types/calendar';

// Constants
export const EVENT_COLORS = [
	'bg-blue-500/90 border-blue-600',
	'bg-emerald-500/90 border-emerald-600',
	'bg-violet-500/90 border-violet-600',
	'bg-amber-500/90 border-amber-600',
	'bg-rose-500/90 border-rose-600',
	'bg-cyan-500/90 border-cyan-600',
	'bg-fuchsia-500/90 border-fuchsia-600'
];

export const GOOGLE_EVENT_COLORS: Record<string, string> = {
	'1': 'bg-indigo-500/90 border-indigo-600', // Lavender
	'2': 'bg-emerald-500/90 border-emerald-600', // Sage
	'3': 'bg-purple-500/90 border-purple-600', // Grape
	'4': 'bg-rose-500/90 border-rose-600', // Flamingo
	'5': 'bg-amber-400/90 border-amber-500', // Banana
	'6': 'bg-orange-500/90 border-orange-600', // Tangerine
	'7': 'bg-sky-500/90 border-sky-600', // Peacock
	'8': 'bg-slate-600/90 border-slate-700', // Graphite
	'9': 'bg-blue-500/90 border-blue-600', // Blueberry
	'10': 'bg-green-600/90 border-green-700', // Basil
	'11': 'bg-red-600/90 border-red-700' // Tomato
};

export const MONTH_NAMES = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

export const SEGMENT_GAP_THRESHOLD = 10; // Gap in minutes to merge listening segments

// Utility functions
export function getEventDate(time: { dateTime?: string; date?: string }): Date {
	if (time.dateTime) {
		return new Date(time.dateTime);
	}
	if (time.date) {
		return new Date(time.date + 'T00:00:00');
	}
	return new Date();
}

export function processEvents(events: CalendarEvent[]): ProcessedEvent[] {
	const recurringColorMap = new Map<string, string>();
	let fallbackIndex = 0;

	for (const event of events) {
		if (!event.recurring_event_id || !event.color_id) continue;
		const googleColor = GOOGLE_EVENT_COLORS[event.color_id];
		if (googleColor) {
			recurringColorMap.set(event.recurring_event_id, googleColor);
		}
	}

	const getFallbackColor = (key: string): string => {
		const existing = recurringColorMap.get(key);
		if (existing) return existing;
		const color = EVENT_COLORS[fallbackIndex % EVENT_COLORS.length];
		fallbackIndex += 1;
		recurringColorMap.set(key, color);
		return color;
	};

	return events.map((event) => {
		const googleColor = event.color_id ? GOOGLE_EVENT_COLORS[event.color_id] : undefined;
		const recurringKey = event.recurring_event_id ?? event.google_id;
		const color = googleColor ?? getFallbackColor(recurringKey);

		return {
			id: event.google_id,
			summary: event.summary || '(No title)',
			startTime: getEventDate(event.start),
			endTime: getEventDate(event.end),
			isAllDay: !event.start.dateTime,
			color,
			htmlLink: event.html_link,
			location: event.location
		};
	});
}

export function processListeningHistory(history: SpotifyListeningEvent[]): ProcessedListeningSegment[] {
	if (history.length === 0) return [];

	const sorted = [...history].sort(
		(a, b) => new Date(a.listened_at).getTime() - new Date(b.listened_at).getTime()
	);

	const segments: ProcessedListeningSegment[] = [];
	let currentSegment: ProcessedListeningSegment | null = null;

	for (const event of sorted) {
		const listenedAt = new Date(event.listened_at);
		const estimatedEndTime = new Date(listenedAt.getTime() + event.progress_reached_ms);

		const track = {
			trackName: event.track_name,
			artistNames: event.artist_names,
			albumName: event.album_name,
			listenedAt: listenedAt,
			durationMs: event.duration_ms,
			progressReachedMs: event.progress_reached_ms
		};

		if (!currentSegment) {
			currentSegment = {
				startTime: listenedAt,
				endTime: estimatedEndTime,
				tracks: [track]
			};
		} else {
			const gapMs = listenedAt.getTime() - currentSegment.endTime.getTime();
			const gapMinutes = gapMs / (1000 * 60);

			if (gapMinutes <= SEGMENT_GAP_THRESHOLD) {
				currentSegment.endTime = estimatedEndTime;
				currentSegment.tracks.push(track);
			} else {
				segments.push(currentSegment);
				currentSegment = {
					startTime: listenedAt,
					endTime: estimatedEndTime,
					tracks: [track]
				};
			}
		}
	}

	if (currentSegment) {
		segments.push(currentSegment);
	}

	return segments;
}

export function formatTime(date: Date): string {
	return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

export function formatDuration(ms: number): string {
	const minutes = Math.floor(ms / 60000);
	const seconds = Math.floor((ms % 60000) / 1000);
	return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}
