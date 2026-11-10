# pbik coverage roadmap (pbik 0.12.0, 2026-11-10)

Read-only review: nothing in the kit was changed. Batch 1 (gaps 1, 20, 24 and schema-checked props; the gap 23 answer) shipped in
pbik 0.13.0: design/reviews/pbik-roadmap-batch1.md. Sources used, and only these:

- **pbik itself**: `tools/pbik/README.md`, `pbik <command> --help`, the `pbikit/` source, and the kit's
  `design/known-gaps.md` ("pbik can't write it yet"), which records how often each gap came up in Reps 1-10.
- **Microsoft Learn**:
  - [L1] *Power BI Desktop project report folder*,
    https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report (updated 2026-09-29)
  - [L2] *Create a Power BI report in enhanced report format*,
    https://learn.microsoft.com/en-us/power-bi/developer/embedded/projects-enhanced-report-format
  - [L3] *Edit Power BI Desktop project files outside Power BI Desktop*,
    https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-external-editing
- **Microsoft's PBIR JSON schemas**: https://github.com/microsoft/json-schemas/tree/main/fabric/item/report/definition,
  the latest version of each, read on 2026-11-10. In the tables below, `S:<kind> <version> #<Definition>` is
  `.../definition/<kind>/<version>/schema.json`, `#/definitions/<Definition>`.

Second pass (2026-11-10, gaps 20-29 below) added these, with the same rule (Microsoft Learn, Microsoft's schemas and
pbik's own code only):

- The schemas as cached by pbik: `pbik schemas fetch` on the rep8 fixture plus the latest version of each kind, into
  `tools/pbik/schemas/` (git-ignored). Probing the next patch, minor and major version of every kind found nothing newer
  than the table below; visualContainer 2.14.0 is still a 404. `definitionProperties/2.0.0` (definition.pbir) was
  cached too; it is Out (L3).
- pbik's `pbikit/` source (build.py, a11y.py, validate.py, roundtrip.py), `design/known-gaps.md` and `design/templates/`.
- **Microsoft Learn**, all read 2026-11-10:
  - [L4] *See what's new in the October 2026 Power BI update*, https://learn.microsoft.com/en-us/power-bi/fundamentals/whats-new
    (updated 2026-11-02)
  - [L5] *Limitations of Power BI Q&A*, https://learn.microsoft.com/en-us/power-bi/natural-language/q-and-a-limitations
    (updated 2026-09-10), Important note: Q&A experiences go away in February 2027; use Copilot instead.
  - [L6] *Convert Map and Filled map visuals to an Azure Maps visual*,
    https://learn.microsoft.com/en-us/azure/azure-maps/power-bi-visual-conversion (updated 2026-01-21), Important note:
    the Bing Maps visual is scheduled for deprecation, with no date set yet.
  - [L7] *Design Power BI reports for accessibility*,
    https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-accessibility-creating-reports (updated 2026-09-29)
  - [L8] *Power BI Report skill*, https://learn.microsoft.com/en-us/power-bi/developer/agentic/power-bi-report-skill-overview
    (updated 2026-10-02), "Considerations": avoid creating visuals scheduled for deprecation, including Q&A, Bing Maps
    and filled maps.
  - L1 and L3 were read again (both updated 2026-09-29). New since the first pass: PBIR is GA and the default format
    (L1 "Convert existing report to PBIR"); detecting and reloading external changes, and the Desktop Bridge, are still
    preview and need the August 2026 Desktop or later (L3 "Prerequisites", "Considerations and limitations").

No other tool, its docs or its command names were used.

## Schema license

The microsoft/json-schemas repository is under the **MIT License** ("Copyright (c) Microsoft Corporation"). This
comes from the repository's `LICENSE` file, and the GitHub license API reports SPDX `MIT`. MIT allows use, copying and
modification, provided the copyright and permission notice go with any copies or substantial portions. pbik reads
the schemas only, and `pbik schemas fetch` caches them git-ignored, so the kit ships no copy and owes no notice. If a
schema file is ever committed, for example as a test fixture, add Microsoft's MIT notice beside it.

## Schemas read (latest published versions)

| Kind | Latest | pbik writes / caps at | File |
|---|---|---|---|
| report | 3.3.0 | via targetDesktop | `definition/report.json` |
| page | 2.1.0 | 2.1.0 | `pages/<page>/page.json` |
| pagesMetadata | 1.1.0 | 1.1.0 | `pages/pages.json` |
| visualContainer | 2.13.0 (Desktop writes 2.14.0: 404) | 2.13.0 | `visuals/<visual>/visual.json` |
| visualConfiguration | 2.8.0 | embedded in visualContainer | `visual` inside visual.json |
| visualContainerMobileState | 2.8.0 | **not written** | `visuals/<visual>/mobile.json` |
| filterConfiguration | 1.3.0 | embedded | `filterConfig` in report, page and visual |
| formattingObjectDefinitions | 1.5.0 | embedded | `objects` selectors |
| semanticQuery | 1.4.0 | embedded | fields, filters, conditional formatting |
| bookmark | 2.1.0 | via targetDesktop | `bookmarks/<name>.bookmark.json` |
| bookmarksMetadata | 1.0.0 | 1.0.0 | `bookmarks/bookmarks.json` |
| reportExtension | 1.0.0 | 1.0.0 | `reportExtensions.json` |
| versionMetadata | 1.0.0 | 1.0.0 | `version.json` |
| definitionStructure | 3.3.0 listed, `schema.json` 404 | n/a | none |

## Coverage map

Key: **Yes** = a layout key or command writes it. **Generic** = only through `props` (any `objects` /
`visualContainerObjects` property, a JSON selector or `{"raw": ...}`), with no model of its meaning and no checks.
**Partial** = some of the schema. **No** = pbik never writes it. **Out** = Microsoft says not to edit it externally.

### Report (`report.json`, S:report 3.3.0)

| Object / operation | pbik | Notes |
|---|---|---|
| `themeCollection.customTheme` (register and apply a theme) | Yes | `theme apply`, layout `theme` |
| `themeCollection.baseTheme` (pick the base theme) | No | left as Desktop wrote it |
| `resourcePackages` RegisteredResources: Image | Yes | `resource add`; binding it is Generic (see gap 3) |
| `resourcePackages` item type ShapeMap | No | gap 14 |
| `publicCustomVisuals` | Yes | written for Deneb and HTML Content |
| `organizationCustomVisuals`, private `CustomVisuals/` folder [L1] | No | gap 15 |
| `filterConfig` (report-level filters) | No | gap 4 |
| `objects.outspacePane` / `section` (filter pane look, collapsed pane) | No | gap 1 |
| `settings` (#ExplorationSettings: 26 settings, e.g. `hideVisualContainerHeader`, `exportDataMode`, `useEnhancedTooltips`, `defaultDrillFilterOtherVisuals`, `pagesPosition`, `locale`) | No | gap 1 |
| `slowDataSourceSettings`, `dataSourceVariables` | No | low; DirectQuery only |
| `annotations` (report, page, visual) [L1 "PBIR annotations"] | No | gap 13 |

### Pages (S:page 2.1.0, S:pagesMetadata 1.1.0)

| Object / operation | pbik | Notes |
|---|---|---|
| Create page, `name`, `displayName`, `width`, `height`, `displayOption` | Yes | stable 20-hex name |
| `visibility: HiddenInViewMode` | Yes | layout `hidden` |
| `pageOrder`, `activePageName` | Yes | layout `active` |
| `landingPageName` (pagesMetadata 1.1.0) | No | gap 12 |
| Remove page | No | `--prune` removes visuals only; gap 12 |
| `objects.background` (colour, transparency) | Yes | |
| `objects.background` image, `displayArea`, `pageSize` type, `pageInformation`, `outspace` (wallpaper) | Generic | page `props` are not a layout key; gap 12 |
| `objects.outspacePane`, `filterCard` (per page) | No | gap 1 |
| `objects.pageRefresh` (automatic page refresh) | No | gap 12 |
| `objects.personalizeVisual` | No | low |
| `filterConfig` (page filters: Categorical, TopN) | Partial | gap 4 |
| `visualInteractions` (NoFilter, DataFilter, HighlightFilter) | Yes | `Default` isn't offered (the absent entry means it) |
| `type: Tooltip` + `pageBinding` (#BindingType Tooltip) | No | gap 6 |
| `type: Drillthrough` + `pageBinding` (`parameters`, `acceptsFilterContext`, `referenceScope`) | No | gap 7 |
| `autoPageGenerationConfig`, `howCreated` | No | Desktop-made only |

### Visuals (S:visualContainer 2.13.0, S:visualConfiguration 2.8.0)

| Object / operation | pbik | Notes |
|---|---|---|
| Create, update or remove visual by ID; `position` x, y, z, width, height, `tabOrder` | Yes | `--prune` removes |
| `position.angle` (rotation) | No | low |
| `isHidden` | Yes | |
| Visual groups (`visualGroup`, `parentGroupName`, `groupMode` ScaleMode / ScrollMode) | Yes | `type: group`, `mode` |
| `visualType` (native types, from templates) | Yes | any type with a harvested template |
| `query.queryState` role bindings, field parameters | Yes | |
| `query.sortDefinition` | Yes | |
| `query.isDrillDisabled`, `expansionStates`, hierarchy fields (#QueryHierarchyLevelExpression) | No | gap 8 |
| `query.options` (binned line sample, overlapping points) | No | low |
| `syncGroup` | Yes | layout `sync` |
| `drillFilterOtherVisuals` | Partial | always written true, no key |
| `objects` (all visual formatting) | Generic, plus keys | keys for text, shapes, cards, navigators, reference lines, column widths, slicer mode and selection |
| Per-member `objects` selectors (`data` / `scopeId`, #DataRepetitionSelector) | Generic | one member at a time; gap 2 |
| `visualContainerObjects`: title, subTitle, background, border, dropShadow, padding, spacing, general (alt text), visualHeader | Yes | layout `container` |
| `visualContainerObjects`: divider, lockAspect, stylePreset, visualHeaderTooltip | Generic | `container:` props |
| `visualContainerObjects.visualLink`: PageNavigation, Bookmark, Back, WebUrl, ClearAllSlicers | Yes | layout `action` |
| `visualLink` drillthrough (`drillthroughSection`), Q&A, `dataFunction` | No | gaps 7 and 16 |
| `visualContainerObjects.visualTooltip` (`type`, `section`: report-page tooltip) | No | gap 6 |
| `mobile.json` (S:visualContainerMobileState: mobile position and formatting) | No | gap 11 |
| `annotations`, `howCreated` | No | gap 13 |
| Custom visuals: Deneb, HTML Content | Yes | other AppSource or organization visuals: gap 15 |

### Fields and expressions (S:semanticQuery 1.4.0, #QueryExpressionContainer)

| Expression | pbik | Notes |
|---|---|---|
| Column, Measure, SourceRef (model and `extension` schema) | Yes | |
| Aggregation: Sum, Average, DistinctCount, Min, Max, CountNonNull (Function 0-5), First / Last | Yes | only Sum and Min seen in a Desktop save (known-gaps) |
| Aggregation: Median, StandardDeviation, Variance (6-8); Percentile | No | gap 9 |
| Hierarchy, HierarchyLevel, PropertyVariationSource (date hierarchies) | No | gap 8 |
| NativeVisualCalculation (visual calculations) | No | gap 10 |
| SparklineData (table and matrix sparklines) | No | gap 10 |
| GroupRef, Discretize (groups and bins) | No | low |
| Literal, ThemeDataColor, FillRule, Conditional / Case, ResourcePackageItem | Yes | cf types, colour values; ResourcePackageItem through `raw` |
| Comparison (measure filter), In (categorical), TopN subquery | Yes | |
| Between, Contains, StartsWith, Not / Or, DateSpan / DateAdd / Now (relative date), Exists | No | gap 4 |
| ScopedEval, FilteredEval, Arithmetic, Floor, AnyValue, DefaultValue, Percentile, NativeColumn / NativeMeasure | No | low; Desktop internals |

### Filters (S:filterConfiguration 1.3.0, #FilterContainer)

| Object / operation | pbik | Notes |
|---|---|---|
| Visual and page filters, `type` Categorical, TopN, Advanced (one measure comparison) | Yes | Advanced is visual-only, not Desktop-tested (README) |
| `isHiddenInViewMode`, `isLockedInViewMode` | Yes | `hidden`, `locked` |
| `type` Range, RelativeDate, RelativeTime, Include, Exclude, Tuple, Passthrough, VisualTopN; Advanced with text conditions | No | gap 4 |
| Report-level filters | No | gap 4 |
| `displayName`, `ordinal` + `filterSortOrder` (filter order in the pane), filter `objects.general` | No | gap 4 |

### Bookmarks (S:bookmark 2.1.0, S:bookmarksMetadata 1.0.0)

| Object / operation | pbik | Notes |
|---|---|---|
| Display bookmarks (`display.mode` hidden per visual or group), `options` (`targetVisualNames`, `applyOnlyToTargetVisuals`, `suppressActiveSection`, `suppressData`, `suppressDisplay`) | Yes | |
| Reset-selection data bookmarks | Yes | `data: true, display: false` |
| Bookmark groups, order | Yes | `bookmarkGroups` |
| Data bookmarks that save a state: `explorationState.filters`, per-section filters, `SingleVisualConfigState` (objects, `activeProjections`, `orderBy`, `expansionStates`), `highlight` | No | gap 5 |
| Bookmarks on another page (`changesPage: true`) | Yes | |

### Report extensions (S:reportExtension 1.0.0)

| Object / operation | pbik | Notes |
|---|---|---|
| Extension measures: add, list, remove; `dataType`, `dataCategory`, `formatString`, `description` | Yes | `measure ext` |
| `hidden`, `displayFolder`, `annotations`, `references`, `measureTemplate` | No | low; gap 13 for annotations |

### Files and operations from Microsoft Learn

| Operation | pbik | Source |
|---|---|---|
| Validate each file against its `$schema` | Yes | `validate` (local cache) [L1 "PBIR Json Schemas"] |
| Respect the naming convention (word characters or hyphens) | Yes | `<ID>_<name>` folders [L1 "PBIR naming convention"] |
| Apply external changes in an open Desktop | Yes | `desktop reload` through the Desktop Bridge [L3] |
| Batch edits across visuals by script | Yes | `build` from layout.json [L1 "PBIR format"] |
| Copy pages, visuals or bookmarks between reports | Partial | `templates harvest` copies formatting only, with no page or bookmark copy; gap 17 |
| `definition.pbir` (`byPath` / `byConnection`), `mobileState.json`, `semanticModelDiagramLayout.json`, legacy `report.json` | Out | Microsoft doesn't support editing these externally during the preview [L3 "Considerations and limitations"]; [L1 "Report files"] |
| `.pbi/localSettings.json` | Out | per user, git-ignored [L1] |
| Service limits: 1,000 pages, 1,000 visuals per page, 1,000 resource files, 300 MB | No check | gap 18 [L1 "PBIR considerations and limitations"] |
| Filter and slicer values saved in the files | No check | [L1 "PBIR folder and files", Important]; gap 19 |

## Gaps ranked by how often a typical build needs them

Frequency comes from the kit's own record (design/known-gaps.md, Reps 1-10) where it has one. Otherwise it's an
estimate from what the BRD template asks for, marked *est.*

| # | Gap | Need | Evidence | Microsoft source |
|---|---|---|---|---|
| 1 | **Report settings and filter pane look**: `report.json` `objects.outspacePane` (e.g. collapsed pane), page `outspacePane` / `filterCard` formatting, `settings` (#ExplorationSettings: hide visual headers, export data mode, enhanced tooltips) | Every build | All 7 reps set `outspacePane.expanded: false` by hand in Desktop | S:report 3.3.0 #ReportFormattingObjects, #OutspacePane, #ExplorationSettings; S:page 2.1.0 #OutspacePane, #FilterCard |
| 2 | **Per-member formatting** (`scopeId` data selectors: series and slice colours, markers, small-multiple headers) | Most builds with a categorical chart | Rep 5: 5, Rep 7: 31 entries | S:formattingObjectDefinitions 1.5.0 #Selector, #DataRepetitionSelector; S:semanticQuery 1.4.0 #QueryExpressionContainer (`Literal`, `Comparison` in scope) |
| 3 | **Images as a layout key** (`image` visual `ResourcePackageItem`, page background or wallpaper image) | Most builds (logo, icons) | Rep 6: 5 images, Rep 7: 6 images + 1 card | S:report 3.3.0 #ResourcePackageItem, #ResourcePackageItemType (Image); S:semanticQuery 1.4.0 #QueryResourcePackageItem; S:page 2.1.0 #Background; [L1 "RegisteredResources\"] |
| 4 | **Filters beyond Categorical and TopN**: relative date and time, Range (between), Advanced text conditions (contains, starts with, blank), Include / Exclude, Tuple, Passthrough; report-level filters; filter `displayName`, order (`ordinal`, `filterSortOrder`) | Most builds (*est.*: a "last 12 months" or year-range filter is common in a BRD) | known-gaps row "Advanced filters ... and report-level filters" | S:filterConfiguration 1.3.0 #FilterContainer (`type`, `ordinal`), `filterSortOrder`; S:report 3.3.0 `filterConfig`; S:semanticQuery 1.4.0 #QueryBetweenExpression, #QueryContainsExpression, #QueryStartsWithExpression, #QueryDateSpanExpression, #QueryDateAddExpression, #QueryNowExpression, #QueryNotExpression |
| 5 | **Data bookmarks that save a state** (slicer selections, filters, sort, projections) | Many builds that use bookmark toggles | Rep 7: 3 bookmarks, each saving 2 slicer states | S:bookmark 2.1.0 #ExplorationState, #FiltersState, #SectionState, #VisualContainerState, #SingleVisualConfigState, #HighlightState |
| 6 | **Report-page tooltips**: page `type: Tooltip` + `pageBinding`, visual `visualTooltip` `type` / `section` | Common in polished builds (*est.*) | None in Reps 1-7 | S:page 2.1.0 `type`, #PageBinding, #BindingType (Tooltip); S:visualConfiguration 2.8.0 #VisualTooltip; [L1 "Common PBIR errors" (pageBinding.name must be unique)] |
| 7 | **Drill-through pages**: page `type: Drillthrough`, `pageBinding.parameters`, `acceptsFilterContext`; button `visualLink` `drillthroughSection` | Common in multi-page builds (*est.*) | None in Reps 1-7 | S:page 2.1.0 #PageBinding, #BindingParameter; S:visualConfiguration 2.8.0 #VisualLink (`drillthroughSection`); [L1 "Common PBIR errors"] |
| 8 | **Hierarchies and drill**: hierarchy fields, `expansionStates` (matrix rows expanded), `isDrillDisabled` | Builds with a matrix or date drill (*est.*) | None recorded | S:semanticQuery 1.4.0 #QueryHierarchyExpression, #QueryHierarchyLevelExpression, #QueryPropertyVariationSourceExpression; S:visualConfiguration 2.8.0 #ExpansionState, #Query (`isDrillDisabled`) |
| 9 | **Aggregations**: Median, StandardDeviation, Variance, Percentile; Desktop check of Avg, Max, CountNonNull, DistinctCount | Occasional | known-gaps: only Sum and Min seen saved | S:semanticQuery 1.4.0 #QueryAggregateFunction (0-8), #QueryPercentileExpression |
| 10 | **Visual calculations and sparklines** | Occasional; growing (*est.*) | None recorded | S:semanticQuery 1.4.0 #QueryNativeVisualCalc, #QuerySparklineDataExpression |
| 11 | **Mobile layout** (`mobile.json` position and formatting per visual) | Rare in the kit; needed when a BRD asks for phone use | None in Reps 1-7 | S:visualContainerMobileState 2.8.0; [L1 "PBIR folder and files" (mobile.json)] |
| 12 | **Page settings and lifecycle**: `landingPageName`, page `props` (background image, `displayArea`, `pageSize` type, `pageInformation`), automatic `pageRefresh`, removing a page | Occasional | None recorded; page `props` would also close the background-image half of gap 3 | S:pagesMetadata 1.1.0 `landingPageName`; S:page 2.1.0 #PageFormattingObjects, #PageSize, #DisplayArea, #PageRefresh, #PageInformation |
| 13 | **Annotations** on report, page, visual (and extension measures): pbik could stamp the visual ID and layout hash, which Desktop ignores but keeps | Every build, but optional (tooling, not looks) | Not used yet | [L1 "PBIR annotations"]; S:report 3.3.0, S:page 2.1.0, S:visualContainer 2.13.0 #Annotation; S:reportExtension 1.0.0 #MeasureExtensionAnnotation |
| 14 | **Shape maps** with an uploaded map (`ShapeMap` resource item) | Rare | Rep 2: 3 | S:report 3.3.0 #ResourcePackageItemType (ShapeMap) |
| 15 | **Other custom visuals**: organization store (`organizationCustomVisuals`), private `.pbiviz` (`CustomVisuals/`, `CustomVisualJavascript` items), AppSource beyond Deneb and HTML Content | Rare; ladder step 4 needs approval (CLAUDE.md) | known-gaps "Custom visuals" | S:report 3.3.0 `organizationCustomVisuals`, #OrganizationCustomVisual, #ResourcePackageType; [L1 "CustomVisuals\"] |
| 16 | **Other visual links**: `dataFunction`; visual `position.angle`; `query.options`. (Q&A is no longer a build target: Q&A is retiring in February 2027 [L5], so gap 20 makes it a validate warning instead.) | Rare | None recorded | S:visualConfiguration 2.8.0 #VisualLink, #VisualQueryOptions; S:visualContainer 2.13.0 #VisualContainerPosition (`angle`) |
| 17 | **Copy a page, visual or bookmark between reports** (rename IDs, fix `pageBinding.name`, keep the bookmark's visuals) | Occasional (reuse across reps) | `templates harvest` covers formatting only | [L1 "PBIR format" (scenarios), "Common PBIR errors" (copied bookmark loses config; unique pageBinding.name)]; [L2] |
| 18 | **Service size limits** as validate checks (1,000 pages, 1,000 visuals per page, 1,000 resource files, 300 MB of resources, 300 MB of report files) | Never hit at kit scale; a cheap guard | None | [L1 "PBIR considerations and limitations"] |
| 19 | **Data values in report files**: list the filter, slicer and selector literals pbik wrote, so a privacy review (docs/it-security.md) can see model values that went to disk | Every build, as a check | Not checked | [L1 "PBIR folder and files", Important note] |

### Gaps added in the second pass (2026-11-10), ranked the same way

The first pass missed these. Most are retirements and accessibility rules on Microsoft Learn, plus schema objects
found by diffing every cached schema definition against the coverage map. Some ranks are estimates, marked *est.*

| # | Gap | Need | Evidence (pbik) | Microsoft source |
|---|---|---|---|---|
| 20 | **Retiring and deprecated visuals and options as validate warnings**: the Q&A visual and Q&A button links (`visualLink.qna`); Map and Filled map (Bing Maps), for which Desktop offers a conversion to Azure Maps; the deprecated page `displayOption` values `DeprecatedDynamic` and `ActualSizeTopLeft`. pbik passes any `displayOption` through unchecked, and validate has no deprecated-visual rule. | Every build, as a check (cheap) | `build.py:991` copies `spec.get("displayOption")` as given; no `qna`, `map` or `filledMap` rule in `validate.py` | [L5] Important (Q&A goes away in February 2027); [L6] Important (Bing Maps scheduled for deprecation); [L8] "Considerations", Legacy visuals; S:page 2.1.0 #PageDisplayOption (both values marked Deprecated); S:visualConfiguration 2.8.0 #VisualLink (`qna`) |
| 21 | **Decorative visuals stay in the tab order**: pbik writes `position.tabOrder` (visual number x 100) on every visual, shapes and decorative images included. Learn says to hide decorative shapes and images from the tab order. The PBIR form of "hidden from tab order" isn't in the schema description, so copy it from a Desktop save first. Add a layout key (e.g. `decorative: true`) that writes that form, and make `pbik validate` warn on a shape or image that has neither alt text nor that flag. | Every build with shapes or image icons (Reps 6-7: glass panels, bands, icons) | `build.py:1308` writes `tabOrder` on every visual; `a11y.py:16,244` only skips `shape` and `basicShape` when it checks order; templates `shape.glass-panel`, `shape.shape-band`, `image.image` | [L7] "Tab order", checklist "Shapes", "Images", "Across visuals on the page"; S:visualContainer 2.13.0 #VisualContainerPosition (`tabOrder`) |
| 22 | **Accessibility checks Learn lists that validate lacks**: alt text over the 250-character limit; text boxes whose text isn't also in alt text; data visuals with no deliberate sort order (the accessible Show Data table follows the visual's sort). | Every build, as a check | `a11y.py:210-213` checks only that alt text exists; no length, text-box or `sortDefinition` rule | [L7] "Alt text" (250-character limit), checklist "Textbox", "Sort order"; S:visualConfiguration 2.8.0 #VisualContainerGeneralFormattingObjects (`altText`), #SortDefinition |
| 23 | **Prerequisites for reloading external changes, as checks**: `pbik desktop reload` and "Apply external changes" are preview, and they need the August 2026 Desktop or later with the **Detect and reload external PBIP changes** preview option turned on. Every project file path must stay under the Windows 260-character limit, and pbik's `<ID>_<name>` folder names make paths longer. Neither is checked: `pbik project check` compares Desktop with the rep's schema target, not with the reload minimum. Reloading also resets filters, so a screenshot taken after a reload shows the default state. | Every build that reloads (*est.*) | No path-length check in `validate.py`; `desktop.py:40` reports only "not open, or its Desktop Bridge preview is off" (exit 3), with no Desktop version or path check | [L3] "Prerequisites" (August 2026 release, the preview option, the 260-character path limit), "Considerations and limitations" (preview; reloading resets filters) |
| 24 | **Roundtrip blind spots**: `pbik roundtrip` compares `definition/**/*.json` only and skips `StaticResources`, so it can't see Desktop rewriting the registered theme or images. Visual automatic filters reach `visual.json` only after the filter pane has been expanded once, so a roundtrip shows `filterConfig` additions that depend on the pane state, not on pbik. With the pane collapsed by default (gap 1), they may never be saved. Roundtrip should label these as pane-dependent rather than propose writing them. | Every roundtrip after a Desktop save | `roundtrip.py:24` `SKIP_DIRS = ("StaticResources",)`; `side_from_git` and `side_from_folder` read `definition/` only | [L1] "PBIR considerations and limitations" (automatic filters persisted only after the filter pane was expanded), "RegisteredResources\" |
| 25 | **Registering new resources is outside what Microsoft documents**: Learn supports edits to RegisteredResources files only for resources Desktop has already registered in report.json. `pbik resource add` (and a new theme file through `theme apply`) registers new ones itself. The PNG route works in Desktop (.claude/rules/svg.md), but it isn't documented, so record it as a support risk, recheck it at every `/update`, and add it as a smoke item. | Most builds (logo, icons, theme) | `resource add` writes the report.json `resourcePackages` entry and the file | [L1] "RegisteredResources\" ("Edits to RegisteredResources files are only supported for already loaded resources ...") |
| 26 | **Newer native visual types and options with no template**: list slicer (dropdown mode in preview), input slicer, Azure Maps (the replacement in gap 20), Gantt (preview); and new formatting on existing charts, such as the plot area background (GA in October 2026), which the settings catalog lacks until a refresh. pbik builds only types with a harvested template; `design/templates/` has `slicer` and `advancedSlicerVisual` but no list slicer, input slicer or map. | Occasional; growing (*est.*) | `design/templates/` listing; `catalog.py` warns only from settings already harvested | [L4] "Reporting" (Gantt, list slicer dropdown, plot area background); [L6] (Azure Maps GA) |
| 27 | **Visual group formatting**: a group's `objects` (background, `general.altText`, lockAspect) aren't written. pbik writes `displayName` and `groupMode` only, so a group that should be announced as one item can't get alt text. | Occasional (Reps 5-7 used groups) | `build.py:1094-1095` | S:visualContainer 2.13.0 #VisualGroupConfig, #VisualGroupFormattingObjects, #VisualGroupGeneralFormattingObjects |
| 28 | **Bookmark display modes beyond hidden**: `spotlight`, `maximize` (focus mode) with `maximizedOptions.dataTable` `accessible` (opens the screen-reader table), and `elevation`. pbik writes only `hidden`. | Rare (*est.*); spotlight is a common storytelling bookmark | `bookmarks.py:104` writes `{"mode": "hidden"}` only | S:bookmark 2.1.0 #VisualContainerDisplayMode, #VisualContainerDisplayState; [L7] "Focus mode", "Show data table" |
| 29 | **Cross-report drillthrough**: report `settings.useCrossReportDrillthrough` and page `pageBinding.referenceScope` `CrossReport`. This extends gap 7 to targets in other reports. | Rare | None recorded | S:report 3.3.0 #ExplorationSettings (`useCrossReportDrillthrough`); S:page 2.1.0 #PageBinding (`referenceScope`) |

### Suggested order (revised 2026-11-10)

1. **Gaps 20, 21, 22 and 1**: retirements and accessibility first. Gaps 20 and 22 are validate rules with no
   build change. Gap 21 needs one Desktop save to read the "hidden from tab order" form and touches every build. Then
   gap 1: report and page-level `props` (filter pane, settings) as layout keys.
2. **Gaps 13, 23 and 24**: annotations for IDs, and the reload and roundtrip checks. All three are tooling only, no
   report output change.
3. **Gaps 3, 12 and 25**: an `image` layout key and page `props` (Desktop-saved examples are already in Reps 6-7),
   with the resource-registration risk recorded and smoke-tested alongside them.
4. **Gaps 4 and 2**: filter types (relative date first) and per-member formatting. Both need a Desktop save to copy
   the exact form, then a catalog refresh and roundtrip.
5. **Gaps 5-8 and 27**: data bookmarks, tooltip pages, drill-through pages, hierarchies, group formatting. Each needs a
   Desktop smoke page first (CLAUDE.md `/smoke`).
6. **Gaps 18, 19 and 26**: the cheap validate checks, and templates for the new slicers and Azure Maps. Harvest
   Azure Maps before the first BRD that asks for a map, because gap 20 rules out Map and Filled map.
7. **Gaps 9-11, 14-17, 28 and 29**: when a BRD asks for them.

## Not covered by this review

- The Power BI theme JSON schema: pbik registers a theme file but doesn't write its contents (gen_theme.py does).
  That schema isn't one of the PBIR report schemas, so it was left out.
- The `definitionStructure` 3.3.0 schema: the folder is listed, but its `schema.json` returned 404.
- visualContainer 2.14.0: Desktop writes it but Microsoft hasn't published it (404). Anything new in it isn't listed
  here.

## Batch 2 status (bulk run 2026-11-10, design/reviews/pbik-roadmap-batch2.md)

| # | Status | Note |
|---|---|---|
| 21 | Partial: check done; writing "hidden from tab order" blocked | `decorative: true` layout key and validate warning; the PBIR form needs one Desktop save (checklist) |
| 22 | Done (check only) | alt text over 250 characters, text box text not in its alt text, data visuals without a sort |
| 13 | Done, UNVERIFIED in Desktop | `annotate`, `annotations` on report, pages, visuals; validate checks unique names and pbik.id; adds `pbikit/unverified.py` and `schemaprops.tree_issues` for every later unverified gap |
| 23 | Done (check only) | 260-character path warning (validate, build), August 2026 Desktop minimum (`project check`, `desktop` exit 3), filter-reset note after reload |
