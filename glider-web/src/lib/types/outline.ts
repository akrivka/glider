export type CheckboxState = 'none' | 'unchecked' | 'checked';

export interface Block {
	id: string;
	content: string; // HTML string with rich-text formatting
	children: Block[];
	collapsed: boolean;
	checkboxState: CheckboxState;
}

export interface OutlineState {
	blocks: Block[];
}

export function createId(): string {
	return Math.random().toString(36).substring(2, 11);
}

export function createBlock(content: string = '', children: Block[] = []): Block {
	return {
		id: createId(),
		content,
		children,
		collapsed: false,
		checkboxState: 'none'
	};
}
