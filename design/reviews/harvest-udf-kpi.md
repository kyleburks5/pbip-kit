# Clean harvest: udf-kpi-study

Made by `pbik templates harvest --clean`. What was removed and how colours were mapped, per template (property paths and reasons only; no values from the source).

## advancedSlicerVisual.svg-kpi-card-buttons

Removed (9):

- bindings (1): `visual.query`
- name, position, group, filters or flags (3): `filterConfig`, `name`, `position`
- per-field / per-member (3): `objects.image (entry for one field or member)`
- saved selection (1): `objects.general.filter`
- text, image or target (1): `visualContainerObjects.stylePreset.name`

Colours mapped (2):

- theme background, much darker -> `shadow` (1): `objects.fillCustom.fillColor @interaction:hover`
- theme data colour 2 -> `brand` (1): `objects.glowCustom.color @default`

## cardVisual.svg-kpi-card

Removed (9):

- bindings (1): `visual.query`
- name, position, group, filters or flags (3): `filterConfig`, `name`, `position`
- per-field / per-member (3): `objects.image (entry for one field or member)`
- text, image or target (2): `objects.image.imageUrl @default`, `visualContainerObjects.stylePreset.name`

Colours mapped (2):

- theme background, much darker -> `shadow` (1): `objects.fillCustom.fillColor @interaction:hover`
- theme data colour 2 -> `brand` (1): `objects.glowCustom.color @default`
