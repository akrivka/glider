import {
	fetchEventsAndListening,
	filterAndSerializeEvents,
	filterAndSerializeListening,
	filterAndSerializeHeartrate
} from '$lib/server/calendar-utils';
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

	// Fetch calendar events, Spotify listening history, and Oura heartrate
	const [events, listeningHistory, heartrateSamples] = await fetchEventsAndListening();

	// Filter and serialize data for the week
	const filteredEvents = filterAndSerializeEvents(events, weekStart, weekEnd);
	const filteredListening = filterAndSerializeListening(listeningHistory, weekStart, weekEnd);
	const filteredHeartrate = filterAndSerializeHeartrate(heartrateSamples, weekStart, weekEnd);

	return {
		events: filteredEvents,
		listeningHistory: filteredListening,
		heartrateSamples: filteredHeartrate,
		weekStart: weekStart.toISOString(),
		weekEnd: weekEnd.toISOString(),
		weekOffset
	};
};
