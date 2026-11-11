# Engineering decisions

- B9: Doctor probes engine availability with a ten-second limit and reports dependency/key presence and free disk; structured run events omit prompts, keys and exception bodies.

- B8: Config v3 rejects nonfinite costs/timeouts, empty paths and out-of-range seeds/work limits; bound Git/image inspection and fix container hash seeding while retaining container CPU/memory/PID limits.

- B7: Retry transient provider/container failures at most three times with exponential backoff and fresh spend reservations; isolate round/arm errors and preserve partial runs.

- A6: Lock v2 stores host and PID; only verified-dead local owners are reclaimed under an exclusive acquisition guard, while legacy/foreign/ambiguous locks remain blocked.

- A5: Audit combines licence evidence and source size with an initial isolated suite plus three reruns; licence approval remains explicit human review.

- A4: Matrix runs have one folder and dollar cap per repository/arm/seed tuple; manifest v2 explicitly records config hash alongside target and Helia commit provenance.

- A3: Export rerun-verified bug leads as standalone pytest repro modules; minimization removes unrelated tests without claiming globally minimal inputs.

- A2: Config v2 adds a persistent run-wide dollar cap; replay is the default, dry-run only validates configuration, and paid calls require both --live and the key.

- A1: Retain metered CoverUp import; automatic paid launch is blocked until a version-pinned spend-enforcing gateway exists (upstream CLI has concurrency/rate limits but no monetary cap).
