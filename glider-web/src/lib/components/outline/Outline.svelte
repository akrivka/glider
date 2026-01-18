<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { outlineStore } from '$lib/stores/outlineStore.svelte';
	import Block from './Block.svelte';
	import Breadcrumbs from './Breadcrumbs.svelte';

	let focusRequest = $state<{ id: string; position: 'start' | 'end' | number } | null>(null);

	let visibleBlocks = $derived(outlineStore.getVisibleBlocks());
	let zoomPath = $derived(outlineStore.state.zoomPath);

	function handleFocusEvent(e: Event) {
		const customEvent = e as CustomEvent<{ id: string; position: 'start' | 'end' | number }>;
		focusRequest = customEvent.detail;
	}

	function handleFocusHandled() {
		focusRequest = null;
	}

	onMount(() => {
		window.addEventListener('outline-focus', handleFocusEvent);

		// Focus the first block on mount
		const firstBlock = outlineStore.state.blocks[0];
		if (firstBlock) {
			focusRequest = { id: firstBlock.id, position: 'start' };
		}

		return () => {
			window.removeEventListener('outline-focus', handleFocusEvent);
		};
	});
</script>

<div class="outline-container mx-auto max-w-3xl p-4">
	<Breadcrumbs />
	{#each visibleBlocks as block, index (block.id)}
		<Block
			{block}
			path={[...zoomPath, index]}
			{focusRequest}
			onFocusHandled={handleFocusHandled}
		/>
	{/each}
</div>
