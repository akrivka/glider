<script lang="ts">
	import type { PageData } from './$types';
	import type {
		CalendarEvent,
		ProcessedEvent,
		SpotifyListeningEvent,
		ProcessedListeningSegment
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

	const HOUR_HEIGHT = 60; // pixels per hour (slightly larger for daily view)
	const DAY_START_HOUR = 6; // Start at 6 AM
	const DAY_END_HOUR = 24; // End at midnight
	const HOURS = Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }, (_, i) => i + DAY_START_HOUR);

	const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

	let hoveredSegment: ProcessedListeningSegment | null = $state(null);
	let tooltipPosition = $state({ x: 0, y: 0 });

	function getEventStyle(event: ProcessedEvent, dayStart: Date): string {
		if (event.isAllDay) {
			return `top: 0; left: 0; right: 0; height: 28px;`;
		}

		const dayStartTime = new Date(dayStart);
		dayStartTime.setHours(DAY_START_HOUR, 0, 0, 0);

		// Calculate position relative to day start
		let startMinutes = (event.startTime.getTime() - dayStartTime.getTime()) / (1000 * 60);
		let endMinutes = (event.endTime.getTime() - dayStartTime.getTime()) / (1000 * 60);

		// Clamp to visible hours
		startMinutes = Math.max(0, startMinutes);
		endMinutes = Math.min((DAY_END_HOUR - DAY_START_HOUR) * 60, endMinutes);

		const top = (startMinutes / 60) * HOUR_HEIGHT;
		const height = Math.max(((endMinutes - startMinutes) / 60) * HOUR_HEIGHT, 24);

		return `top: ${top}px; left: 0; right: 0; height: ${height}px;`;
	}

	function getSegmentStyle(segment: ProcessedListeningSegment, dayStart: Date): string {
		const dayStartTime = new Date(dayStart);
		dayStartTime.setHours(DAY_START_HOUR, 0, 0, 0);

		let startMinutes = (segment.startTime.getTime() - dayStartTime.getTime()) / (1000 * 60);
		let endMinutes = (segment.endTime.getTime() - dayStartTime.getTime()) / (1000 * 60);

		// Clamp to visible hours
		startMinutes = Math.max(0, startMinutes);
		endMinutes = Math.min((DAY_END_HOUR - DAY_START_HOUR) * 60, endMinutes);

		const top = (startMinutes / 60) * HOUR_HEIGHT;
		const height = Math.max(((endMinutes - startMinutes) / 60) * HOUR_HEIGHT, 16);

		return `top: ${top}px; height: ${height}px;`;
	}

	function formatDateHeader(dateISO: string): string {
		const date = new Date(dateISO);
		const dayName = DAY_NAMES[date.getDay()];
		const monthName = MONTH_NAMES[date.getMonth()];
		return `${dayName}, ${monthName} ${date.getDate()}, ${date.getFullYear()}`;
	}

	function isToday(dateISO: string): boolean {
		const date = new Date(dateISO);
		const today = new Date();
		return (
			date.getDate() === today.getDate() &&
			date.getMonth() === today.getMonth() &&
			date.getFullYear() === today.getFullYear()
		);
	}

	function handleSegmentEnter(event: MouseEvent, segment: ProcessedListeningSegment) {
		hoveredSegment = segment;
		tooltipPosition = { x: event.clientX, y: event.clientY };
	}

	function handleSegmentLeave() {
		hoveredSegment = null;
	}

	const targetDate = $derived(new Date(data.targetDate));
	const processedEvents = $derived(processEvents(data.events as CalendarEvent[]));
	const allDayEvents = $derived(processedEvents.filter((e) => e.isAllDay));
	const timedEvents = $derived(processedEvents.filter((e) => !e.isAllDay));
	const listeningSegments = $derived(
		processListeningHistory(data.listeningHistory as SpotifyListeningEvent[])
	);
</script>

<svelte:head>
	<title>Daily View | Glider</title>
</svelte:head>

<div class="flex h-screen flex-col bg-slate-950 text-slate-100">
	<!-- Header -->
	<header class="flex items-center justify-between border-b border-slate-800 px-6 py-4">
		<div class="flex items-center gap-4">
			<h1 class="text-2xl font-light tracking-wide text-slate-200">
				<span class="font-semibold text-cyan-400">Glider</span> Daily
			</h1>
		</div>

		<div class="flex items-center gap-3">
			<a
				href="/daily?day={data.dayOffset - 1}"
				class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
				aria-label="Previous day"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
				</svg>
			</a>

			<a
				href="/daily?day=0"
				class="rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-medium text-slate-300 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
			>
				Today
			</a>

			<a
				href="/daily?day={data.dayOffset + 1}"
				class="flex h-10 w-10 items-center justify-center rounded-lg border border-slate-700 bg-slate-900 text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
				aria-label="Next day"
			>
				<svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</a>
		</div>

		<div class="flex items-center gap-4">
			<a
				href="/calendar"
				class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-400 transition-all hover:border-cyan-500/50 hover:bg-slate-800 hover:text-cyan-400"
			>
				Week View
			</a>
			<div class="text-right">
				<p class="text-lg font-medium text-slate-200">{formatDateHeader(data.targetDate)}</p>
				<p class="text-sm text-slate-500">
					{#if isToday(data.targetDate)}
						Today
					{:else}
						Daily view
					{/if}
				</p>
			</div>
		</div>
	</header>

	<!-- Main Content - Centered fixed width -->
	<div class="flex flex-1 justify-center overflow-hidden">
		<div class="flex w-full max-w-lg flex-col">
			<!-- All-day events row -->
			{#if allDayEvents.length > 0}
				<div class="flex border-b border-slate-800">
					<div class="w-14 flex-shrink-0"></div>
					<div class="relative h-10 flex-1 bg-slate-900/30 px-2">
						<span class="text-xs text-slate-500">All day</span>
						{#each allDayEvents as event}
							<div
								class="absolute inset-x-2 top-4 truncate rounded px-2 text-xs font-medium text-white {event.color}"
								style="height: 22px; line-height: 22px;"
								title={event.summary}
							>
								{event.summary}
							</div>
						{/each}
					</div>
					<div class="w-20 flex-shrink-0"></div>
				</div>
			{/if}

			<!-- Column headers -->
			<div class="flex border-b border-slate-800">
				<div class="w-14 flex-shrink-0"></div>
				<div class="flex-1 px-2 py-1">
					<span class="text-xs font-medium text-slate-500">Calendar</span>
				</div>
				<div class="w-20 flex-shrink-0 border-l border-slate-800/50 px-2 py-1">
					<div class="flex items-center gap-1">
						<svg class="h-3 w-3 text-green-500" viewBox="0 0 24 24" fill="currentColor">
							<path
								d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"
							/>
						</svg>
						<span class="text-xs font-medium text-slate-500">Music</span>
					</div>
				</div>
			</div>

			<!-- Scrollable content - single scroll container for both columns -->
			<div class="flex-1 overflow-y-auto">
				<div class="flex" style="height: {HOURS.length * HOUR_HEIGHT}px">
					<!-- Time Column -->
					<div class="w-14 flex-shrink-0 border-r border-slate-800 bg-slate-900/50">
						{#each HOURS as hour}
							<div class="relative flex items-start justify-end pr-2" style="height: {HOUR_HEIGHT}px">
								<span class="relative -top-2 text-xs text-slate-500">
									{hour.toString().padStart(2, '0')}:00
								</span>
							</div>
						{/each}
					</div>

					<!-- Calendar Events Column -->
					<div class="relative flex-1">
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
						<div class="absolute inset-0 px-2">
							{#each timedEvents as event}
								<div
									class="absolute overflow-hidden rounded-md border-l-2 text-sm shadow-lg transition-transform hover:scale-[1.01] {event.color}"
									style={getEventStyle(event, targetDate)}
									title="{event.summary}{event.location ? ` \u2022 ${event.location}` : ''}"
								>
									<div class="flex h-full flex-col p-2">
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
						</div>

						<!-- Current time indicator -->
						{#if isToday(data.targetDate)}
							{@const now = new Date()}
							{@const nowMinutes = (now.getHours() - DAY_START_HOUR) * 60 + now.getMinutes()}
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

					<!-- Spotify Listening Column -->
					<div class="relative w-20 flex-shrink-0 border-l border-slate-800/50 bg-slate-900/20">
						<!-- Hour lines (faint, to connect with calendar) -->
						{#each HOURS as hour, hourIndex}
							<div
								class="absolute left-0 right-0 border-t border-slate-800/30 {hourIndex === 0
									? 'border-transparent'
									: ''}"
								style="top: {hourIndex * HOUR_HEIGHT}px; height: {HOUR_HEIGHT}px;"
							></div>
						{/each}

						<!-- Listening segments -->
						{#each listeningSegments as segment}
							<div
								class="absolute left-1 right-1 cursor-pointer rounded bg-green-600/30 border border-green-500/40 transition-all hover:bg-green-600/50 hover:border-green-500/60"
								style={getSegmentStyle(segment, targetDate)}
								onmouseenter={(e) => handleSegmentEnter(e, segment)}
								onmouseleave={handleSegmentLeave}
								role="button"
								tabindex="0"
							>
								<div class="p-1 text-xs text-green-200 truncate">
									{segment.tracks.length}
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>
		</div>
	</div>
</div>

<!-- Tooltip for hovering over segments -->
{#if hoveredSegment}
	<div
		class="fixed z-50 max-w-sm rounded-lg border border-slate-700 bg-slate-900 p-3 shadow-xl"
		style="left: {tooltipPosition.x + 16}px; top: {tooltipPosition.y - 10}px;"
	>
		<div class="mb-2 flex items-center gap-2 border-b border-slate-700 pb-2">
			<svg class="h-4 w-4 text-green-500" viewBox="0 0 24 24" fill="currentColor">
				<path
					d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"
				/>
			</svg>
			<span class="text-sm font-medium text-slate-200">
				{formatTime(hoveredSegment.startTime)} - {formatTime(hoveredSegment.endTime)}
			</span>
		</div>
		<div class="max-h-64 space-y-2 overflow-y-auto">
			{#each hoveredSegment.tracks as track}
				<div class="rounded bg-slate-800/50 p-2">
					<div class="font-medium text-slate-200 text-sm truncate">{track.trackName}</div>
					<div class="text-xs text-slate-400 truncate">{track.artistNames.join(', ')}</div>
					<div class="mt-1 flex items-center gap-2 text-xs text-slate-500">
						<span>{track.albumName}</span>
						<span class="text-slate-600">|</span>
						<span>{formatDuration(track.progressReachedMs)}</span>
					</div>
				</div>
			{/each}
		</div>
	</div>
{/if}
