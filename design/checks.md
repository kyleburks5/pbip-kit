# Common defects to check on every review

Seeded from Reps 2-7. Add a line whenever a new defect is found. Name findings by visual ID in review.md.

- Button slicers show no text (the button is too short for the built-in padding)
- Cards or text are clipped at the bottom (the card or text box is below its minimum height)
- A card shows a measure name instead of its label (an empty title was saved as a blank custom title)
- A text box has a white fill on a coloured band
- A table has scrollbars, a hidden last row, or a clipped first column
- Data bars overlap their numbers
- A chart driven by a field parameter shows one bar named after the parameter
- Shadows differ between cards (a missing shadow preset), or a card has a container shadow on top of its own
- Corner radius, border and padding differ between cards
- A leftover container background or border on a card
- Data labels sit in pale boxes, or axis titles show when the wireframe has none
- Stacked-column labels are invisible against the bar colour
- A category label is cut off on a chart axis
- A first-year or blank-comparison state shows "(Blank)" or an empty pill
- Totals do not add up (parts versus the total)
- Page 1 does not open on the intended default selection
- A ranked or status-gated table shows extra blank or "0.00" rows: in DAX a blank counts as less than any number, so a rank or status gate must check ISBLANK first (Rep 4)
- A card's reference line ends in "--" (a reference label with no detail still shows the detail placeholder)
- Data labels in the wrong display unit ("$0.1M" for values under $100K)
- A multi-select button slicer shows every button as selected when nothing is selected
- A ranked list (top/bottom N) shows extra rows, blank values or -100% in a filter state where some members have no rows: test every ranked measure in such a state (Rep 4: Feb 2023 + Electronics), not only the default
- The empty case: pick a member that has rows but nothing to show (Rep 7: a player with attempts but no made shot) and check every card, small multiple, SVG and chart. No "(Blank)", no empty tiles without a message, no broken image; zeros or a clear message instead
- New card small multiples draw no tiles when the category has no rows, so `showBlankAs` never applies (Rep 7)
- Helper or label text wraps to a second line and is clipped by the visual below or beside it (Rep 7)
- A shape draws in the theme's first data colour instead of its token colour (fill set without the `{id: default}` selector, Rep 7)
- A card panel or tile much taller than its content, or a large empty area under the values (Rep 7)
- A chart draws the empty-chart icon (too little room to plot: a title or axis titles in a short visual, Rep 6)
- A two-series bar chart in theme colours instead of the series tokens (selector-less `dataPoint.fill`, Rep 6)
- The tallest column or its label touches the top of the plot (no Y-axis max measure, Rep 6)
- Every visual ID in layout.json is in the report, the wireframe and the spec, once (`audit_ids.py`)
- Every SVG measure is well-formed in every audit state, and the numbers it draws match the measure (`audit_svg.py`, `audit_numbers.py`)
