# Engineering decisions

- Scope: Record external administration, long/paid campaigns and optional research extensions as blocked/unverified rather than inventing credentials, results or unsupported integrations.
- Failure completion: Infrastructure/cache errors leave an arm resumable after other rounds and arms finish; failed generation is never silently marked complete.

- C13: Reports generate portable HTML and SVG without plotting dependencies, with seed-mean feedback learning curves and the same arm-summary metrics in Markdown and HTML.

- C12: Bugcheck evaluates saved arm/seed suites against a reverse-patched disposable snapshot, refuses synthetic/changed targets, and requires stable failure evidence (verification record v2).

- C11: Versioned arm summaries bootstrap held-out scores across seeds with a fixed RNG; fewer than two seeds and zero-denominator rates remain undefined.

- C10: Estimate is offline config arithmetic with a hard API cap and explicitly assumption-based timeout-scaled time, excluding unknown startup/triage costs.

- B9: Doctor probes engine availability with a ten-second limit and reports dependency/key presence and free disk; structured run events omit prompts, keys and exception bodies.

- B8: Config v3 rejects nonfinite costs/timeouts, empty paths and out-of-range seeds/work limits; bound Git/image inspection and fix container hash seeding while retaining container CPU/memory/PID limits.

- B7: Retry transient provider/container failures at most three times with exponential backoff and fresh spend reservations; isolate round/arm errors and preserve partial runs.

- A6: Lock v2 stores host and PID; only verified-dead local owners are reclaimed under an exclusive acquisition guard, while legacy/foreign/ambiguous locks remain blocked.

- A5: Audit combines licence evidence and source size with an initial isolated suite plus three reruns; licence approval remains explicit human review.

- A4: Matrix runs have one folder and dollar cap per repository/arm/seed tuple; manifest v2 explicitly records config hash alongside target and Helia commit provenance.

- A3: Export rerun-verified bug leads as standalone pytest repro modules; minimization removes unrelated tests without claiming globally minimal inputs.

- A2: Config v2 adds a persistent run-wide dollar cap; replay is the default, dry-run only validates configuration, and paid calls require both --live and the key.

- A1: Retain metered CoverUp import; automatic paid launch is blocked until a version-pinned spend-enforcing gateway exists (upstream CLI has concurrency/rate limits but no monetary cap).
