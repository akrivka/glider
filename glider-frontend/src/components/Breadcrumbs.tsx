import { Component, For, Show } from 'solid-js';
import { outlineStore, BlockLocation } from '../store/outlineStore';

export const Breadcrumbs: Component = () => {
  const breadcrumbs = () => outlineStore.getBreadcrumbs();

  const handleBreadcrumbClick = (path: number[]) => {
    const focusId = outlineStore.zoomTo(path);
    if (focusId) {
      requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent('outline-focus', {
          detail: { id: focusId, position: 'start' }
        }));
      });
    }
  };

  const getBlockText = (location: BlockLocation): string => {
    // Create a temporary div to extract text from HTML
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = location.block.content;
    const text = tempDiv.textContent || '';
    // Truncate if too long
    return text.length > 50 ? text.substring(0, 50) + '...' : text;
  };

  return (
    <Show when={breadcrumbs().length > 0}>
      <div class="breadcrumbs mb-4 flex items-center gap-2 text-sm text-gray-500">
        {/* Root link */}
        <button
          class="hover:text-gray-700 hover:underline"
          onClick={() => handleBreadcrumbClick([])}
        >
          Root
        </button>

        <For each={breadcrumbs()}>
          {(location) => (
            <>
              <span class="text-gray-400">/</span>
              <button
                class="hover:text-gray-700 hover:underline"
                onClick={() => handleBreadcrumbClick(location.path)}
              >
                {getBlockText(location)}
              </button>
            </>
          )}
        </For>
      </div>
    </Show>
  );
};
