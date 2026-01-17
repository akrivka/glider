export interface CalendarEventTime {
	dateTime?: string;
	date?: string;
	timeZone?: string;
}

export interface CalendarEvent {
	id: string;
	google_id: string;
	calendar_id: string;
	summary: string;
	start: CalendarEventTime;
	end: CalendarEventTime;
	status: string;
	html_link?: string;
	location?: string;
	description?: string;
	created?: string;
	updated?: string;
	_synced_at?: string;
}

export interface WeekDay {
	date: Date;
	dayName: string;
	dayNumber: number;
	isToday: boolean;
}

export interface ProcessedEvent {
	id: string;
	summary: string;
	startTime: Date;
	endTime: Date;
	isAllDay: boolean;
	color: string;
	htmlLink?: string;
	location?: string;
}

export interface SpotifyListeningEvent {
	id: string;
	spotify_track_id: string;
	track_name: string;
	artist_names: string[];
	artist_ids: string[];
	album_name: string;
	album_id: string;
	duration_ms: number;
	listened_at: string;
	progress_reached_ms: number;
	percentage_listened: number;
	explicit: boolean;
	popularity: number;
	_synced_at?: string;
}

export interface ProcessedListeningSegment {
	startTime: Date;
	endTime: Date;
	tracks: {
		trackName: string;
		artistNames: string[];
		albumName: string;
		listenedAt: Date;
		durationMs: number;
		progressReachedMs: number;
	}[];
}
