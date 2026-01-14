import { Component, For, Show, createEffect, onMount, createSignal } from 'solid-js';
import { Block as BlockType } from '../types/outline';
import { outlineStore, BlockPath } from '../store/outlineStore';

interface BlockProps {
  block: BlockType;
  path: BlockPath;
  focusRequest: { id: string; position: 'start' | 'end' | number } | null;
  onFocusHandled: () => void;
}

export const Block: Component<BlockProps> = (props) => {
  let contentRef: HTMLDivElement | undefined;
  const [showLinkModal, setShowLinkModal] = createSignal(false);
  const [linkUrl, setLinkUrl] = createSignal('');

  const hasChildren = () => props.block.children.length > 0;
  const isCollapsed = () => props.block.collapsed;
  const depth = () => props.path.length - 1;

  // Set initial content on mount
  onMount(() => {
    if (contentRef) {
      contentRef.innerHTML = props.block.content || '';
    }
  });

  // Sync content from store when it changes externally (e.g., after merge)
  createEffect(() => {
    const content = props.block.content;
    if (contentRef && document.activeElement !== contentRef) {
      contentRef.innerHTML = content || '';
    }
  });

  // Handle focus requests
  createEffect(() => {
    const req = props.focusRequest;
    if (req && req.id === props.block.id && contentRef) {
      // Sync content before focusing (important for split/merge operations)
      if (contentRef.innerHTML !== props.block.content) {
        contentRef.innerHTML = props.block.content || '';
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

          const walker = document.createTreeWalker(
            contentRef,
            NodeFilter.SHOW_TEXT,
            null
          );

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

      props.onFocusHandled();
    }
  });

  const getCursorPosition = (): number => {
    const selection = window.getSelection();
    if (!selection || !contentRef) return 0;

    if (selection.rangeCount === 0) return 0;
    const range = selection.getRangeAt(0);

    // Create a range from start of contentRef to cursor
    const preRange = document.createRange();
    preRange.selectNodeContents(contentRef);
    preRange.setEnd(range.startContainer, range.startOffset);

    return preRange.toString().length;
  };

  const getInnerHTML = (): string => {
    return contentRef?.innerHTML || '';
  };

  const getTextContent = (): string => {
    return contentRef?.textContent || '';
  };

  const handleInput = (e: InputEvent) => {
    const html = getInnerHTML();
    outlineStore.updateBlockContent(props.block.id, html);
  };

  const applyFormatting = (command: string) => {
    document.execCommand(command, false);
    contentRef?.focus();
  };

  const insertLink = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const selectedText = selection.toString();
    if (!selectedText) {
      alert('Please select some text first to create a link.');
      return;
    }

    setShowLinkModal(true);
  };

  const confirmLink = () => {
    const url = linkUrl();
    if (!url) return;

    document.execCommand('createLink', false, url);
    setShowLinkModal(false);
    setLinkUrl('');
    contentRef?.focus();

    // Update store with new HTML
    const html = getInnerHTML();
    outlineStore.updateBlockContent(props.block.id, html);
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    // Ctrl+;: toggle collapse
    if (e.key === ';' && e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault();
      if (hasChildren()) {
        outlineStore.toggleCollapsed(props.block.id);
      }
      return;
    }

    // Cmd+.: zoom into block
    if (e.key === '.' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
      e.preventDefault();
      const focusId = outlineStore.zoomIn(props.block.id);
      if (focusId) {
        // Focus will be handled by Outline component after re-render
        requestAnimationFrame(() => {
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: focusId, position: 'start' }
          }));
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
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: focusId, position: 'start' }
          }));
        });
      }
      return;
    }

    // Cmd+Enter: cycle checkbox state
    if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !e.shiftKey) {
      e.preventDefault();
      outlineStore.cycleCheckboxState(props.block.id);
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
    const htmlContent = getInnerHTML();

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
      outlineStore.updateBlockContent(props.block.id, beforeHTML);
      // Sync the DOM immediately
      if (contentRef) {
        contentRef.innerHTML = beforeHTML;
      }

      // Create new block with content after cursor
      const newId = outlineStore.insertBlockAsSibling(props.block.id, afterHTML);

      // Dispatch focus request for new block
      window.dispatchEvent(new CustomEvent('outline-focus', {
        detail: { id: newId, position: 'start' }
      }));
    }

    if (e.key === 'Backspace' && cursorPos === 0 && !e.shiftKey) {
      e.preventDefault();

      if (textContent === '' && hasChildren()) {
        // Don't merge if block has children and is empty - just prevent
        return;
      }

      const result = outlineStore.mergeWithPrevious(props.block.id);
      if (result.focusId) {
        window.dispatchEvent(new CustomEvent('outline-focus', {
          detail: { id: result.focusId, position: result.focusOffset }
        }));
      }
    }

    if (e.key === 'Tab') {
      e.preventDefault();

      if (e.shiftKey) {
        // Unindent
        outlineStore.unindentBlock(props.block.id);
      } else {
        // Indent
        outlineStore.indentBlock(props.block.id);
      }

      // Refocus after DOM updates
      requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent('outline-focus', {
          detail: { id: props.block.id, position: cursorPos }
        }));
      });
    }

    if (e.key === 'ArrowUp' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const selection = window.getSelection();
      if (selection && selection.isCollapsed) {
        e.preventDefault();
        const prevBlock = outlineStore.getPreviousBlock(props.block.id);
        if (prevBlock) {
          // Try to maintain horizontal position, clamped to the previous block's length
          // Create a temporary div to get text length from HTML content
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = prevBlock.block.content;
          const prevLength = tempDiv.textContent?.length || 0;
          const targetPos = Math.min(cursorPos, prevLength);
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: prevBlock.block.id, position: targetPos }
          }));
        }
      }
    }

    if (e.key === 'ArrowDown' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const selection = window.getSelection();
      if (selection && selection.isCollapsed) {
        e.preventDefault();
        const nextBlock = outlineStore.getNextBlock(props.block.id);
        if (nextBlock) {
          // Try to maintain horizontal position, clamped to the next block's length
          // Create a temporary div to get text length from HTML content
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = nextBlock.block.content;
          const nextLength = tempDiv.textContent?.length || 0;
          const targetPos = Math.min(cursorPos, nextLength);
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: nextBlock.block.id, position: targetPos }
          }));
        }
      }
    }

    if (e.key === 'ArrowLeft' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const selection = window.getSelection();
      if (selection && selection.isCollapsed && cursorPos === 0) {
        e.preventDefault();
        const prevBlock = outlineStore.getPreviousBlock(props.block.id);
        if (prevBlock) {
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: prevBlock.block.id, position: 'end' }
          }));
        }
      }
    }

    if (e.key === 'ArrowRight' && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey) {
      const selection = window.getSelection();
      if (selection && selection.isCollapsed && cursorPos === textContent.length) {
        e.preventDefault();
        const nextBlock = outlineStore.getNextBlock(props.block.id);
        if (nextBlock) {
          window.dispatchEvent(new CustomEvent('outline-focus', {
            detail: { id: nextBlock.block.id, position: 'start' }
          }));
        }
      }
    }
  };

  const handleToggleCollapse = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    outlineStore.toggleCollapsed(props.block.id);
  };

  const handleCheckboxClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    outlineStore.cycleCheckboxState(props.block.id);
  };

  const renderCheckbox = () => {
    const state = props.block.checkboxState;
    if (state === 'none') return null;

    return (
      <div
        class="w-4 h-4 flex items-center justify-center flex-shrink-0 cursor-pointer border-2 border-gray-400 rounded mr-2 hover:border-gray-600"
        onClick={handleCheckboxClick}
      >
        <Show when={state === 'checked'}>
          <svg class="w-3 h-3 text-gray-700" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 6L5 9L10 3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </Show>
      </div>
    );
  };

  return (
    <div class="block-container">
      <div class="flex items-start group">
        {/* Collapse toggle / bullet */}
        <div
          class="w-5 h-6 flex items-center justify-center flex-shrink-0 cursor-pointer select-none"
          onClick={handleToggleCollapse}
        >
          <Show
            when={hasChildren()}
            fallback={
              <span class="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
            }
          >
            <span
              class={`text-gray-500 text-sm transition-transform ${isCollapsed() ? '' : 'rotate-90'}`}
            >
              &#9656;
            </span>
          </Show>
        </div>

        {/* Checkbox (if enabled) */}
        {renderCheckbox()}

        {/* Content */}
        <div
          ref={contentRef}
          contentEditable={true}
          class="flex-1 outline-none py-0.5 px-1 min-h-[1.5rem] leading-6 text-gray-900"
          onInput={handleInput}
          onKeyDown={handleKeyDown}
        />
      </div>

      {/* Link Modal */}
      <Show when={showLinkModal()}>
        <div class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div class="bg-white rounded-lg p-6 shadow-xl max-w-md w-full">
            <h3 class="text-lg font-semibold mb-4">Insert Link</h3>
            <input
              type="text"
              placeholder="https://example.com"
              class="w-full border border-gray-300 rounded px-3 py-2 mb-4 outline-none focus:border-blue-500"
              value={linkUrl()}
              onInput={(e) => setLinkUrl(e.currentTarget.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  confirmLink();
                }
                if (e.key === 'Escape') {
                  e.preventDefault();
                  setShowLinkModal(false);
                  setLinkUrl('');
                }
              }}
            />
            <div class="flex justify-end gap-2">
              <button
                class="px-4 py-2 text-gray-600 hover:text-gray-800"
                onClick={() => {
                  setShowLinkModal(false);
                  setLinkUrl('');
                }}
              >
                Cancel
              </button>
              <button
                class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                onClick={confirmLink}
              >
                Insert
              </button>
            </div>
          </div>
        </div>
      </Show>

      {/* Children */}
      <Show when={hasChildren() && !isCollapsed()}>
        <div class="ml-5">
          <For each={props.block.children}>
            {(child, index) => (
              <Block
                block={child}
                path={[...props.path, index()]}
                focusRequest={props.focusRequest}
                onFocusHandled={props.onFocusHandled}
              />
            )}
          </For>
        </div>
      </Show>
    </div>
  );
};
