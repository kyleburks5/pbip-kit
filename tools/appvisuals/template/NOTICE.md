# Notices

The pbip-kit app-visual template started from Microsoft's Dot Plot visual
(https://github.com/microsoft/powerbi-visuals-dotplot, commit e56f099): its IVisual shape, formatting-model cards,
selection behaviour (click, Ctrl-click, clear, context menu, keyboard) and capabilities layout. Files that carry code
adapted from it say so at the top. Its licence:

> Power BI Visualizations
>
> Copyright (c) Microsoft Corporation
>
> All rights reserved.
>
> MIT License
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
> documentation files (the ""Software""), to deal in the Software without restriction, including without limitation
> the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
> permit persons to whom the Software is furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of
> the Software.
>
> THE SOFTWARE IS PROVIDED *AS IS*, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
> WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS
> OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
> OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Bundled into every build (`pbik visual build`), from the kit tools folder:

| Package | Version | Licence | What |
| --- | --- | --- | --- |
| d3 (d3-selection, d3-scale, d3-array, d3-timer, d3-interpolate, d3-force, d3-quadtree, d3-zoom, d3-brush) | 7.9.0 | ISC, Copyright Mike Bostock | drawing, motion, physics, interaction |
| d3-ease | 3.0.2 | BSD-3-Clause, Copyright Mike Bostock (easing equations: Robert Penner, BSD) | easing |
| powerbi-models | 2.2.0 | MIT, Copyright Microsoft Corporation | filter mode (BasicFilter) |
| powerbi-visuals-utils-formattingmodel, -formattingutils | 6.2.2, 6.1.2 | MIT, Copyright Microsoft Corporation | formatting pane, number formats |
| @fontsource/inter (Inter latin 400 and 600) | 5.3.0 | SIL Open Font License 1.1, Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter) | the bundled font |

A visual that imports more adds them to its own handoff pack (`pbik visual handoff` lists every package it imports
with its licence): flubber (MIT), topojson-client and us-atlas / world-atlas (ISC), d3-flextree (WTFPL), d3-geo
(ISC), three (MIT).

The icons (src/kit/icons.ts) are drawn by the kit. The kit's own code in this folder is MIT like the Dot Plot.

SIL Open Font License 1.1 (Inter): the font may be bundled, embedded and redistributed with software, and may not be
sold by itself; the full text is at https://openfontlicense.org and in the @fontsource/inter package (LICENSE).
