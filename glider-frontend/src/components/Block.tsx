import { Component, For, Show, createEffect, onMount } from 'solid-js';
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

  const hasChildren = () => props.block.children.length > 0;
  const isCollapsed = () => props.block.collapsed;
  const depth = () => props.path.length - 1;

  // Set initial content on mount
  onMount(() => {
    if (contentRef) {
      contentRef.textContent = props.block.content;
    }
  });

  // Sync content from store when it changes externally (e.g., after merge)
  createEffect(() => {
    const content = props.block.content;
    if (contentRef && document.activeElement !== contentRef) {
      contentRef.textContent = content;
    }
  });

  // Handle focus requests
  createEffect(() => {
    const req = props.focusRequest;
    if (req && req.id === props.block.id && contentRef) {
      // Sync content before focusing (important for split/merge operations)
      if (contentRef.textContent !== props.block.content) {
        contentRef.textContent = props.block.content;
      }

      contentRef.focus();

      const selection = window.getSelection();
      const range = document.createRange();
      const textNode = contentRef.firstChild;

      if (req.position === 'start') {
        range.setStart(contentRef, 0);
        range.collapse(true);
      } else if (req.position === 'end') {
        if (textNode) {
          range.setStart(textNode, textNode.textContent?.length || 0);
        } else {
          range.setStart(contentRef, 0);
        }
        range.collapse(true);
      } else if (typeof req.position === 'number') {
        if (textNode && textNode.textContent) {
          const offset = Math.min(req.position, textNode.textContent.length);
          range.setStart(textNode, offset);
        } else {
          range.setStart(contentRef, 0);
        }
        range.collapse(true);
      }

      selection?.removeAllRanges();
      selection?.addRange(range);
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

  const handleInput = (e: InputEvent) => {
    const target = e.currentTarget as HTMLDivElement;
    outlineStore.updateBlockContent(props.block.id, target.textContent || '');
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    const cursorPos = getCursorPosition();
    // Use DOM content, not store content, since contentEditable is managed imperatively
    const content = contentRef?.textContent || '';

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();

      // Split content at cursor
      const beforeCursor = content.slice(0, cursorPos);
      const afterCursor = content.slice(cursorPos);

      // Update current block with content before cursor
      outlineStore.updateBlockContent(props.block.id, beforeCursor);
      // Sync the DOM immediately
      if (contentRef) {
        contentRef.textContent = beforeCursor;
      }

      // Create new block with content after cursor
      const newId = outlineStore.insertBlockAsSibling(props.block.id, afterCursor);

      // Dispatch focus request for new block
      window.dispatchEvent(new CustomEvent('outline-focus', {
        detail: { id: newId, position: 'start' }
      }));
    }

    if (e.key === 'Backspace' && cursorPos === 0 && !e.shiftKey) {
      e.preventDefault();

      if (content === '' && hasChildren()) {
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
          const prevContent = prevBlock.block.content;
          const targetPos = Math.min(cursorPos, prevContent.length);
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
          const nextContent = nextBlock.block.content;
          const targetPos = Math.min(cursorPos, nextContent.length);
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
      if (selection && selection.isCollapsed && cursorPos === content.length) {
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

        {/* Content */}
        <div
          ref={contentRef}
          contentEditable={true}
          class="flex-1 outline-none py-0.5 px-1 min-h-[1.5rem] leading-6 text-gray-900"
          onInput={handleInput}
          onKeyDown={handleKeyDown}
        />
        {/* Content is managed imperatively via textContent to avoid SolidJS reactivity issues */}
      </div>

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
