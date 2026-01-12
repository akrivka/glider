In this phase of this project, we'll implement a simple outliner interface, that will be a building block of the core note-taking system. 

# Steps 

1. [ ] Basic outliner with nesting and collapsing
2. [ ] Rich-text inside blocks
3. [ ] Zooming in and out of blocks, batch collapsing/expanding

# Step 1

The goal is to create something akin to Roam Research/Workflowy's outliner, specifically:
* It allows arbirtary nesting and collapsing of blocks.
* There is no sense in which navigation makes it seem like there's an underlying plain-text Markdown list (there shouldn't be!), meaning:
    * Backspacing at the beginning of a block should merge the current block with the previous block
    * (Shift-)Tab-ing should bring the current block to the previous/next level, wherever is nearest.
* Arrowing up and down should move the cursor to the most natural position

Make this the landing page of @glider-frontend/ with one editable outline in the center. Do not worry about backend replication at all, make it be client-side only, but be aware that we will want to sync this with a backend representation eventually (in a simple way! no CRDTs or other complicated stuff. It doesn't have to work offline).

# Step 2

TBD

# Step 3

TBD