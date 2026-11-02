# pixelpass: SDET context

pixelpass is a library, so its automated tests are unit tests that ship with each implementation. There is no API TestRig
(`api-test/`), no UI TestRig and no coverage matrix: `crewline testcase`, `expected-diff`, `scope` and `coverage` return NOT_RUN
here, and no `profile.yaml` exists.

| Implementation | Tests | Runner | Command (see `development/local-context.md`) |
|---|---|---|---|
| JavaScript `js/` (`@injistack/pixelpass`) | `js/test/*.test.js`, 9 files, 67 tests | Jest 29 + babel-jest | `npm ci` then `npm test` in `js/` |
| Kotlin `kotlin/PixelPass` (`pixelpass-aar`, `pixelpass-jar`) | `src/commonTest` (9 files), `src/jvmTest` (4), `src/androidUnitTest` (2) | kotlin-test, JUnit 4, MockK | `gradlew :PixelPass:jvmTest :PixelPass:testDebugUnitTest` in `kotlin/` |
| Swift (iOS) | separate repository `inji/pixelpass-ios-swift` | - | out of scope here |

## What a change must re-run

- A change to `js/src/**`: the Jest suite. Acceptance tests for a new or changed API go in `js/test/`, one file per API
  (`generateQRCode.test.js`, `decode.test.js`, ...).
- A change to `kotlin/PixelPass/src/commonMain/**`: both `jvmTest` and `testDebugUnitTest` (common code runs on both targets).
  A change to `jvmMain` or `androidMain` needs at least its own target's tests.
- A behaviour change in one implementation: check whether the other one (and the Swift repository) must change too. The
  three implementations share one QR data format; the READMEs document the same APIs.
- System test / regression: there is no environment of its own. Released artifacts are consumed by inji-verify, mimoto and
  inji-certify (`development/local-context.md`, "Consumers"); a format or API change is regression-tested by building a
  consumer against the new version (Inferred: no automated cross-repo check exists).

Known failures at onboarding are in `known-issues.md`; validate only what a change touches.
