# Generation 2 Phase 6 CI classification

The authorization commit `51f077cc5acddd02a231567088f70a3c7bdb7d36` did **not** achieve a green full-repository test workflow. This report does not relabel that workflow as green.

The failed workflow was `tests` run **35718227521** (run number 411). Inspection of the failed job shows the same legacy Phase-4 GitHub-runner evidence problem already observed before Generation 2: pinned experiment evidence under `results/experiments/` and normalized Phase-3 cache metadata under `data/cache/phase3/` are absent on the hosted runner. Representative errors are `pinned source is not a regular file`, `INPUT_IDENTITY_MISMATCH: pinned input missing`, and missing `data/cache/phase3/normalized/.../metadata.json`.

On the same exact authorization commit, the dedicated Generation-2 holdout-selection audit, Phase-6 independent audit, Phase-6 preseal static gate, and Generation-2 synthetic rehearsal gate all completed successfully.

Classification: **legacy CI environment / missing-fixture limitation; no Generation-2 regression identified**. The red full-suite result remains an explicit open limitation and is not waived or rewritten as a pass. Generation-2 acquisition may rely only on the dedicated fail-closed gates and the committed authorization-artifact verifier. No holdout history was accessed during this classification.
