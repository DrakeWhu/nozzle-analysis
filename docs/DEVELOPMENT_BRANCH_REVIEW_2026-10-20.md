# Development branch review — 2026-10-20

Repository: `nozzle-analysis`. Audited base: `912cf1220f35b42f7c51f9eea8b57ca9f071cc65`.
Remote references observed at `2026-10-20T11:41:21.015955+00:00`.

## Evidence scope

Remote heads were fetched into a temporary bare shared clone. Source repositories
were not switched, merged, rebased, or updated with development code. Inspection
used `git show`, `git diff`, `git log`, `git rev-list --left-right --count`,
and `git merge-base --is-ancestor`. Reference acquisition used `git ls-remote
--heads origin` and `git fetch --no-tags origin
'+refs/heads/*:refs/remotes/origin/*'` in the temporary clone. No branch tests,
simulations, scheduler jobs, analysis pipelines, or cleanup commands were run.
The inventory is a dated remote snapshot; findings below cover selected relevant
implementations, not certification of every changed file.

`BASELINE_2026-10-20.md` is preserved byte-for-byte as historical evidence for
the audited base and its recorded Cloud environment. It does not validate these
development tips, future versions, SUNRISE, LYNX, or WarpX execution. Its SHA-256:
`379353c5718bedc6c7f7ea0896df4d7bd3136beb9e3fbab524dd309f2f3b7ce8`.

## Remote branch inventory

Counts are commits unique to the audited base / unique to the remote branch.
A zero branch-only count denotes an ancestor or the identical base, not pending
implementation work. Hashes, rather than moving branch names, identify evidence.

| Remote branch | Commit | Base-only / branch-only |
| --- | --- | --- |
| `main` | `912cf1220f35b42f7c51f9eea8b57ca9f071cc65` | 0 / 0 |

## Verified findings

The remote advertised only `main`, at the same commit as the audited base.
No nozzle development branch was available to inspect in that snapshot.
This does not prove that unadvertised or later work does not exist.

In `src/mna_nozzle_analysis/analysis.py`, numerical objectives are calculated
from carbon-probe samples and Ez field diagnostics. Animation is a separate
optional rendering path (`make_animation=False` by default), not an input to
those objective formulas. The current Lynx configuration nevertheless enables
animation and declares the MP4 as a required reduced output. Thus MP4 absence
can block this profile's workflow validation; animation failure when enabled
can also interrupt the analysis run. Neither is an intrinsic physical
requirement of the numerical objectives. This documentation stage changes no
flag, required output, formula, or validation behavior.

## Cross-repository consequences and possible conflicts

The inspected optimizer N2 contract applies to capillary electron scopes and
exact particle exits. It is not suitable as an automatic replacement for the
nozzle adapter's one-carbon-probe compatibility fields. Multichannel first-row
selection and optional-output evidence behavior remain unchanged at the
inspected optimizer tips. Nozzle's last physical probe sample and its field
peak over 100--300 fs must remain distinct from final-dump or propagation-based
selection policies in the other analysis repositories.

Workflow retention and validated-cleanup branches encode different launch
policies, and new guiding/LFMetrics branches broaden retained-product needs.
None is incorporated or authorized by this documentation commit. No remote
nozzle documentation overlap was found; cross-repository semantic review is
still required before later integration.

The owner must decide whether animation is required QA, workflow-blocking,
cleanup-blocking, optimizer-blocking, or optional in any future profile.
Required Ez diagnostics and sufficient temporal sampling for the physical
objectives are separate questions. Removing the MP4 requirement would need a
reviewed configuration change; this stage only clarifies its current meaning.

## Integration boundary

The current stage is documentation only. No branch implementation, species
selection, objective, temporal policy, scientific-validation rule, or raw
cleanup behavior is adopted. Scientific decisions above remain pending.
Any later integration requires its own version-specific tests and site evidence.
