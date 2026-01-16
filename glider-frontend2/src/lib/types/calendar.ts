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
