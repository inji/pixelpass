# pixelpass: local engineering context

Context for contributors and AI agents working in this repository: layout, build and test commands, and the default change
scope. Produced by Crewline module onboarding and reviewed by the module owner.
Every row was **verified** on `upstream/develop` @ `c9e2258d` (2026-11-02) from the file named, unless marked Inferred.
The repository's READMEs (`README.md`, `js/Readme.md`, `kotlin/Readme.md`) win where they are more specific.

| Item | Value | Evidence |
|---|---|---|
| Repository | https://github.com/inji/pixelpass (base branch `develop`) | |
| What it is | Library that encodes VC data into a QR payload (CBOR, zlib, Base45) and decodes it back. Not a service | `README.md` |
| Implementations | JavaScript (`js/`, npm `@injistack/pixelpass` 1.0.0-rc.2) and Kotlin Multiplatform (`kotlin/PixelPass`, Android AAR + JVM JAR). Swift lives in `inji/pixelpass-ios-swift` | `js/package.json:2-3`, `kotlin/Readme.md` |
| Maven | none (no `pom.xml`); the Kotlin side is Gradle | files |
| Gradle | wrapper 8.5, root `kotlin/settings.gradle.kts` (projects `:PixelPass`, `:example-qr-generator`, `:examplejavaapp`; `:app` is included but has no folder) | `kotlin/gradle/wrapper/gradle-wrapper.properties`, `kotlin/settings.gradle.kts` |
| Kotlin / AGP | Kotlin 2.0.0, AGP 8.3.0, compileSdk 33, minSdk 23 | `kotlin/gradle/libs.versions.toml:2-3`, `kotlin/PixelPass/build.gradle.kts` (`android {}`) |
| Java | build needs a **JDK 17 toolchain** (`jvmToolchain(17)`, source/target 17); CI runs Gradle on JDK 21 (`JAVA_VERSION: 21`) | `kotlin/PixelPass/build.gradle.kts` (`kotlin {}`, `compileOptions`), `.github/workflows/push-trigger.yml` |
| Unit-test libraries | Kotlin: kotlin-test, JUnit 4.13.2, MockK 1.13.10. JS: Jest 29, babel-jest | `kotlin/PixelPass/build.gradle.kts` (`commonTest`), `js/package.json` |
| JaCoCo | yes, Kotlin: `jacocoMergedReport` merges `jvmTest` + `testDebugUnitTest`, runs after every test task | `kotlin/PixelPass/build.gradle.kts` (`jacoco {}`, `jacocoMergedReport`) |
| CI workflows | `push-trigger.yml` (Kotlin build on push/PR; Sonar on push; npm publish on manual dispatch), `kotlin-artifacts-build.yml` (manual AAR/JAR publish) | `.github/workflows/` |
| Reusable CI | mosip/kattu @ v0.0.1: gradle-build, gradlew-sonar-analysis, npm-publish-to-npm-registry, maven-publish-android, maven-publish-android-download | workflow `uses:` |
| CI gap | **no CI job runs the JS tests**; PRs only build the Kotlin side | `.github/workflows/push-trigger.yml` (KI-PP-003) |
| DB scripts / Deploy | none (library) | files |
| Repository guidance | `README.md`, `js/Readme.md` (APIs, breaking changes in 0.8.0), `kotlin/Readme.md` (APIs, Gradle/Maven coordinates) | files |
| API / UI tests | none (see `.crewline/qa/module-context.md`) | |

## Projects and tests

| Project | Sources | Tests | Test command | Coverage for diff-coverage | Status |
|---|---|---|---|---|---|
| `js` (`@injistack/pixelpass`) | `js/src/` | Jest, 9 files / 67 tests in `js/test/` | `npm ci`, then `npm test` (`jest --coverage`) | `js/coverage/lcov.info` (Jest default reporters) | **Verified**: 66 passed, 1 failed (KI-PP-001), twice. Evidence `npm-ci`, `npm test` runs |
| `js/example` | `js/example/example.js` | none (`npm start` only) | - | - | demo, not tested |
| `kotlin/PixelPass` | `src/commonMain`, `jvmMain`, `androidMain` (14 files) | `commonTest` 9 (+ helper `IgnoreOnAndroid.kt`), `jvmTest` 4, `androidUnitTest` 2 | `gradlew :PixelPass:jvmTest :PixelPass:testDebugUnitTest` (in `kotlin/`) | `kotlin/PixelPass/build/reports/jacoco/jacocoMergedReport/jacocoMergedReport.xml` | **Inferred**: the run stopped before compiling, no JDK 17 on the onboarding machine (KI-PP-002) |
| `kotlin/example-qr-generator`, `kotlin/examplejavaapp` | example apps | `examplejavaapp`: JUnit 5 setup, no tests | - | - | demo, not tested |

## Commands

Run from the project folder, through `python -m crewline run --repo <worktree> --cwd <worktree>/<project> --out <task>/evidence/<name>.json -- <command>`.

- JS install + tests (Verified): `npm ci` then `npm test`. On Windows call `npm.cmd` (crewline run does not resolve `npm`).
- JS diff coverage (Inferred): `crewline diff-coverage --jacoco js/coverage --include '*js/src/*'`.
- Kotlin tests (Inferred): `gradlew :PixelPass:jvmTest :PixelPass:testDebugUnitTest`; `jacocoMergedReport` runs after them.
  Needs JDK 17 installed (Gradle finds it) and the Android SDK in `kotlin/local.properties` (`sdk.dir=...`, gitignored) or
  `ANDROID_HOME`. On Windows pass the full path of `gradlew.bat`.
- Kotlin build (Inferred): `gradlew :PixelPass:assembleRelease :PixelPass:jvmJar` (what `jarRelease` depends on, minus Dokka).
- Coding standards: none found (no ktlint/detekt/eslint/prettier config); `kotlin.code.style=official` only
  (`kotlin/gradle.properties`) → `crewline coding-standards` checks debug leftovers only.

## Consumers (linked repositories)

A change to the QR data format or a public API affects these; they get their own task, branch and PR, after this one is released.

| Consumer | Uses | Evidence (in that repository) |
|---|---|---|
| inji-verify | npm `@injistack/pixelpass` ^0.8.0-RC2 (`inji-verify-sdk`, `verify-ui`); `pixelpass-jar` 0.8.0 (`verify-core`) | `inji-verify-sdk/package.json`, `verify-ui/package.json`, `pom.xml` |
| mimoto | `pixelpass-jar` | `pom.xml` |
| inji-certify | `pixelpass-jar` | `certify-service/pom.xml` |

## Default approved paths (the plan narrows them per task)

- JS: `js/src/**`, `js/test/**`; `js/package.json` and `js/package-lock.json` for dependency tasks
- Kotlin: `kotlin/PixelPass/src/**`; `kotlin/gradle/libs.versions.toml` for dependency tasks
- Docs: `README.md`, `js/Readme.md`, `kotlin/Readme.md` when an API changes
- Sensitive, always `scope_change`: `.github/**`, `kotlin/**/*.gradle*`, `kotlin/PixelPass/publish-artifact.gradle`, `kotlin/gradle/wrapper/**`, version fields (`js/package.json` `version`, Gradle publish versions)

## Open (owner to confirm)

- Node version for development and publishing (not pinned: no `engines` or `.nvmrc`; onboarding used Node 20.20.2).
- Whether to add a JS test job to CI (KI-PP-003) — a separate task.
- Coverage threshold if the team's standard differs from 80%.
