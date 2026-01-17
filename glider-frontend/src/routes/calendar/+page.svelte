<script lang="ts">
	import type { PageData } from './$types';
	import type {
		CalendarEvent,
		ProcessedEvent,
		WeekDay,
		SpotifyListeningEvent,
		ProcessedListeningSegment,
		OuraHeartrateSample,
		ProcessedHeartrateSample
	} from '$lib/types/calendar';
	import {
		EVENT_COLORS,
		MONTH_NAMES,
		getEventDate,
		processEvents,
		processListeningHistory,
		formatTime,
		formatDuration
	} from '$lib/utils/calendar';

	let { data }: { data: PageData } = $props();

	const HOUR_HEIGHT = 48; // pixels per hour
	const DAY_START_HOUR = 6; // Start at 6 AM
	const DAY_END_HOUR = 22; // End at 10 PM
	const HOURS = Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }, (_, i) => i + DAY_START_HOUR);

	const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

	// Heart rate range for color gradient (typical resting to active range)
	const MIN_BPM = 50;
	const MAX_BPM = 150;

	let hoveredTrack: {
		track: { trackName: string; artistNames: string[]; albumName: string };
		position: { x: number; y: number };
	} | null = $state(null);
	let selectedSegment: ProcessedListeningSegment | null = $state(null);
	let hoveredHeartrate: {
		bpm: number;
		time: string;
		position: { x: number; y: number };
	} | null = $state(null);

	function getWeekDays(weekStartISO: string): WeekDay[] {
		const weekStart = new Date(weekStartISO);
		const today = new Date();
		today.setHours(0, 0, 0, 0);

		return Array.from({ length: 7 }, (_, i) => {
			const date = new Date(weekStart);
			date.setDate(weekStart.getDate() + i);
			const dateOnly = new Date(date);
			dateOnly.setHours(0, 0, 0, 0);

			return {
				date,
				dayName: DAY_NAMES[i],
				dayNumber: date.getDate(),
				isToday: dateOnly.getTime() === today.getTime()
			};
		});
	}


	function getEventsForDay(events: ProcessedEvent[], day: Date): ProcessedEvent[] {
		const dayStart = new Date(day);
		dayStart.setHours(0, 0, 0, 0);
		const dayEnd = new Date(day);
		dayEnd.setHours(23, 59, 59, 999);

		return events.filter((event) => {
			return event.startTime < dayEnd && event.endTime > dayStart;
		});
	}

	function getEventStyle(event: ProcessedEvent, day: Date): string {
		if (event.isAllDay) {
			return `top: 0; left: 2px; right: 2px; height: 24px;`;
		}

		const dayStart = new Date(day);
		dayStart.setHours(DAY_START_HOUR, 0, 0, 0);

		// Calculate position relative to day start
		let startMinutes = (event.startTime.getTime() - dayStart.getTime()) / (1000 * 60);
		let endMinutes = (event.endTime.getTime() - dayStart.getTime()) / (1000 * 60);

		// Clamp to visible hours
		startMinutes = Math.max(0, startMinutes);
		endMinutes = Math.min((DAY_END_HOUR - DAY_START_HOUR) * 60, endMinutes);

		const top = (startMinutes / 60) * HOUR_HEIGHT;
		const height = Math.max(((endMinutes - startMinutes) / 60) * HOUR_HEIGHT, 20);

		return `top: ${top}px; left: 2px; right: 2px; height: ${height}px;`;
	}

	function formatWeekRange(weekStartISO: string): string {
		const weekStart = new Date(weekStartISO);
		const weekEnd = new Date(weekStart);
		weekEnd.setDate(weekStart.getDate() + 6);

		const startMonth = MONTH_NAMES[weekStart.getMonth()];
		const endMonth = MONTH_NAMES[weekEnd.getMonth()];

		if (startMonth === endMonth) {
			return `${startMonth} ${weekStart.getDate()} - ${weekEnd.getDate()}, ${weekStart.getFullYear()}`;
		}
		return `${startMonth} ${weekStart.getDate()} - ${endMonth} ${weekEnd.getDate()}, ${weekStart.getFullYear()}`;
	}

	function getListeningForDay(
		segments: ProcessedListeningSegment[],
		day: Date
	): ProcessedListeningSegment[] {
		const dayStart = new Date(day);
		dayStart.setHours(0, 0, 0, 0);
		const dayEnd = new Date(day);
		dayEnd.setHours(23, 59, 59, 999);

		return segments.filter((segment) => {
			return segment.startTime < dayEnd && segment.endTime > dayStart;
		});
	}

	function getSegmentStyle(segment: ProcessedListeningSegment, day: Date): string {
		const dayStart = new Date(day);
		dayStart.setHours(DAY_START_HOUR, 0, 0, 0);

		let startMinutes = (segment.startTime.getTime() - dayStart.getTime()) / (1000 * 60);
		let endMinutes = (segment.endTime.getTime() - dayStart.getTime()) / (1000 * 60);

		startMinutes = Math.max(0, startMinutes);
		endMinutes = Math.min((DAY_END_HOUR - DAY_START_HOUR) * 60, endMinutes);

		const top = (startMinutes / 60) * HOUR_HEIGHT;
		const height = Math.max(((endMinutes - startMinutes) / 60) * HOUR_HEIGHT, 16);

		return `top: ${top}px; height: ${height}px;`;
	}

	function getTrackAtPosition(
		segment: ProcessedListeningSegment,
		day: Date,
		mouseY: number,
		elementTop: number
	): { trackName: string; artistNames: string[]; albumName: string } | null {
		const dayStart = new Date(day);
		dayStart.setHours(DAY_START_HOUR, 0, 0, 0);

		const relativeY = mouseY - elementTop;
		const timeAtCursor = dayStart.getTime() + (relativeY / HOUR_HEIGHT) * 60 * 60 * 1000;

		for (const track of segment.tracks) {
			const trackStart = track.listenedAt.getTime();
			const trackEnd = trackStart + track.progressReachedMs;

			if (timeAtCursor >= trackStart && timeAtCursor <= trackEnd) {
				return {
					trackName: track.trackName,
					artistNames: track.artistNames,
					albumName: track.albumName
				};
			}
		}

		return segment.tracks[0] || null;
	}

	function handleSegmentHover(
		event: MouseEvent,
		segment: ProcessedListeningSegment,
		day: Date
	) {
		const target = event.currentTarget as HTMLElement;
		const rect = target.getBoundingClientRect();
		const track = getTrackAtPosition(segment, day, event.clientY, rect.top);

		if (track) {
			hoveredTrack = {
				track,
				position: { x: event.clientX, y: event.clientY }
			};
		}
	}

	function handleSegmentClick(segment: ProcessedListeningSegment) {
		selectedSegment = segment;
	}

	// Process heartrate samples from raw data
	function processHeartrateSamples(samples: OuraHeartrateSample[]): ProcessedHeartrateSample[] {
		return samples.map((sample) => ({
			timestamp: new Date(sample.timestamp),
			bpm: sample.bpm,
			source: sample.source
		}));
	}

	// Get heartrate samples for a specific day
	function getHeartrateForDay(samples: ProcessedHeartrateSample[], day: Date): ProcessedHeartrateSample[] {
		const dayStart = new Date(day);
		dayStart.setHours(0, 0, 0, 0);
		const dayEnd = new Date(day);
		dayEnd.setHours(23, 59, 59, 999);

		return samples.filter((sample) => {
			return sample.timestamp >= dayStart && sample.timestamp <= dayEnd;
		});
	}

	// Get color for BPM value (gradient from light red to dark red)
	function getBpmColor(bpm: number): string {
		// Normalize BPM to 0-1 range
		const normalized = Math.min(1, Math.max(0, (bpm - MIN_BPM) / (MAX_BPM - MIN_BPM)));
		// Create gradient from light red (low BPM) to dark red (high BPM)
		const opacity = 0.3 + normalized * 0.5; // 0.3 to 0.8 opacity
		return `rgba(239, 68, 68, ${opacity})`; // red-500 with variable opacity
	}

	// Get Y position for a timestamp within the day
	function getHeartrateYPosition(timestamp: Date, day: Date): number {
		const dayStart = new Date(day);
		dayStart.setHours(DAY_START_HOUR, 0, 0, 0);

		const minutesFromStart = (timestamp.getTime() - dayStart.getTime()) / (1000 * 60);
		const clampedMinutes = Math.max(0, Math.min((DAY_END_HOUR - DAY_START_HOUR) * 60, minutesFromStart));

		return (clampedMinutes / 60) * HOUR_HEIGHT;
	}

	// Handle heartrate hover
	function handleHeartrateHover(event: MouseEvent, samples: ProcessedHeartrateSample[], day: Date) {
		const target = event.currentTarget as HTMLElement;
		const rect = target.getBoundingClientRect();
		const relativeY = event.clientY - rect.top;

		const dayStart = new Date(day);
		dayStart.setHours(DAY_START_HOUR, 0, 0, 0);

		// Calculate time at cursor position
		const timeAtCursor = new Date(dayStart.getTime() + (relativeY / HOUR_HEIGHT) * 60 * 60 * 1000);

		// Find the closest sample to this time
		let closestSample: ProcessedHeartrateSample | null = null;
		let closestDistance = Infinity;

		for (const sample of samples) {
			const distance = Math.abs(sample.timestamp.getTime() - timeAtCursor.getTime());
			if (distance < closestDistance) {
				closestDistance = distance;
				closestSample = sample;
			}
		}

		// Only show tooltip if within 15 minutes of a sample
		if (closestSample && closestDistance < 15 * 60 * 1000) {
			hoveredHeartrate = {
				bpm: closestSample.bpm,
				time: formatTime(closestSample.timestamp),
				position: { x: event.clientX, y: event.clientY }
			};
		} else {
			hoveredHeartrate = null;
		}
	}

	const weekDays = $derived(getWeekDays(data.weekStart));
	const processedEvents = $derived(processEvents(data.events as CalendarEvent[]));
	const allDayEvents = $derived(processedEvents.filter((e) => e.isAllDay));
	const timedEvents = $derived(processedEvents.filter((e) => !e.isAllDay));
	const listeningSegments = $derived(
		processListeningHistory(data.listeningHistory as SpotifyListeningEvent[])
	);
	const heartrateSamples = $derived(
		processHeartrateSamples((data.heartrateSamples || []) as OuraHeartrateSample[])
	);
</script>

<svelte:head>
	<title>Calendar | Glider</title>
</svelte:head>

<div class="flex h-screen flex-col bg-slate-950 text-slate-100">
	<!-- Header -->
	<header class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
		<div class="flex items-center gap-4">
			<h1 class="text-2xl font-light tracking-wide text-slate-200">
				<span class="font-semibold text-cyan-400">Glider</span> Calendar
			</h1>
		</div>

		<div class="flex items-center gap-3">
			<a
				href="/calendar?week={data.weekOffset - 1}"
				class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
				aria-label="Previous week"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
			</a>

			<a
				href="/calendar?week=0"
				class="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
			>
				Today
			</a>

			<a
				href="/calendar?week={data.weekOffset + 1}"
				class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
				aria-label="Next week"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</a>
		</div>

		<div class="flex items-center gap-4">
			<a
				href="/daily"
				class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
			>
				Daily View
			</a>
			<div class="text-right">
				<p class="text-lg font-medium text-slate-200">{formatWeekRange(data.weekStart)}</p>
				<p class="text-sm text-slate-500">Week view</p>
			</div>
		</div>
	</header>

	<!-- Calendar Grid -->
	<div class="flex flex-1 flex-col overflow-hidden">
		<!-- Fixed header area with all-day events and day names -->
		<div class="flex flex-shrink-0">
			<!-- Time column header spacer -->
			<div class="w-16 flex-shrink-0 border-r border-slate-800 bg-slate-900/50">
				{#if allDayEvents.length > 0}
					<div class="h-8 border-b border-slate-800"></div>
				{/if}
				<div class="h-14 border-b border-slate-800"></div>
			</div>

			<!-- Day headers -->
			<div class="flex flex-1 overflow-x-auto">
				{#each weekDays as day}
					<div class="flex min-w-[120px] flex-1 flex-col border-r border-slate-800/50 last:border-r-0">
						<!-- All-day events row -->
						{#if allDayEvents.length > 0}
							<div class="relative h-8 border-b border-slate-800 bg-slate-900/30">
								{#each getEventsForDay(allDayEvents, day.date) as event}
									<div
										class="absolute inset-x-1 top-1 truncate rounded px-1 text-xs font-medium text-white {event.color}"
										style="height: 22px; line-height: 22px;"
										title={event.summary}
									>
										{event.summary}
									</div>
								{/each}
							</div>
						{/if}

						<!-- Day header -->
						<div
							class="flex h-14 flex-col items-center justify-center border-b border-slate-800 {day.isToday
								? 'bg-cyan-500/10'
								: 'bg-slate-900/30'}"
						>
							<span class="text-xs font-medium uppercase tracking-wider text-slate-500">
								{day.dayName}
							</span>
							<span
								class="mt-0.5 flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold {day.isToday
									? 'bg-cyan-500 text-white'
									: 'text-slate-200'}"
							>
								{day.dayNumber}
							</span>
						</div>
					</div>
				{/each}
			</div>
		</div>

		<!-- Scrollable area with time labels and day columns -->
		<div class="flex flex-1 overflow-y-auto">
			<!-- Time Column -->
			<div class="w-16 flex-shrink-0 border-r border-slate-800 bg-slate-900/50">
				<div class="relative" style="height: {HOURS.length * HOUR_HEIGHT}px">
					{#each HOURS as hour}
						<div class="relative flex items-start justify-end pr-2" style="height: {HOUR_HEIGHT}px">
							<span class="relative -top-2 text-xs text-slate-500">
								{hour.toString().padStart(2, '0')}:00
							</span>
						</div>
					{/each}
				</div>
			</div>

			<!-- Days Grid -->
			<div class="flex flex-1 overflow-x-auto">
				{#each weekDays as day}
					<div class="flex min-w-[140px] flex-1 border-r border-slate-800/50 last:border-r-0">
						<!-- Calendar Events Column -->
						<div class="relative flex-1" style="height: {HOURS.length * HOUR_HEIGHT}px">
							<!-- Hour lines -->
							{#each HOURS as hour, hourIndex}
								<div
									class="absolute left-0 right-0 border-t border-slate-800/50 {hourIndex === 0
										? 'border-transparent'
										: ''}"
									style="top: {hourIndex * HOUR_HEIGHT}px; height: {HOUR_HEIGHT}px;"
								></div>
							{/each}

							<!-- Events -->
							{#each getEventsForDay(timedEvents, day.date) as event}
								<div
									class="absolute overflow-hidden rounded-md border-l-2 text-xs shadow-lg transition-transform hover:scale-[1.02] {event.color}"
									style={getEventStyle(event, day.date)}
									title="{event.summary}{event.location ? ` • ${event.location}` : ''}"
								>
									<div class="flex h-full flex-col p-1.5">
										<span class="truncate font-medium text-white">{event.summary}</span>
										<span class="text-white/70">
											{formatTime(event.startTime)} - {formatTime(event.endTime)}
										</span>
										{#if event.location}
											<span class="mt-0.5 truncate text-white/60">{event.location}</span>
										{/if}
									</div>
								</div>
							{/each}

							<!-- Current time indicator -->
							{#if day.isToday}
								{@const now = new Date()}
								{@const nowMinutes =
									(now.getHours() - DAY_START_HOUR) * 60 + now.getMinutes()}
								{#if nowMinutes >= 0 && nowMinutes < (DAY_END_HOUR - DAY_START_HOUR) * 60}
									<div
										class="absolute left-0 right-0 z-10 flex items-center"
										style="top: {(nowMinutes / 60) * HOUR_HEIGHT}px"
									>
										<div class="h-2.5 w-2.5 rounded-full bg-red-500"></div>
										<div class="h-0.5 flex-1 bg-red-500"></div>
									</div>
								{/if}
							{/if}
						</div>

						<!-- Spotify Column -->
						<div
							class="relative w-8 flex-shrink-0 border-l border-slate-800/30 bg-slate-900/20"
							style="height: {HOURS.length * HOUR_HEIGHT}px"
						>
							<!-- Spotify logo at top -->
							<div class="absolute top-0 left-0 right-0 flex justify-center pt-1">
								<svg class="h-3 w-3 text-green-500/60" viewBox="0 0 24 24" fill="currentColor">
									<path
										d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"
									/>
								</svg>
							</div>

							<!-- Listening segments -->
							{#each getListeningForDay(listeningSegments, day.date) as segment}
								<div
									class="absolute left-0.5 right-0.5 cursor-pointer rounded-sm bg-green-600/40 border-l-2 border-green-500/60 transition-all hover:bg-green-600/60 hover:border-green-400"
									style={getSegmentStyle(segment, day.date)}
									onmousemove={(e) => handleSegmentHover(e, segment, day.date)}
									onmouseleave={() => (hoveredTrack = null)}
									onclick={() => handleSegmentClick(segment)}
									role="button"
									tabindex="0"
								></div>
							{/each}
						</div>

						<!-- Oura Heartrate Column -->
						{#if true}
							{@const dayHeartrate = getHeartrateForDay(heartrateSamples, day.date)}
							<div
								class="relative w-8 flex-shrink-0 border-l border-slate-800/30 bg-slate-900/20"
								style="height: {HOURS.length * HOUR_HEIGHT}px"
								onmousemove={(e) => handleHeartrateHover(e, dayHeartrate, day.date)}
								onmouseleave={() => (hoveredHeartrate = null)}
								role="img"
								aria-label="Heart rate data"
							>
								<!-- Heart icon at top -->
								<div class="absolute top-0 left-0 right-0 flex justify-center pt-1">
									<svg class="h-3 w-3 text-red-500/60" viewBox="0 0 24 24" fill="currentColor">
										<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
									</svg>
								</div>

								<!-- Heartrate samples as continuous line visualization -->
								{#if dayHeartrate.length > 0}
									<svg
										class="absolute inset-0 overflow-visible"
										style="top: 0; left: 0; width: 100%; height: 100%;"
										preserveAspectRatio="none"
									>
										<!-- Draw vertical bars for each sample -->
										{#each dayHeartrate as sample, i}
											{@const y = getHeartrateYPosition(sample.timestamp, day.date)}
											{@const nextSample = dayHeartrate[i + 1]}
											{@const nextY = nextSample ? getHeartrateYPosition(nextSample.timestamp, day.date) : y + 2}
											{@const height = Math.max(2, nextY - y)}
											<rect
												x="2"
												y={y}
												width="28"
												height={height}
												fill={getBpmColor(sample.bpm)}
											/>
										{/each}
									</svg>
								{/if}
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>

<!-- Hover tooltip for track info -->
{#if hoveredTrack}
	<div
		class="pointer-events-none fixed z-50 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 shadow-xl"
		style="left: {hoveredTrack.position.x + 12}px; top: {hoveredTrack.position.y - 10}px;"
	>
		<div class="flex items-center gap-1.5">
			<svg class="h-3 w-3 text-green-500" viewBox="0 0 24 24" fill="currentColor">
				<path
					d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"
				/>
			</svg>
			<div>
				<div class="max-w-xs truncate text-xs font-medium text-slate-200">
					{hoveredTrack.track.trackName}
				</div>
				<div class="max-w-xs truncate text-xs text-slate-400">
					{hoveredTrack.track.artistNames.join(', ')}
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Hover tooltip for heartrate info -->
{#if hoveredHeartrate}
	<div
		class="pointer-events-none fixed z-50 rounded-md border border-slate-700 bg-slate-900 px-2 py-1.5 shadow-xl"
		style="left: {hoveredHeartrate.position.x + 12}px; top: {hoveredHeartrate.position.y - 10}px;"
	>
		<div class="flex items-center gap-1.5">
			<svg class="h-3 w-3 text-red-500" viewBox="0 0 24 24" fill="currentColor">
				<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
			</svg>
			<div>
				<div class="text-xs font-medium text-slate-200">
					{hoveredHeartrate.bpm} BPM
				</div>
				<div class="text-xs text-slate-400">
					{hoveredHeartrate.time}
				</div>
			</div>
		</div>
	</div>
{/if}

<!-- Click popup for full segment details -->
{#if selectedSegment}
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
		onclick={() => (selectedSegment = null)}
		role="button"
		tabindex="0"
	>
		<div
			class="max-h-[80vh] w-full max-w-md overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-2xl"
			onclick={(e) => e.stopPropagation()}
			role="dialog"
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-slate-700 bg-slate-800/50 px-4 py-3">
				<div class="flex items-center gap-2">
					<svg class="h-5 w-5 text-green-500" viewBox="0 0 24 24" fill="currentColor">
						<path
							d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"
						/>
					</svg>
					<div>
						<h3 class="text-sm font-semibold text-slate-200">Listening Session</h3>
						<p class="text-xs text-slate-400">
							{formatTime(selectedSegment.startTime)} - {formatTime(selectedSegment.endTime)}
						</p>
					</div>
				</div>
				<button
					class="text-slate-400 transition-colors hover:text-slate-200"
					onclick={() => (selectedSegment = null)}
					aria-label="Close"
				>
					<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M6 18L18 6M6 6l12 12"
						/>
					</svg>
				</button>
			</div>

			<!-- Track list -->
			<div class="max-h-96 space-y-2 overflow-y-auto p-4">
				{#each selectedSegment.tracks as track, index}
					<div class="rounded-lg bg-slate-800/50 p-3 transition-colors hover:bg-slate-800">
						<div class="flex items-start justify-between gap-2">
							<div class="min-w-0 flex-1">
								<div class="font-medium text-slate-200">{track.trackName}</div>
								<div class="mt-0.5 text-sm text-slate-400">
									{track.artistNames.join(', ')}
								</div>
								<div class="mt-1 text-xs text-slate-500">{track.albumName}</div>
							</div>
							<div class="flex-shrink-0 text-right">
								<div class="text-xs text-slate-400">
									{formatTime(track.listenedAt)}
								</div>
								<div class="mt-0.5 text-xs text-slate-500">
									{formatDuration(track.progressReachedMs)}
								</div>
							</div>
						</div>
					</div>
				{/each}
			</div>

			<!-- Footer -->
			<div class="border-t border-slate-700 bg-slate-800/30 px-4 py-3">
				<div class="flex items-center justify-between text-xs text-slate-400">
					<span>{selectedSegment.tracks.length} track{selectedSegment.tracks.length !== 1 ? 's' : ''}</span>
					<span>
						{formatDuration(
							selectedSegment.endTime.getTime() - selectedSegment.startTime.getTime()
						)} total
					</span>
				</div>
			</div>
		</div>
	</div>
{/if}
