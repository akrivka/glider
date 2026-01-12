import { createStore, produce } from 'solid-js/store';
import { Block, createBlock, OutlineState } from '../types/outline';

// Path represents the position of a block in the tree as an array of indices
export type BlockPath = number[];

export interface BlockLocation {
  path: BlockPath;
  block: Block;
}

function createInitialState(): OutlineState {
  return {
    blocks: [createBlock('')],
  };
}

const [state, setState] = createStore<OutlineState>(createInitialState());

// Get block at a given path
function getBlockAtPath(blocks: Block[], path: BlockPath): Block | null {
  if (path.length === 0) return null;

  let current: Block | undefined = blocks[path[0]];
  for (let i = 1; i < path.length; i++) {
    if (!current) return null;
    current = current.children[path[i]];
  }
  return current || null;
}

// Get parent blocks array and index for a given path
function getParentAndIndex(blocks: Block[], path: BlockPath): { parent: Block[] | null; parentPath: BlockPath; index: number } {
  if (path.length === 0) return { parent: null, parentPath: [], index: -1 };
  if (path.length === 1) return { parent: blocks, parentPath: [], index: path[0] };

  const parentPath = path.slice(0, -1);
  const parentBlock = getBlockAtPath(blocks, parentPath);
  if (!parentBlock) return { parent: null, parentPath: [], index: -1 };

  return { parent: parentBlock.children, parentPath, index: path[path.length - 1] };
}

// Find block by ID and return its path
function findBlockPath(blocks: Block[], id: string, currentPath: BlockPath = []): BlockPath | null {
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    const path = [...currentPath, i];
    if (block.id === id) return path;
    const childPath = findBlockPath(block.children, id, path);
    if (childPath) return childPath;
  }
  return null;
}

// Get all blocks in document order (flattened, respecting collapsed state for visibility)
function flattenBlocks(blocks: Block[], path: BlockPath = [], includeCollapsed = false): BlockLocation[] {
  const result: BlockLocation[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const block = blocks[i];
    const blockPath = [...path, i];
    result.push({ path: blockPath, block });
    if (block.children.length > 0 && (includeCollapsed || !block.collapsed)) {
      result.push(...flattenBlocks(block.children, blockPath, includeCollapsed));
    }
  }
  return result;
}

// Get the previous visible block in document order
function getPreviousBlock(id: string): BlockLocation | null {
  const flat = flattenBlocks(state.blocks);
  const index = flat.findIndex(loc => loc.block.id === id);
  if (index <= 0) return null;
  return flat[index - 1];
}

// Get the next visible block in document order
function getNextBlock(id: string): BlockLocation | null {
  const flat = flattenBlocks(state.blocks);
  const index = flat.findIndex(loc => loc.block.id === id);
  if (index < 0 || index >= flat.length - 1) return null;
  return flat[index + 1];
}

// Update block content
function updateBlockContent(id: string, content: string) {
  const path = findBlockPath(state.blocks, id);
  if (!path) return;

  setState(produce((s) => {
    let current: Block[] = s.blocks;
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]].children;
    }
    current[path[path.length - 1]].content = content;
  }));
}

// Toggle collapsed state
function toggleCollapsed(id: string) {
  const path = findBlockPath(state.blocks, id);
  if (!path) return;

  setState(produce((s) => {
    let current: Block[] = s.blocks;
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]].children;
    }
    current[path[path.length - 1]].collapsed = !current[path[path.length - 1]].collapsed;
  }));
}

// Insert a new block after the given block, returns the new block's ID
function insertBlockAfter(id: string, content: string = ''): string {
  const path = findBlockPath(state.blocks, id);
  if (!path) return '';

  const newBlock = createBlock(content);
  const block = getBlockAtPath(state.blocks, path);

  // If block has visible children (not collapsed), insert as first child
  if (block && block.children.length > 0 && !block.collapsed) {
    setState(produce((s) => {
      let current: Block[] = s.blocks;
      for (let i = 0; i < path.length - 1; i++) {
        current = current[path[i]].children;
      }
      current[path[path.length - 1]].children.unshift(newBlock);
    }));
  } else {
    // Insert as sibling after
    setState(produce((s) => {
      let current: Block[] = s.blocks;
      for (let i = 0; i < path.length - 1; i++) {
        current = current[path[i]].children;
      }
      current.splice(path[path.length - 1] + 1, 0, newBlock);
    }));
  }

  return newBlock.id;
}

// Insert a new block as a sibling (always, even if current block has children)
function insertBlockAsSibling(id: string, content: string = ''): string {
  const path = findBlockPath(state.blocks, id);
  if (!path) return '';

  const newBlock = createBlock(content);

  setState(produce((s) => {
    let current: Block[] = s.blocks;
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]].children;
    }
    current.splice(path[path.length - 1] + 1, 0, newBlock);
  }));

  return newBlock.id;
}

// Delete a block and return info about what to focus
function deleteBlock(id: string): { focusId: string | null; focusAtEnd: boolean } {
  const path = findBlockPath(state.blocks, id);
  if (!path) return { focusId: null, focusAtEnd: false };

  const prevBlock = getPreviousBlock(id);

  // Don't delete if it's the only block
  if (state.blocks.length === 1 && path.length === 1 && state.blocks[0].children.length === 0) {
    return { focusId: null, focusAtEnd: false };
  }

  setState(produce((s) => {
    let current: Block[] = s.blocks;
    for (let i = 0; i < path.length - 1; i++) {
      current = current[path[i]].children;
    }
    current.splice(path[path.length - 1], 1);
  }));

  return { focusId: prevBlock?.block.id || null, focusAtEnd: true };
}

// Merge a block with its previous sibling (for backspace at start of block)
function mergeWithPrevious(id: string): { focusId: string | null; focusOffset: number } {
  const path = findBlockPath(state.blocks, id);
  if (!path) return { focusId: null, focusOffset: 0 };

  const block = getBlockAtPath(state.blocks, path);
  if (!block) return { focusId: null, focusOffset: 0 };

  const prevBlock = getPreviousBlock(id);
  if (!prevBlock) return { focusId: null, focusOffset: 0 };

  const prevContent = prevBlock.block.content;
  const focusOffset = prevContent.length;

  // Update previous block's content
  setState(produce((s) => {
    let current: Block[] = s.blocks;
    for (let i = 0; i < prevBlock.path.length - 1; i++) {
      current = current[prevBlock.path[i]].children;
    }
    current[prevBlock.path[prevBlock.path.length - 1]].content = prevContent + block.content;
  }));

  // Move children of deleted block to previous block if it has none
  if (block.children.length > 0) {
    const prevBlockCurrent = getBlockAtPath(state.blocks, prevBlock.path);
    if (prevBlockCurrent && prevBlockCurrent.children.length === 0) {
      setState(produce((s) => {
        let prevCurrent: Block[] = s.blocks;
        for (let i = 0; i < prevBlock.path.length - 1; i++) {
          prevCurrent = prevCurrent[prevBlock.path[i]].children;
        }
        prevCurrent[prevBlock.path[prevBlock.path.length - 1]].children = [...block.children];
      }));
    }
  }

  // Delete the current block
  setState(produce((s) => {
    // Re-find path since structure may have changed
    const currentPath = findBlockPath(s.blocks, id);
    if (!currentPath) return;

    let current: Block[] = s.blocks;
    for (let i = 0; i < currentPath.length - 1; i++) {
      current = current[currentPath[i]].children;
    }
    current.splice(currentPath[currentPath.length - 1], 1);
  }));

  return { focusId: prevBlock.block.id, focusOffset };
}

// Indent a block (make it a child of the previous sibling)
function indentBlock(id: string): boolean {
  const path = findBlockPath(state.blocks, id);
  if (!path) return false;

  const index = path[path.length - 1];

  // Can't indent if it's the first item at its level
  if (index === 0) return false;

  const block = getBlockAtPath(state.blocks, path);
  if (!block) return false;

  setState(produce((s) => {
    let parent: Block[] = s.blocks;
    for (let i = 0; i < path.length - 1; i++) {
      parent = parent[path[i]].children;
    }

    // Get previous sibling
    const prevSibling = parent[index - 1];

    // Remove block from current position
    const [removed] = parent.splice(index, 1);

    // Add to previous sibling's children
    prevSibling.children.push(removed);

    // Expand the previous sibling if it was collapsed
    prevSibling.collapsed = false;
  }));

  return true;
}

// Unindent a block (move it to parent's level, after parent)
function unindentBlock(id: string): boolean {
  const path = findBlockPath(state.blocks, id);
  if (!path || path.length < 2) return false; // Can't unindent top-level blocks

  const block = getBlockAtPath(state.blocks, path);
  if (!block) return false;

  setState(produce((s) => {
    // Get parent block
    const parentPath = path.slice(0, -1);
    let grandparent: Block[] = s.blocks;
    for (let i = 0; i < parentPath.length - 1; i++) {
      grandparent = grandparent[parentPath[i]].children;
    }

    const parentIndex = parentPath[parentPath.length - 1];
    const parentBlock = grandparent[parentIndex];
    const blockIndex = path[path.length - 1];

    // Remove block from parent's children
    const [removed] = parentBlock.children.splice(blockIndex, 1);

    // Move any siblings that were after this block to become children of the removed block
    const siblingsAfter = parentBlock.children.splice(blockIndex);
    removed.children.push(...siblingsAfter);

    // Insert after parent
    grandparent.splice(parentIndex + 1, 0, removed);
  }));

  return true;
}

// Get the last visible descendant of a block
function getLastVisibleDescendant(block: Block): Block {
  if (block.children.length === 0 || block.collapsed) {
    return block;
  }
  return getLastVisibleDescendant(block.children[block.children.length - 1]);
}

export const outlineStore = {
  get state() { return state; },
  getBlockAtPath,
  findBlockPath,
  flattenBlocks,
  getPreviousBlock,
  getNextBlock,
  updateBlockContent,
  toggleCollapsed,
  insertBlockAfter,
  insertBlockAsSibling,
  deleteBlock,
  mergeWithPrevious,
  indentBlock,
  unindentBlock,
};
