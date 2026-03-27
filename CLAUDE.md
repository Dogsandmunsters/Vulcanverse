# Vulcanverse Logic Auditor

## Project Goal

Audit 6,115 numbered sections across the Vulcanverse gamebook series (Books 1–5) for structural errors, broken references, and logic-gating issues. The series is an open-world gamebook: players can revisit sections freely, with state tracked via **codewords** and **titles*** (global flags) and **tickboxes** (local per-section visit markers).

## Source Material

The manuscript is split across five files which are located in the Source directory of the repo. Each section is numbered and contains narrative text, choices, and mechanical instructions. Parse using `python-docx`.

### Reference Material
Lists of items, codewords and titles are in the Reference directory of the repo.

## Key Concepts

### Codewords
Named flags the player acquires or loses. Used to gate access to content, track quest progress, and enable/disable options. Codewords are shared across all five books.

- **Book 1 (The Houses of the Dead):** codewords begin with N
- **Book 2 (The Hammer of the Sun):** codewords begin with O
- **Book 3 (The Wild Woods):** codewords begin with P
- **Book 4 (The Pillars of the Sky):** codewords begin with Q
- **Book 5 (Workshop of the Gods):** codewords begin with R

Cross-book codeword references are normal and expected (e.g. Book 5 checking for a Book 1 codeword starting with N). These are NOT errors.

### Tickboxes
A section may contain a tickbox (drawn as an empty square). Instructions tell the player to "tick the box" on their first visit. On revisits, the section branches: "If the box is ticked, turn to X. If not, read on."

Tickbox checks should appear in the same section that contains the tickbox. Flag any tickbox check that references a box in a different section — this needs manual review.

### Current Location
Some sections instruct the player: "Note that your Current Location is [this section number]." Later, other sections may say "Turn to your Current Location." The risk is a path where a player reaches a "Turn to your Current Location" instruction without having previously been told to note one.

## Parsing Grammar

Recognise these patterns (case-insensitive, allowing minor variation):

### Navigation
- `Turn to N` / `► N` / `go to N` — redirect to section N
- `Turn to your Current Location` — redirect to previously noted section

### Codeword Operations
- `If you have the codeword X, turn to N` — conditional gate
- `If you have the codeword X, read on. If not, turn to N` — inverse gate
- `Get the codeword X` / `You now have the codeword X` — acquire codeword
- `Lose the codeword X` / `Delete the codeword X` — remove codeword

### Tickbox Operations
- `Tick the box` / `Put a tick in the box` — mark visited
- `If the box is ticked, turn to N` — visited-branch
- `If this box is empty...` / `If the box is not ticked...` — unvisited-branch

### Other State
- `Note that your Current Location is N`
- Stat checks (e.g. `Make a CHARISMA roll at Difficulty 12`)
- `If you have [item], turn to N`

## Processing Strategy

Context window limitations mean you cannot process all 6,115 sections at once. Work in phases, persisting intermediate results as JSON files.

### Phase 1: Parse & Index
Process each .docx file in chunks. For every section, extract and save to `sections_index.json`:
- Section number
- Source book (1–5)
- All outgoing references (section numbers this section can send you to)
- All codeword operations (check/acquire/lose, with the codeword name)
- All tickbox operations (tick/check-ticked/check-empty)
- Whether it sets Current Location (and to what number)
- Whether it references Current Location as a destination
- Raw text (truncated to first 200 chars for context)

### Phase 2: Structural Validation
Using `sections_index.json`, check for:

1. **Broken references:** Section N refers to section M, but section M does not exist in the index. Report every instance.
2. **Orphan sections:** Sections that exist but are never referenced as a destination from any other section. (Note: each book has a known entry point, so the opening section of each book is not an orphan.)
3. **Dead ends:** Sections with no outgoing references at all — no "turn to" instructions. Some may be legitimate endings (victory/death), but most indicate missing content. Flag all for review.
4. **Circular redirects:** Unconditional chains (A → B → C → A) with no player choice or state change involved.
5. **Codeword spelling consistency:** Cluster codeword names by edit distance. Flag likely typos (e.g. "Doubloon" vs "Doublon").

Save results to `structural_errors.json`.

### Phase 3: Codeword Logic Audit
Build `codeword_map.json`:
- For each codeword: list of sections that grant it, list that remove it, list that check for it.
- For sections that check multiple codewords: record the order of checks and what each branch leads to.

Then check:

1. **Codewords checked but never granted:** A codeword is tested in some section but no section in any book ever grants it. (May indicate a cross-book dependency — flag for review, don't assume error.)
2. **Codewords granted but never checked:** A codeword is given to the player but never tested anywhere. Possible vestigial content.
3. **Shadowing candidates:** In sections that check for two or more codewords related to the same quest line, the more advanced/completion codeword should generally be checked first. If a "progress" codeword is checked before a "completion" codeword, the completion branch may be unreachable. Flag these as candidates for manual review — do NOT assume they are all errors, as the author may have reasons for the ordering.

### Phase 4: Current Location Audit
Trace paths to every section that says "Turn to your Current Location." Verify that all reasonable paths to that section pass through a "Note that your Current Location is N" instruction first. This is inherently a reachability problem and may require heuristic sampling rather than exhaustive proof.

### Phase 5: Tickbox Consistency
For each section containing a tickbox check:
- Verify the tickbox itself exists in the same section.
- Flag any section that checks a tickbox belonging to a different section.
- Verify both branches (ticked/unticked) lead somewhere valid.

## Output Format

All reports should be JSON files with human-readable summaries. Each flagged issue should include:
- Section number and book
- Issue type (broken_ref, orphan, dead_end, spelling, shadowing, etc.)
- Brief description
- Severity: ERROR (almost certainly wrong) vs WARNING (needs manual review)

Final summary report: `audit_report.json` aggregating counts by type and severity, plus a plaintext `audit_summary.txt` for easy reading.

## Important Notes

- **Do not auto-correct anything.** This is an audit, not a repair tool. Report findings for human review.
- **Expect legitimate complexity.** An open-world gamebook with 6,115 sections will have many cross-references, conditional branches, and intentional design patterns that may look unusual. Err on the side of flagging as WARNING rather than ERROR when uncertain.
- **Work incrementally.** Complete each phase fully before starting the next. Confirm results with the user between phases.
- **Persist everything.** Save all intermediate JSON files so work is not lost if a session ends.
