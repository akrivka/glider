<script lang="ts">
	import Outline from '$lib/components/outline/Outline.svelte';
</script>

<svelte:head>
	<title>Outline Demo | Glider</title>
</svelte:head>

<div class="min-h-screen bg-white">
	<header class="border-b border-gray-200 bg-gray-50 px-6 py-4">
		<div class="mx-auto max-w-3xl">
			<h1 class="text-2xl font-semibold text-gray-900">Outline Demo</h1>
			<p class="mt-1 text-sm text-gray-500">
				A Roam Research / Workflowy-style outliner with rich-text support
			</p>
		</div>
	</header>

	<main class="py-6">
		<Outline />
	</main>

	<footer class="border-t border-gray-200 bg-gray-50 px-6 py-4">
		<div class="mx-auto max-w-3xl text-sm text-gray-500">
			<h2 class="mb-2 font-medium text-gray-700">Keyboard shortcuts:</h2>
			<div class="grid grid-cols-2 gap-x-8 gap-y-1">
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Enter</kbd> - Create new block</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Tab</kbd> - Indent block</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Shift+Tab</kbd> - Unindent block</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Backspace</kbd> - Merge with previous (at start)</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Ctrl+;</kbd> - Toggle collapse</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+.</kbd> - Zoom into block</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+,</kbd> - Zoom out</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+Enter</kbd> - Toggle checkbox</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+B</kbd> - Bold</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+I</kbd> - Italic</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+U</kbd> - Underline</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+Shift+X</kbd> - Strikethrough</div>
				<div><kbd class="rounded bg-gray-200 px-1.5 py-0.5">Cmd+K</kbd> - Insert link</div>
			</div>
		</div>
	</footer>
</div>
