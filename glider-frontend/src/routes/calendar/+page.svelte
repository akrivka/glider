<script lang="ts">
	import type { PageData } from './$types';
	import type { CalendarEvent, ProcessedEvent, WeekDay } from '$lib/types/calendar';

	let { data }: { data: PageData } = $props();

	const HOUR_HEIGHT = 48; // pixels per hour
	const DAY_START_HOUR = 6; // Start at 6 AM
	const DAY_END_HOUR = 22; // End at 10 PM
	const HOURS = Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }, (_, i) => i + DAY_START_HOUR);

	const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
	const MONTH_NAMES = [
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

	// Color palette for events
	const EVENT_COLORS = [
		'bg-blue-500/90 border-blue-600',
		'bg-emerald-500/90 border-emerald-600',
		'bg-violet-500/90 border-violet-600',
		'bg-amber-500/90 border-amber-600',
		'bg-rose-500/90 border-rose-600',
		'bg-cyan-500/90 border-cyan-600',
		'bg-fuchsia-500/90 border-fuchsia-600'
	];

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

	function getEventDate(time: { dateTime?: string; date?: string }): Date {
		if (time.dateTime) {
			return new Date(time.dateTime);
		}
		if (time.date) {
			return new Date(time.date + 'T00:00:00');
		}
		return new Date();
	}

	function processEvents(events: CalendarEvent[]): ProcessedEvent[] {
		return events.map((event, index) => ({
			id: event.google_id,
			summary: event.summary || '(No title)',
			startTime: getEventDate(event.start),
			endTime: getEventDate(event.end),
			isAllDay: !event.start.dateTime,
			color: EVENT_COLORS[index % EVENT_COLORS.length],
			htmlLink: event.html_link,
			location: event.location
		}));
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

	function formatTime(date: Date): string {
		return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
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

	const weekDays = $derived(getWeekDays(data.weekStart));
	const processedEvents = $derived(processEvents(data.events as CalendarEvent[]));
	const allDayEvents = $derived(processedEvents.filter((e) => e.isAllDay));
	const timedEvents = $derived(processedEvents.filter((e) => !e.isAllDay));
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
	<div class="flex flex-1 overflow-hidden">
		<!-- Time Column -->
		<div class="w-16 flex-shrink-0 border-r border-slate-800 bg-slate-900/50">
			<!-- All-day header spacer -->
			{#if allDayEvents.length > 0}
				<div class="h-8 border-b border-slate-800"></div>
			{/if}
			<!-- Day headers spacer -->
			<div class="h-14 border-b border-slate-800"></div>
			<!-- Hour labels -->
			<div class="relative">
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
			{#each weekDays as day, dayIndex}
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

					<!-- Hours grid with events -->
					<div
						class="relative flex-1 overflow-y-auto"
						style="height: {HOURS.length * HOUR_HEIGHT}px"
					>
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
				</div>
			{/each}
		</div>
	</div>
</div>
