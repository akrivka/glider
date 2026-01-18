<script lang="ts">
	import { outlineStore, type BlockLocation } from '$lib/stores/outlineStore.svelte';
	import { extractTextFromHtml } from '$lib/utils/sanitize';

	let breadcrumbs = $derived(outlineStore.getBreadcrumbs());

	function handleBreadcrumbClick(path: number[]) {
		const focusId = outlineStore.zoomTo(path);
		if (focusId) {
			requestAnimationFrame(() => {
				window.dispatchEvent(
					new CustomEvent('outline-focus', {
						detail: { id: focusId, position: 'start' }
					})
				);
			});
		}
	}

	function getBlockText(location: BlockLocation): string {
		const text = extractTextFromHtml(location.block.content);
		// Truncate if too long
		return text.length > 50 ? text.substring(0, 50) + '...' : text;
	}
</script>

{#if breadcrumbs.length > 0}
	<div class="breadcrumbs mb-4 flex items-center gap-2 text-sm text-gray-500">
		<!-- Root link -->
		<button class="hover:text-gray-700 hover:underline" onclick={() => handleBreadcrumbClick([])}>
			Root
		</button>

		{#each breadcrumbs as location (location.path.join('-'))}
			<span class="text-gray-400">/</span>
			<button
				class="hover:text-gray-700 hover:underline"
				onclick={() => handleBreadcrumbClick(location.path)}
			>
				{getBlockText(location)}
			</button>
		{/each}
	</div>
{/if}
