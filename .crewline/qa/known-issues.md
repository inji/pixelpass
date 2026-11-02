# pixelpass: known issues and baseline debt

Recorded at module onboarding (2026-11-02) on `upstream/develop` @ `c9e2258d` so later changes are validated only for what they
change. Baseline: JS Jest suite 66/67 passed (twice); Kotlin unit tests not run (KI-PP-002). No API TestRig, so no validator
profile baseline.

| ID | Issue | Status | Evidence | Impact / action |
|---|---|---|---|---|
| KI-PP-001 | Jest `generateQRCode › supports all ECC levels` exceeds the default 5 s timeout: it generates 4 QR images in one test | Verified | `js/test/generateQRCode.test.js:15`; fails in 2 of 2 full runs; passes with `--testTimeout=30000` in 10.7 s | Timing debt, not a functional failure. A JS change is judged on the other 66 tests plus its own; do not count this as a regression. Not fixed during onboarding |
| KI-PP-002 | Kotlin build requires a JDK 17 toolchain and has no toolchain download repository; a machine with only JDK 21 cannot compile | Verified | `kotlin/PixelPass/build.gradle.kts` (`jvmToolchain(17)`); Gradle: "No matching toolchains found ... languageVersion=17" | Install JDK 17 locally before running Kotlin tests. CI uses JDK 21 for Gradle (`push-trigger.yml`) and gets 17 from the runner (Inferred) |
| KI-PP-003 | No CI job runs the JS tests; PR checks cover only the Kotlin build | Verified | `.github/workflows/push-trigger.yml` (jobs `publish-pixelpass-to-npm-registry` on manual dispatch only, `build-kotlin`, `sonar_analysis`) | JS changes need local test evidence (`npm test`) in the task; a CI job is a separate task |
| KI-PP-004 | `npm ci` in `js/` reports 16 vulnerabilities (7 low, 2 moderate, 7 high) | Verified | `npm ci` output, 2026-11-02 | Dependency debt for a `dependency-upgrade` task; not a gate for unrelated changes |
| KI-PP-005 | `kotlin/settings.gradle.kts` includes `:app`, which has no folder | Verified | `kotlin/settings.gradle.kts` | Harmless (Gradle creates an empty project); informational |
