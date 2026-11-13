Sample design files the kit tests read instead of the project's own (batch 3 item 17): tokens.json and the
pbip-polish.json theme, copies of the kit defaults. /theme rewrites design/tokens.json in a project; the tests keep
working because they never read it. Update these only when the token or theme format changes.
