# Engineering decisions

- A4: Matrix runs have one folder and dollar cap per repository/arm/seed tuple; manifest v2 explicitly records config hash alongside target and Helia commit provenance.

- A3: Export rerun-verified bug leads as standalone pytest repro modules; minimization removes unrelated tests without claiming globally minimal inputs.

- A2: Config v2 adds a persistent run-wide dollar cap; replay is the default, dry-run only validates configuration, and paid calls require both --live and the key.

- A1: Retain metered CoverUp import; automatic paid launch is blocked until a version-pinned spend-enforcing gateway exists (upstream CLI has concurrency/rate limits but no monetary cap).
