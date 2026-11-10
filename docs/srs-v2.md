# Helia SRS v2: repository-scale automated testing

## Objective

Compare failure-guided test generation against an existing repository suite, independent
one-shot LLM generation and CoverUp at equal generation budgets. Use pure-Python
repositories with approximately 1,000-10,000 source lines. Training or fine-tuning models
is outside this implementation.

## Required invariants

1. Seeded, capped mutation sampling spans files and functions.
2. Feedback and held-out partitions are disjoint and identical across arms for each seed.
3. Generation and policy never consume held-out results or mutated source.
4. Target code executes only in resource-limited, network-off Docker workers.
5. Original and selected-subset tests must pass before mutant failures count as evidence.
6. Invalid, flaky and infrastructure failures remain distinguishable from real bug leads.
7. LLM requests are cached by provider, model, prompt and settings; spend is recorded.
8. Every run records configuration, source fingerprint, target commit, implementation
   fingerprint, runner image ID, seeds, generated tests, outcomes and metrics.
9. Resuming must reject changes to inputs or the runner image.
10. Fake execution is explicitly synthetic and cannot produce research verdicts.

## Interfaces

`contracts/models.py` defines schema-version-1 records; `contracts/schemas/` contains
generated JSON Schema. Producers reject unknown fields. M1 supplies `RepoIndex`, M2
supplies `Mutant`, M3 supplies `ExecResult`, M4 supplies `Failure`, M5/LLM supplies
`LLMResponse`, M8 supplies `Metrics`, and M9 supplies `BugLead`.

## Evaluation

H1 compares held-out mutation score with one-shot and repository baselines. H2 examines
unique failure discoveries per round. H3 compares coverage gain. H4 compares policy
trajectories and a random ablation. H5 compares held-out kills per dollar with CoverUp.
Paired seed estimates are reported without claiming success when results are null,
inconclusive, synthetic or insufficient. Untested/infrastructure/timeout counts remain
available alongside mutation scores. No zero-cost division is represented as infinity.

## Delivery gates

- Foundation: dependency lock, contracts, fakes, CI and synthetic end-to-end execution.
- Ground truth: Docker verified, three qualified pinned targets, reproducible baseline scores.
- Generators: live generation and metered external CoverUp artifacts validated.
- Guided loop: budgeted feedback policy, triage and historical-fix verification.
- Experiments: frozen reviewed source/configuration, three targets, at least ten seeds.
- Report: completed measured runs, hypothesis interpretation, limitations and reproduction.

The implementation ledger records which gates have local evidence and which still need
infrastructure or experiment inputs. Team ceremonies, GitHub permissions and external
publication are not inferred from the source document as authorizations to contact people.

