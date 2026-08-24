---
name: math-workflow-methodology
description: "General methodology for AI-assisted math modeling work: six-phase pipeline with an Evidence Gate that blocks hallucinated or hand-edited results. Reusable in any environment."
---

# AI Math-Modeling Workflow (methodology)

## Core idea

Run a math modeling task as a **six-phase pipeline**:

```
read → model → solve → visualize → paper → verify
(P1)   (P2)    (P3)     (P4)        (P5)    (P6)
```

Every artifact produced by a phase is **hashed (SHA-256) into a run manifest**
(`run_manifest.json`, backed by an append-only `run_log.jsonl`), together with
the exact command that produced it and its exit code. Before any phase starts,
the pipeline **re-hashes the previous phase's artifacts and compares them to the
manifest**. If a hash differs — a file was hand-edited, regenerated, or replaced —
the gate fails and the pipeline **refuses to advance**. No gate, no advancement.

The manifest is the single credential for stage advancement. Any number that ends
up in the final paper must be traceable to a recorded real run.

## Why it matters

AI-generated contest papers (and AI-assisted scientific reports in general) are
easy to produce and equally easy to fake. A model asked to "fill in the result"
will happily hallucinate plausible numbers. The Evidence Gate makes fabrication
**structurally impossible rather than merely discouraged**:

- Every figure, result file, and source file is hashed at the moment it is produced.
- Any manual tweak to a result (e.g., editing a number in a JSON output to make
  the paper look better) is detected the next time the gate runs.
- Reviewers and judges can audit the whole chain: artifact → hash → command → exit code.

In a human-in-the-loop contest setting, this matters doubly: the AI accelerates
the work, the human stays in control of modeling decisions, and **traceability
guarantees that the delivered paper reflects genuinely executed code**.

## Reusable parts

1. **`run_manifest.json` schema** — per-stage snapshot:
   `artifact_path → {sha256, size, mtime}` plus `last_cmd` and `exit_code`.
2. **Append-only log (`run_log.jsonl`)** — one JSON record per run, ordered by
   timestamp; the source of truth from which the snapshot is rebuilt.
3. **Gate check flow** — before starting stage *N*, verify stage *N-1*:
   - required outputs exist (per-stage glob patterns);
   - their current SHA-256 matches the recorded hashes;
   - recorded `exit_code == 0`;
   - otherwise return non-zero and **do not advance**.
4. **Phase checklist templates (P1–P6)** — each phase defines
   *goal / inputs / operations / deliverables / acceptance criteria / HIL pause point*.
5. **Human-in-the-loop checkpoints (HIL)** — the pipeline pauses at every
   decision-critical moment (problem understanding, model assumptions, key numeric
   results, final paper) and asks the human to confirm before proceeding.

## Workflow details

### Environment & project layout (generalize to any project)

- One directory per problem (`solve/<problem>/`); all outputs live under its
  `output/` subdirectory.
- The `output/` layout is fixed: `analysis/`, `code/`, `figures/`, `paper/`,
  `acceptance_report.md`, `run_manifest.json` (snapshot) and `run_log.jsonl`
  (append-only log).
- All Python invocations use **the project's Python interpreter** (a dedicated
  virtual environment), never a bare system `python`, to avoid PATH surprises.
- LaTeX compilation uses the configured LaTeX toolchain (e.g., `xelatex`/`latexmk`
  from a system TeX distribution such as MiKTeX); the exact paths are environment
  configuration, not part of the methodology.
- If a path may contain spaces, always quote it in shell commands; in Python, use
  `pathlib`.
- Before starting, run an environment self-check (read-only) and abort if anything
  fails: interpreter present, LaTeX template present, required Python packages
  importable.

### The Evidence Gate (mandatory)

- **End of a stage** — record the run:
  ```bash
  python make_manifest.py record <problem_dir> <stage> \
      --inputs a.csv,b.docx --outputs code/result_q1.json,code/solve.py \
      --cmd "<the full command that ran>" --exit-code <exit_code>
  ```
  This appends one line to `run_log.jsonl` and updates the `run_manifest.json`
  snapshot with the output hashes.
- **Start of a stage** — verify the previous stage's gate:
  ```bash
  python verify_manifest.py gate <problem_dir> <stage>
  ```
  A non-zero exit means the gate **failed**; do not proceed. Fix the discrepancy
  (regenerate the artifact, or re-record honestly) before continuing.
- The manifest is **append-only**; records are never rewritten in place. This
  makes the pipeline tamper-evident by construction.

### Phase templates (P1–P6)

Each phase follows the same template: **goal / inputs / operations / deliverables /
acceptance criteria / HIL pause**.

#### P1 — Read (→ `analysis/problem_summary.md`)
- **Goal**: fully understand the problem; decompose into sub-questions Q1..Qn.
- **Operations**: extract text from the statement (DOCX/PDF); if a scanned PDF has
  no text layer, use an OCR/vision path and tell the user explicitly — never
  silently guess. Run a quick EDA on every data file (column names, units,
  missing values, anomalies). For each sub-question, list goal, constraints,
  inputs, outputs, and every parameter. Write `analysis/problem_summary.md`
  (background, data dictionary, parameter list, sub-question statements).
- **Deliverables**: `analysis/problem_summary.md`.
- **Acceptance**: every sub-question has a verbal goal+constraint description;
  every column/unit is explained; every parameter is listed.
- **HIL**: ⏸ restate the problem understanding to the user; proceed only after
  confirmation.

#### P2 — Model (→ `analysis/model_spec.md` + `analysis/symbols.md`)
- **Goal**: formalize the word problem into a mathematical model.
- **Operations**: choose methods from a method matrix (optimization / prediction /
  evaluation / clustering / mechanism), preferring simple over advanced unless
  justified. For combinatorial/optimization problems, reuse a solver skeleton
  (data structures, cost function, greedy construction, local search). Write
  decision variables, objective, constraints; number the model assumptions in
  strict, testable mathematical language. Maintain a symbol table
  (`analysis/symbols.md`). In `model_spec.md`, give each sub-question a complete
  model plus a **comparison table of at least two candidate approaches**
  (algorithm / core logic / difficulty / pros+cons / novelty, with the chosen one
  marked and justified).
- **Deliverables**: `analysis/model_spec.md`, `analysis/symbols.md`.
- **Acceptance**: every sub-question has a complete model (variables / objective /
  constraints); assumptions are testable; method choice is justified.
- **HIL**: ⏸ confirm model and assumptions before P3.

#### P3 — Solve (→ `code/solve_q*.py` + `code/result_q*.json/.txt`)
- **Goal**: obtain reproducible, real results.
- **Operations**: write self-contained solvers `code/solve_q1.py`, `solve_q2.py`,
  … (CP-SAT for combinatorial; greedy + local search for heuristics; regression /
  scipy for prediction). Run each solver → machine-readable `code/result_q*.json`
  + human-readable summary `code/result_q*.txt`. For iterative algorithms
  (bisection, sweeping, convergence), **record every iteration inside the result
  JSON** (step, candidate value, feasibility, interval/step, intermediates) so the
  process itself is presentable evidence. For parameter sweeps: coarse scan to
  locate, then refine the peak window until results stabilize, keeping all levels
  archived. After every run, **record evidence** (see Evidence Gate).
- **Deliverables**: `code/*.py`, `code/result_q*.json`, `code/result_q*.txt`.
- **Acceptance**: exit code 0; result JSON contains key metrics; P3 is recorded in
  the manifest.
- **HIL**: ⏸ show the key numeric results; proceed only after the user confirms
  they are reasonable.

#### P4 — Visualize (→ `figures/*.png`)
- **Goal**: publication-grade figures.
- **Operations**: use a shared figure style (paper palette, 300 dpi, complete
  titles/units/captions). Every key judgment/critical value/extreme value gets a
  figure or iteration table — zero-crossing plots, extreme/distribution plots with
  peaks marked, convergence tables, effect/bias plots — with data taken from the
  result JSON iteration history. Produce a pipeline/tech-route diagram. Run a
  programmatic figure check (decodable / non-blank / reasonable size) and fix any
  damaged or blank figure before proceeding. Review every figure against the
  check report and the solve results, and write the review conclusion into notes.
- **Deliverables**: `figures/*.png` (300 dpi) + diagram sources + `figures/check_report.json`.
- **Acceptance**: every figure passes the programmatic check; the pipeline diagram
  exists; review conclusions are written down.
- **HIL**: none mandatory (folded into P5).

#### P5 — Paper (→ `paper/main.tex` + `paper/main.pdf`)
- **Goal**: compile a submittable PDF.
- **Operations**: copy the class/template file into `output/paper/`. Write
  `main.tex` following the paper-structure and layout norms (abstract on its own
  page, page limits, title font, first-line indents, centered figures/tables/
  equations, numbered equations, three-line tables, figure references, GB/T 7714
  references). Insert the P4 diagrams with `\ref` cross-references; **numbers in
  figures must match the body text and the result JSONs**. Each question's
  "solve" section carries an iteration table; results/analysis carry comparison
  tables (approach comparison, cross-validation against literature values).
  References must be real and verifiable — search the literature, verify DOI/arXiv
  before formatting; **never fabricate citations**. Write the abstract last, with
  concrete numeric results, iterated ≥3 times. If AI was used, include the
  required AI-usage disclosure statement. Compile and check (`latex_check`:
  zero fatal errors, no undefined ref/cite, overfull within threshold). Optionally
  also emit a full Word version via pandoc (editable OMML math).
- **Deliverables**: `paper/main.tex`, `paper/main.pdf`.
- **Acceptance**: zero fatal compile errors; no undefined refs/cites; overfull
  within threshold; Word version generated (if required).
- **HIL**: ⏸ user reviews the full paper before delivery.

#### P6 — Verify (→ `acceptance_report.md`)
- **Goal**: automated acceptance of the whole pipeline.
- **Operations**: run an acceptance script that checks: completeness / text leakage
  and placeholders (including internal-file leaks) / numerical consistency (paper
  vs result JSONs) / figure-reference completeness (referenced figures must pass
  quality checks) / LaTeX compiles / model is formalized / paper elements complete
  / format norms (page counts) / code reproducible / figure quality (all figures
  pass checks, pipeline diagram exists) / PDF visual sanity (render pages, none
  blank, page count matches).
- **Failure handling**: for any failed check, fix against the acceptance checklist
  and norms, then rerun until all green.
- **HIL**: ⏸ final confirmation before delivery.

### HIL checkpoints summary

| Phase | Pause point |
|---|---|
| P1 | Restate problem understanding — confirm |
| P2 | Confirm model & assumptions |
| P3 | Show key numeric results — confirm plausibility |
| P4 | (none, folded into P5) |
| P5 | Full-paper review before delivery |
| P6 | Final confirmation before handover |

### Compliance red lines

- **Every number in the paper must be traceable** to a recorded real run in
  `run_manifest.json` (guaranteed by the Evidence Gate).
- AI usage must be disclosed truthfully per the contest's rules.
- Core modeling decisions stay with the human; the AI accelerates implementation.
