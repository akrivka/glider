<script lang="ts">
	import type { Block as BlockType } from '$lib/types/outline';
	import { outlineStore, type BlockPath } from '$lib/stores/outlineStore.svelte';
	import { sanitizeHtml, sanitizeUrl } from '$lib/utils/sanitize';
	import Block from './Block.svelte';

	interface Props {
		block: BlockType;
		path: BlockPath;
		focusRequest: { id: string; position: 'start' | 'end' | number } | null;
		onFocusHandled: () => void;
	}

	let { block, path, focusRequest, onFocusHandled }: Props = $props();

	let contentRef: HTMLDivElement | undefined = $state();
	let showLinkModal = $state(false);
	let linkUrl = $state('');

	let hasChildren = $derived(block.children.length > 0);
	let isCollapsed = $derived(block.collapsed);

	// Set initial content on mount
	$effect(() => {
		if (contentRef && block.content !== undefined) {
			// Only set content if the element is not focused (to avoid overwriting user edits)
			if (document.activeElement !== contentRef) {
				contentRef.innerHTML = sanitizeHtml(block.content || '');
			}
		}
	});

	// Handle focus requests
	$effect(() => {
		const req = focusRequest;
		if (req && req.id === block.id && contentRef) {
			// Sync content before focusing (important for split/merge operations)
			const sanitizedContent = sanitizeHtml(block.content || '');
			if (contentRef.innerHTML !== sanitizedContent) {
				contentRef.innerHTML = sanitizedContent;
			}

			contentRef.focus();

			const selection = window.getSelection();
			if (!selection) return;

			try {
				const range = document.createRange();

				if (req.position === 'start') {
					range.setStart(contentRef, 0);
					range.collapse(true);
				} else if (req.position === 'end') {
					// Move to end of content
					if (contentRef.lastChild) {
						const lastNode = contentRef.lastChild;
						if (lastNode.nodeType === Node.TEXT_NODE) {
							range.setStart(lastNode, lastNode.textContent?.length || 0);
						} else {
							range.setStartAfter(lastNode);
						}
					} else {
						range.setStart(contentRef, 0);
					}
					range.collapse(true);
				} else if (typeof req.position === 'number') {
					// Position cursor at specific offset in text content
					const targetOffset = req.position;
					let currentOffset = 0;
					let found = false;

					const walker = document.createTreeWalker(contentRef, NodeFilter.SHOW_TEXT, null);

					let node: Node | null;
					while ((node = walker.nextNode())) {
						const textLength = node.textContent?.length || 0;
						if (currentOffset + textLength >= targetOffset) {
							range.setStart(node, targetOffset - currentOffset);
							range.collapse(true);
							found = true;
							break;
						}
						currentOffset += textLength;
					}

					if (!found) {
						// If we couldn't find the position, go to end
						if (contentRef.lastChild) {
							range.setStartAfter(contentRef.lastChild);
						} else {
							range.setStart(contentRef, 0);
						}
						range.collapse(true);
					}
				}

				selection.removeAllRanges();
				selection.addRange(range);
			} catch (e) {
				console.error('Error setting cursor position:', e);
			}

			onFocusHandled();
		}
	});

	function getCursorPosition(): number {
		const selection = window.getSelection();
		if (!selection || !contentRef) return 0;

		if (selection.rangeCount === 0) return 0;
		const range = selection.getRangeAt(0);

		// Create a range from start of contentRef to cursor
		const preRange = document.createRange();
		preRange.selectNodeContents(contentRef);
		preRange.setEnd(range.startContainer, range.startOffset);

		return preRange.toString().length;
	}

	function getInnerHTML(): string {
		return contentRef?.innerHTML || '';
	}

	function getTextContent(): string {
		return contentRef?.textContent || '';
	}

	function handleInput() {
		const html = getInnerHTML();
		outlineStore.updateBlockContent(block.id, html);
	}

	function applyFormatting(command: string) {
		document.execCommand(command, false);
		contentRef?.focus();
	}

	function insertLink() {
		const selection = window.getSelection();
		if (!selection || selection.rangeCount === 0) return;

		const selectedText = selection.toString();
		if (!selectedText) {
			alert('Please select some text first to create a link.');
			return;
		}

		showLinkModal = true;
	}

	function confirmLink() {
		const url = linkUrl;
		if (!url) return;

		// Validate URL to prevent javascript: and other dangerous protocols
		const safeUrl = sanitizeUrl(url);
		if (!safeUrl) {
			alert('Please enter a valid URL (http://, https://, or mailto:)');
			return;
		}

		document.execCommand('createLink', false, safeUrl);
		showLinkModal = false;
		linkUrl = '';
		contentRef?.focus();

		// Update store with new HTML
		const html = getInnerHTML();
		outlineStore.updateBlockContent(block.id, html);
	}

	function handleKeyDown(e: KeyboardEvent) {
		// Ctrl+;: toggle collapse
		if (e.key === ';' && e.ctrlKey && !e.metaKey && !e.shiftKey) {
			e.preventDefault();
			if (hasChildren) {
				outlineStore.toggleCollapsed(block.id);
			}
			return;
		}

		// Cmd+.: zoom into block
		if (e.key === '.' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
			e.preventDefault();
			const focusId = outlineStore.zoomIn(block.id);
			if (focusId) {
				// Focus will be handled by Outline component after re-render
				requestAnimationFrame(() => {
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: focusId, position: 'start' }
						})
					);
				});
			}
			return;
		}

		// Cmd+,: zoom out
		if (e.key === ',' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
			e.preventDefault();
			const focusId = outlineStore.zoomOut();
			if (focusId) {
				requestAnimationFrame(() => {
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: focusId, position: 'start' }
						})
					);
				});
			}
			return;
		}

		// Cmd+Enter: cycle checkbox state
		if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
			e.preventDefault();
			outlineStore.cycleCheckboxState(block.id);
			return;
		}

		// Bold: Cmd+B
		if (e.key === 'b' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			applyFormatting('bold');
			return;
		}

		// Italic: Cmd+I
		if (e.key === 'i' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			applyFormatting('italic');
			return;
		}

		// Underline: Cmd+U
		if (e.key === 'u' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			applyFormatting('underline');
			return;
		}

		// Strikethrough: Cmd+Shift+X
		if (e.key === 'x' && (e.metaKey || e.ctrlKey) && e.shiftKey) {
			e.preventDefault();
			applyFormatting('strikeThrough');
			return;
		}

		// Link: Cmd+K
		if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
			e.preventDefault();
			insertLink();
			return;
		}

		const cursorPos = getCursorPosition();
		const textContent = getTextContent();

		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();

			// Get HTML before and after cursor
			const selection = window.getSelection();
			if (!selection || !contentRef) return;

			const range = selection.getRangeAt(0);

			// Clone the content
			const beforeRange = document.createRange();
			beforeRange.selectNodeContents(contentRef);
			beforeRange.setEnd(range.startContainer, range.startOffset);

			const afterRange = document.createRange();
			afterRange.selectNodeContents(contentRef);
			afterRange.setStart(range.startContainer, range.startOffset);

			// Create temporary containers to get HTML
			const beforeContainer = document.createElement('div');
			beforeContainer.appendChild(beforeRange.cloneContents());
			const beforeHTML = beforeContainer.innerHTML;

			const afterContainer = document.createElement('div');
			afterContainer.appendChild(afterRange.cloneContents());
			const afterHTML = afterContainer.innerHTML;

			// Update current block with content before cursor
			outlineStore.updateBlockContent(block.id, beforeHTML);
			// Sync the DOM immediately
			if (contentRef) {
				contentRef.innerHTML = beforeHTML;
			}

			// Create new block with content after cursor
			const newId = outlineStore.insertBlockAsSibling(block.id, afterHTML);

			// Dispatch focus request for new block
			window.dispatchEvent(
				new CustomEvent('outline-focus', {
					detail: { id: newId, position: 'start' }
				})
			);
		}

		if (e.key === 'Backspace' && cursorPos === 0 && !e.shiftKey) {
			e.preventDefault();

			if (textContent === '' && hasChildren) {
				// Don't merge if block has children and is empty - just prevent
				return;
			}

			const result = outlineStore.mergeWithPrevious(block.id);
			if (result.focusId) {
				window.dispatchEvent(
					new CustomEvent('outline-focus', {
						detail: { id: result.focusId, position: result.focusOffset }
					})
				);
			}
		}

		if (e.key === 'Tab') {
			e.preventDefault();

			if (e.shiftKey) {
				// Unindent
				outlineStore.unindentBlock(block.id);
			} else {
				// Indent
				outlineStore.indentBlock(block.id);
			}

			// Refocus after DOM updates
			requestAnimationFrame(() => {
				window.dispatchEvent(
					new CustomEvent('outline-focus', {
						detail: { id: block.id, position: cursorPos }
					})
				);
			});
		}

		if (e.key === 'ArrowUp' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
			const selection = window.getSelection();
			if (selection && selection.isCollapsed) {
				e.preventDefault();
				const prevBlock = outlineStore.getPreviousBlock(block.id);
				if (prevBlock) {
					// Try to maintain horizontal position, clamped to the previous block's length
					// Create a temporary div to get text length from HTML content
					const tempDiv = document.createElement('div');
					tempDiv.innerHTML = prevBlock.block.content;
					const prevLength = tempDiv.textContent?.length || 0;
					const targetPos = Math.min(cursorPos, prevLength);
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: prevBlock.block.id, position: targetPos }
						})
					);
				}
			}
		}

		if (e.key === 'ArrowDown' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
			const selection = window.getSelection();
			if (selection && selection.isCollapsed) {
				e.preventDefault();
				const nextBlock = outlineStore.getNextBlock(block.id);
				if (nextBlock) {
					// Try to maintain horizontal position, clamped to the next block's length
					// Create a temporary div to get text length from HTML content
					const tempDiv = document.createElement('div');
					tempDiv.innerHTML = nextBlock.block.content;
					const nextLength = tempDiv.textContent?.length || 0;
					const targetPos = Math.min(cursorPos, nextLength);
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: nextBlock.block.id, position: targetPos }
						})
					);
				}
			}
		}

		if (e.key === 'ArrowLeft' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
			const selection = window.getSelection();
			if (selection && selection.isCollapsed && cursorPos === 0) {
				e.preventDefault();
				const prevBlock = outlineStore.getPreviousBlock(block.id);
				if (prevBlock) {
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: prevBlock.block.id, position: 'end' }
						})
					);
				}
			}
		}

		if (e.key === 'ArrowRight' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
			const selection = window.getSelection();
			if (selection && selection.isCollapsed && cursorPos === textContent.length) {
				e.preventDefault();
				const nextBlock = outlineStore.getNextBlock(block.id);
				if (nextBlock) {
					window.dispatchEvent(
						new CustomEvent('outline-focus', {
							detail: { id: nextBlock.block.id, position: 'start' }
						})
					);
				}
			}
		}
	}

	function handleToggleCollapse(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		outlineStore.toggleCollapsed(block.id);
	}

	function handleCheckboxClick(e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		outlineStore.cycleCheckboxState(block.id);
	}

	function handleLinkKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			confirmLink();
		}
		if (e.key === 'Escape') {
			e.preventDefault();
			showLinkModal = false;
			linkUrl = '';
		}
	}
</script>

<div class="block-container">
	<div class="group flex items-start">
		<!-- Collapse toggle / bullet -->
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="flex h-6 w-5 flex-shrink-0 cursor-pointer select-none items-center justify-center"
			onclick={handleToggleCollapse}
		>
			{#if hasChildren}
				<span
					class="text-sm text-gray-500 transition-transform {isCollapsed ? '' : 'rotate-90'}"
				>
					&#9656;
				</span>
			{:else}
				<span class="h-1.5 w-1.5 rounded-full bg-gray-400"></span>
			{/if}
		</div>

		<!-- Checkbox (if enabled) -->
		{#if block.checkboxState !== 'none'}
			<!-- svelte-ignore a11y_click_events_have_key_events -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				class="mr-2 flex h-4 w-4 flex-shrink-0 cursor-pointer items-center justify-center rounded border-2 border-gray-400 hover:border-gray-600"
				onclick={handleCheckboxClick}
			>
				{#if block.checkboxState === 'checked'}
					<svg
						class="h-3 w-3 text-gray-700"
						viewBox="0 0 12 12"
						fill="none"
						xmlns="http://www.w3.org/2000/svg"
					>
						<path
							d="M2 6L5 9L10 3"
							stroke="currentColor"
							stroke-width="2"
							stroke-linecap="round"
							stroke-linejoin="round"
						/>
					</svg>
				{/if}
			</div>
		{/if}

		<!-- Content -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			bind:this={contentRef}
			contenteditable="true"
			class="min-h-[1.5rem] flex-1 px-1 py-0.5 leading-6 text-gray-900 outline-none"
			oninput={handleInput}
			onkeydown={handleKeyDown}
		></div>
	</div>

	<!-- Link Modal -->
	{#if showLinkModal}
		<!-- svelte-ignore a11y_click_events_have_key_events -->
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
			<div class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
				<h3 class="mb-4 text-lg font-semibold">Insert Link</h3>
				<input
					type="text"
					placeholder="https://example.com"
					class="mb-4 w-full rounded border border-gray-300 px-3 py-2 outline-none focus:border-blue-500"
					bind:value={linkUrl}
					onkeydown={handleLinkKeyDown}
				/>
				<div class="flex justify-end gap-2">
					<button
						class="px-4 py-2 text-gray-600 hover:text-gray-800"
						onclick={() => {
							showLinkModal = false;
							linkUrl = '';
						}}
					>
						Cancel
					</button>
					<button
						class="rounded bg-blue-500 px-4 py-2 text-white hover:bg-blue-600"
						onclick={confirmLink}
					>
						Insert
					</button>
				</div>
			</div>
		</div>
	{/if}

	<!-- Children -->
	{#if hasChildren && !isCollapsed}
		<div class="ml-5">
			{#each block.children as child, index (child.id)}
				<Block
					block={child}
					path={[...path, index]}
					{focusRequest}
					{onFocusHandled}
				/>
			{/each}
		</div>
	{/if}
</div>
