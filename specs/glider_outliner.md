In this phase of this project, we'll implement a simple outliner interface, that will be a building block of the core note-taking system. 

# Steps

1. [x] Basic outliner with nesting and collapsing
2. [x] Rich-text inside blocks
3. [x] Zooming in and out of blocks and basic keybinds

# Step 1

The goal is to create something akin to Roam Research/Workflowy's outliner, specifically:
* It allows arbirtary nesting and collapsing of blocks.
* There is no sense in which navigation makes it seem like there's an underlying plain-text Markdown list (there shouldn't be!), meaning:
    * Backspacing at the beginning of a block should merge the current block with the previous block
    * (Shift-)Tab-ing should bring the current block to the previous/next level, wherever is nearest.
* Arrowing up and down should move the cursor to the most natural position, as if it was a WYSIWYG editor (e.g. arrowing up from a position in the middle of a block shouldn't jump to the first position in the block above)

Make this the landing page of @glider-web/ with one editable outline in the center. Do not worry about backend replication at all, make it be client-side only, but be aware that we will want to sync this with a backend representation eventually (in a simple way! no CRDTs or other complicated stuff. It doesn't have to work offline).

# Step 2

Now we'll add rich-text capabilities to the outliner. Add bold, italic, underline, strikethrough and links. Feel free to use Markdown as the underlying representation, but don't surface it to the UI. From the UI, it should look like a native rich-text editor like Google Docs.

As bonus step, add the ability to add TODO check-boxes to the beginning of the block. In the background representation, you can represent this is as [ ] but again, don't let the user actually see the underlying representation: if they delete the check-box they delete all of it. Let it be toggleable by cmd+enter: cycle through: checkbox, checked checkbox, no checkbox.

# Step 3

First, add the basic keybind Ctrl+; for collapsing/expanding the current block.

Next, add the following keybinds:
* Cmd+.: zooms in to the current block, making it top-level, and showing the "path" to it as breadcrumbs in smaller horizontal text above, and focusing onto the first nested block (that way, one can keep pressing Cmd+> to zoom further and further)
* Cmd+,: to zoom out one level, again focusing the nested block