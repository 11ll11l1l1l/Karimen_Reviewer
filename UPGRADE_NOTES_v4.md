# Build 4.0 upgrade notes

This build is based directly on the supplied Build 3.2 Game+ package.

## Preserved

- all 650 questions
- all 133 question images
- explanations and source references
- A1/B1 bank filters
- progress import/export
- adaptive question scheduling
- exam timer and flagging
- optional Supabase live room/rankings
- Arcade/Cute/Night themes
- WAV sound effects and haptics

## Added

- XP/level progression
- journey/world stages
- fixed daily challenge
- daily challenge streak tracking
- three-life survival mode
- adaptive boss exam
- mistake book
- weak-category weighting in adaptive selection
- expanded achievements
- pass-readiness estimate
- 56 dynamic cat mascot images
- category-specific mascot outfits
- correct/streak/wrong/pleading/comeback/victory mascot states
- browser-spoken mascot lines
- redesigned game HUD and navigation

## Mascot behavior

Repeated wrong answers increment a losing-chain counter. At two consecutive misses the mascot switches to the pleading state. A correct answer after two or more misses produces the comeback state. Correct streaks of 3+ produce the streak state.
