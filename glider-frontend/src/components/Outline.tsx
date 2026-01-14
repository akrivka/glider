import { Component, For, createSignal, onMount, onCleanup } from 'solid-js';
import { outlineStore } from '../store/outlineStore';
import { Block } from './Block';
import { Breadcrumbs } from './Breadcrumbs';

export const Outline: Component = () => {
  const [focusRequest, setFocusRequest] = createSignal<{ id: string; position: 'start' | 'end' | number } | null>(null);

  const visibleBlocks = () => outlineStore.getVisibleBlocks();
  const zoomPath = () => outlineStore.state.zoomPath;

  const handleFocusEvent = (e: CustomEvent<{ id: string; position: 'start' | 'end' | number }>) => {
    setFocusRequest(e.detail);
  };

  onMount(() => {
    window.addEventListener('outline-focus', handleFocusEvent as EventListener);

    // Focus the first block on mount
    const firstBlock = outlineStore.state.blocks[0];
    if (firstBlock) {
      setFocusRequest({ id: firstBlock.id, position: 'start' });
    }
  });

  onCleanup(() => {
    window.removeEventListener('outline-focus', handleFocusEvent as EventListener);
  });

  const handleFocusHandled = () => {
    setFocusRequest(null);
  };

  return (
    <div class="outline-container max-w-3xl mx-auto p-4">
      <Breadcrumbs />
      <For each={visibleBlocks()}>
        {(block, index) => (
          <Block
            block={block}
            path={[...zoomPath(), index()]}
            focusRequest={focusRequest()}
            onFocusHandled={handleFocusHandled}
          />
        )}
      </For>
    </div>
  );
};
