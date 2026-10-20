# Repository guidance: nozzle-analysis

## Scope

- `src/mna_nozzle_analysis/` owns reusable reduction and analysis.
  `examples/lynx/` owns the campaign adapter, PICMI input, and site runners.
- Read the README, `examples/lynx/LAUNCH.md`, and the campaign/optimizer JSON
  contracts before changing outputs or diagnostic settings.
- Preserve the file/configuration boundary with campaign-workflow and
  campaign-optimizer; keep the repositories independently usable.
- Consult `docs/DEVELOPMENT_BRANCH_REVIEW_2026-10-20.md` for the inspected
  remote snapshot and cross-repository contract risks before integration.

## Scientific invariants

- The carbon objective is the longitudinal kinetic-energy gain of the
  non-depositing C12 6+ probe from its initial to its last physical
  ParticleExtrema sample. Do not replace it with total kinetic energy.
- Preserve trailing-empty-sample handling, boundary classification, the
  two-cell default tolerance, sampling-gap metadata, and terminal loss reasons.
- The field objective is the temporal peak of the 99.5th percentile of abs(Ez)
  in the configured exit region and window, reconstructed at theta=0 with all
  dumped RZ modes. The raw maximum is QA, not the objective.
- Preserve the distinction between physical objectives and the summary fields
  used for compatibility with the generic multichannel optimizer.
- The current Lynx profile requires the animation MP4 as a configured output.
  Animation is optional in the library and is not an intrinsic physical
  requirement for evaluating the numerical objectives. Required Ez diagnostics
  supply the field objective independently of video rendering. Do not change
  output requirements or retention policy as a documentation fix.

## Verification

- Use `PYTHONPATH=src python -B -m unittest discover -s tests -p 'test_*.py' -v`
  with the scientific environment, preferably in an isolated export.
- See `docs/BASELINE_2026-10-20.md`. Synthetic NPZ and ParticleExtrema fixtures
  are software tests, not scientific results or real-openPMD validation.
  Keep the baseline as historical evidence, not validation of later revisions
  or SUNRISE/LYNX execution.
- Validate runtime-specific behavior separately on the intended WarpX/LYNX
  stack. Do not launch jobs or remove campaign raw data without authorization.
- Write code, comments, tests, documentation, commits, and PR text in English.
