import {
	fetchEventsAndListening,
	filterAndSerializeEvents,
	filterAndSerializeListening
} from '$lib/server/calendar-utils';
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
	const [events, listeningHistory] = await fetchEventsAndListening();

	// Filter and serialize data for the day
	const filteredEvents = filterAndSerializeEvents(events, dayStart, dayEnd);
	const filteredListening = filterAndSerializeListening(listeningHistory, dayStart, dayEnd);

	return {
		events: filteredEvents,
		listeningHistory: filteredListening,
		targetDate: targetDate.toISOString(),
		dayOffset
	};
};
