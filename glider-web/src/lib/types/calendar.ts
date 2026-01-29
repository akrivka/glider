export interface CalendarEventTime {
	dateTime?: string;
	date?: string;
	timeZone?: string;
}

export interface CalendarEvent {
	id: string;
	google_id: string;
	calendar_id: string;
	recurring_event_id?: string;
	color_id?: string;
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

export interface OuraHeartrateSample {
	id: string;
	timestamp: string;
	bpm: number;
	source: string;
	_synced_at?: string;
}

export interface ProcessedHeartrateSample {
	timestamp: Date;
	bpm: number;
	source: string;
}

// Oura Daily Stress
export interface OuraDailyStress {
	id: string;
	day: string;
	stress_high: number | null;
	recovery_high: number | null;
	day_summary: string | null;
	_synced_at?: string;
}

// Oura Daily Activity
export interface OuraDailyActivity {
	id: string;
	day: string;
	score: number | null;
	active_calories: number | null;
	steps: number | null;
	total_calories: number | null;
	target_calories: number | null;
	equivalent_walking_distance: number | null;
	high_activity_time: number | null;
	medium_activity_time: number | null;
	low_activity_time: number | null;
	sedentary_time: number | null;
	resting_time: number | null;
	_synced_at?: string;
}

// Oura Daily Readiness
export interface OuraDailyReadiness {
	id: string;
	day: string;
	score: number | null;
	temperature_deviation: number | null;
	temperature_trend_deviation: number | null;
	contributors: {
		activity_balance: number | null;
		body_temperature: number | null;
		hrv_balance: number | null;
		previous_day_activity: number | null;
		previous_night: number | null;
		recovery_index: number | null;
		resting_heart_rate: number | null;
		sleep_balance: number | null;
	} | null;
	_synced_at?: string;
}

// Oura Daily Sleep
export interface OuraDailySleep {
	id: string;
	day: string;
	score: number | null;
	contributors: {
		deep_sleep: number | null;
		efficiency: number | null;
		latency: number | null;
		rem_sleep: number | null;
		restfulness: number | null;
		timing: number | null;
		total_sleep: number | null;
	} | null;
	_synced_at?: string;
}

// Oura Daily SpO2
export interface OuraDailySpo2 {
	id: string;
	day: string;
	spo2_percentage: {
		average: number | null;
	} | null;
	_synced_at?: string;
}

// Oura Sleep Period (detailed)
export interface OuraSleepPeriod {
	id: string;
	day: string;
	bedtime_start: string | null;
	bedtime_end: string | null;
	average_breath: number | null;
	average_heart_rate: number | null;
	average_hrv: number | null;
	lowest_heart_rate: number | null;
	total_sleep_duration: number | null;
	deep_sleep_duration: number | null;
	light_sleep_duration: number | null;
	rem_sleep_duration: number | null;
	awake_time: number | null;
	efficiency: number | null;
	latency: number | null;
	type: string | null;
	_synced_at?: string;
}

// Oura Workout
export interface OuraWorkout {
	id: string;
	day: string;
	activity: string | null;
	calories: number | null;
	distance: number | null;
	start_datetime: string | null;
	end_datetime: string | null;
	intensity: string | null;
	label: string | null;
	source: string | null;
	_synced_at?: string;
}

// Oura Session (meditation, breathing)
export interface OuraSession {
	id: string;
	day: string;
	start_datetime: string | null;
	end_datetime: string | null;
	type: string | null;
	mood: string | null;
	_synced_at?: string;
}
