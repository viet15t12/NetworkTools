# PanelSideBar snap-to-collapse

Reviewed: **2026-08-16**.

## VS Code behavior

The implementation was checked against the current VS Code workbench source:

- `SidebarPart` declares `minimumWidth = 170` and `snap = true`.
- `SplitView` calculates a snap boundary from half of the view minimum size.
  A visible view stays at its minimum while the pointer is between the minimum
  and the snap boundary, then becomes hidden after crossing the boundary.
- The same boundary works in reverse for restoring a hidden view. SplitView
  keeps a cached visible size so normal visibility toggles can restore the
  user's previous width.

Primary references:

- [VS Code SidebarPart](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/browser/parts/sidebar/sidebarPart.ts)
- [VS Code SplitView](https://github.com/microsoft/vscode/blob/main/src/vs/base/browser/ui/splitview/splitview.ts)

## CAMS contract

`Main.qml` uses the same constants:

- minimum visible width: 170 px;
- snap boundary: 85 px;
- maximum width: 600 px.

One persistent 8 px `MouseArea` owns the complete drag, including when the
sidebar changes between visible and collapsed. Pointer coordinates are mapped
to scene coordinates before calculating the desired width, because the grab
area moves with the divider during the drag.

The visible geometry has three states:

1. Desired width below 85 px: sidebar is collapsed and occupies 0 px.
2. Desired width from 85 through 170 px: sidebar is visible at 170 px.
3. Desired width above 170 px: sidebar follows the pointer up to 600 px.

`savedSidebarWidth` is independent from the transient drag width. Ctrl+B and
ActivityBar visibility toggles restore that saved width. A completed visible
resize becomes the next saved width.

Qt Quick `SplitView` was not retained for this top-level resize. It has no
equivalent public `snap` property, and its internal visible-size cache competed
with the custom threshold during an active pointer grab. The sidebar and
content therefore use explicit anchored geometry with a single state owner.

## Regression coverage

`test_main_sidebar_snaps_closed_and_open_at_vscode_threshold` performs real
pointer press/move/release events:

- 84 px desired width collapses to 0 px;
- 85 px desired width restores to exactly 170 px;
- the released visible width becomes the saved width.
