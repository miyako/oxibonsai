# oxibonsai for 4D

[Overview](https://miyako.github.io/oxibonsai/) | [Integration guide](https://miyako.github.io/oxibonsai/guide.html)

Run the [OxiBonsai](https://github.com/cool-japan/oxibonsai) local HTTP server from **4D 20+**.
This repository is the MIT-licensed 4D component and its build/packaging integration,
not the upstream inference engine. The upstream Rust engine is Apache-2.0 licensed.

The documentation site follows the [shared local inference site design](https://github.com/miyako/local-inference-site-design/blob/main/SITE-DESIGN.md),
with oxibonsai's own branding and capabilities. Preview it with
`bundle exec jekyll serve --destination .build/site` and open
`http://127.0.0.1:4000/oxibonsai/`. Check the overview and guide in light and dark
mode at desktop and mobile widths when changing the layout or styles.

## Installation and targets

Download a component from [Releases](https://github.com/miyako/oxibonsai/releases),
install the `.4dbase` in your application's `Components` folder, and restart 4D.
Source projects declare the `miyako/tcp`, `miyako/workers`, and `miyako/event`
dependencies in `oxibonsai/Project/Sources/dependencies.json`; resolve these with
4D's dependency manager when using the source project.
Model weights are **not included** and require separate disk space and RAM.

| Component target | Resource executable | Build features |
|---|---|---|
| macOS Apple Silicon | `Resources/bin/macOS/oxibonsai` (universal) | `server,metal` |
| macOS Intel | same universal executable | `server` (CPU) |
| Windows x64 | `Resources/bin/Windows/oxibonsai.exe` | `server` (CPU) |
| Windows ARM64 | `Resources/bin/WindowsARM/oxibonsai.exe` | `server` (CPU) |

No Linux component or CUDA-enabled executable is packaged here. Upstream's optional
CUDA, RAG, and other CLI capabilities are not promises of this component's builds.
The wrapper chooses a bundled executable for the current platform, or falls back to
`oxibonsai` on `PATH` when that file is absent.

## Use from 4D

The example downloads the Bonsai GGUF if needed, then starts the server on
`http://127.0.0.1:8080`. Use a tokenizer matching your model; the bundled
`Resources/models/tokenizer.json` is the fallback, not a universal tokenizer.

```4d
var $oxibonsai : cs.oxibonsai
var $homeFolder; $modelFolder : 4D.Folder
var $huggingface : cs.event.huggingface
var $huggingfaces : cs.event.huggingfaces
var $event : cs.event.event
var $options : Object

$homeFolder:=Folder(fk home folder).folder(".GGUF")
$modelFolder:=$homeFolder.folder("Bonsai")

$event:=cs.event.event.new()
$event.onError:=Formula(ALERT($2.message))
$event.onSuccess:=Formula(ALERT($2.models.extract("name").join(",")+" started"))
$event.onData:=Formula(MESSAGE(This.file.fullName+":"+String((This.range.end/This.range.length)*100; "###.00%")))
$event.onResponse:=Formula(MESSAGE(This.file.fullName+":download complete"))
$event.onTerminate:=Formula(LOG EVENT(Into 4D debug message; "oxibonsai process terminated"))

$options:={host: "127.0.0.1"; max_seq_len: 8192; pool_size: 1; \
max_concurrent_requests: 4; request_timeout_ms: 60000}

$huggingface:=cs.event.huggingface.new($modelFolder; "prism-ml/Bonsai-8B-gguf"; ["Bonsai-8B.gguf"])
$huggingfaces:=cs.event.huggingfaces.new([$huggingface])
$oxibonsai:=cs.oxibonsai.new(8080; $huggingfaces; $homeFolder; $options; $event)
```

`onSuccess` currently means the worker was started, **not** that model loading
or an HTTP readiness check succeeded. Check `GET /health` before sending requests;
loading a large model can take time. Call `$oxibonsai.terminate()` to stop the worker.

### Options and API

Options use underscores; the wrapper converts them to CLI hyphens. The model
downloader supplies `model` as a `4D.File`. Optional `tokenizer` must also be a
`4D.File`; omitting it selects the bundled tokenizer.

| 4D option / CLI flag | Upstream default / meaning |
|---|---|
| `host` / `--host` | `127.0.0.1` |
| constructor port / `--port` | `8080` |
| `max_seq_len` / `--max-seq-len` | `4096`, prompt plus generation context |
| `pool_size` / `--pool-size` | CPU: min(4, cores); GPU/Metal clamped to 1 |
| `max_concurrent_requests` / `--max-concurrent-requests` | `32`; excess requests return 503 |
| `request_timeout_ms` / `--request-timeout-ms` | `60000`; timed-out requests return 408 |
| `bearer_token` / `--bearer-token` | Unset: no authentication |
| `config` / `--config` | Optional upstream TOML config (observability settings; not a substitute for server flags) |

Keep the loopback binding unless you deliberately configure network access.
`bearer_token` is forwarded to the server; clients must send
`Authorization: Bearer <token>`. Upstream also accepts `OXIBONSAI_BEARER_TOKEN`
from the environment, avoiding a token in process arguments. `/health` and
`/metrics` are exempt from bearer authentication; admin endpoints are not.
The CLI loads `.env` from its working directory or parents; explicit flags take
precedence over the supported environment defaults. In this upstream revision,
`serve` does not apply the TOML server settings; use the explicit flags above.
Do not put secrets in this repository.

For 4D AI Kit's OpenAI-compatible provider, use base URL
`http://127.0.0.1:8080/v1`, the model ID returned by `GET /v1/models`, and
the same bearer token if configured.

| API | Component's `oxibonsai serve` |
|---|---|
| `GET /v1/models` | Available |
| `POST /v1/chat/completions` | Available, including streaming upstream |
| `POST /v1/completions` | Available upstream |
| `POST /v1/embeddings` | Available, but uses TF-IDF/byte-hash vectors, not Bonsai model embeddings |
| Images, files, moderations | Not exposed by this server entry point |

Upstream's separate image CLI and `oxibonsai-serve` binary are not used by this wrapper.
The embeddings endpoint accepts but ignores the requested model name; do not
treat its lexical vectors as learned semantic embeddings from the loaded GGUF.

## Reproducible source builds

As checked on **2026-11-02**, upstream's latest release is **v0.2.3**
(published 2026-07-22); its `master` HEAD and the dereferenced tag both resolve to
**`1d10c48e14754ff6999158f8fa13c7c92b40b0dc`**, committed
**2026-07-22 09:54:07 UTC**. The existing bundled executables already report
0.2.3, but have no recorded build provenance; this update establishes a
source-built packaging path rather than claiming a newer upstream version.

[`upstream.json`](https://github.com/miyako/oxibonsai/blob/main/upstream.json) pins the commit, package **`oxibonsai-cli`**,
binary **`oxibonsai`**, target features, and **Rust 1.99.0**. Upstream declares
Rust >=1.86, but its source repository does not track `Cargo.lock`; this repository
supplies a resolved lockfile and uses `--locked` with a pinned newer compiler.
No upstream prebuilt executables are downloaded. Reproducibility here means pinned
source/dependencies/toolchain/features, not a guarantee of byte-identical binaries
across different SDK or linker versions.

Install Python 3.12+, Git, rustup, CMake, and a native C/C++ toolchain (Xcode
command-line tools on macOS; Visual Studio C++ Build Tools and Windows SDK on
Windows). The resolved TLS dependency includes `aws-lc-sys`, so this build is not
C-toolchain-free even though the inference engine is Rust. On a matching
native host, for example Apple Silicon:

```sh
rustup toolchain install 1.99.0 --profile minimal --target aarch64-apple-darwin
python3 scripts/build-server.py --target aarch64-apple-darwin
python3 -m unittest discover -s scripts/tests -v
```

Use the corresponding target triple from `upstream.json` on each other host.
The script fetches the exact commit, checks the source is clean, copies the
lockfile, builds release mode with explicit features, checks `--version` and
`serve --help`, and writes the executable plus SHA-256 provenance to
`.build/server/artifacts/<target>/`. It refuses inherited `RUSTFLAGS` and
`CARGO_ENCODED_RUSTFLAGS`. Windows builds explicitly set the recorded
`-C target-feature=+crt-static` so the VC runtime is not an unbundled prerequisite.
For an update, change the pin intentionally, regenerate `Cargo.lock` using the
pinned Rust toolchain against that source, and rerun all four native builds.
Use a fresh `--work-dir` when changing the source pin.

The [source-build workflow](https://github.com/miyako/oxibonsai/blob/main/.github/workflows/build-server.yml) runs on native
macOS ARM/Intel and Windows x64/ARM64 runners. It combines the Mac slices with
`lipo`, verifies both architectures, checks each artifact's source/lockfile/hash,
audits Mach-O imports and normal/delayed PE imports against system runtimes,
and uploads **`server-resource-bin`** with the complete 4D resource layout and
`source.json`. The upstream license is included in both native artifacts and
the final `Resources/bin/UPSTREAM-LICENSE.txt`, with its checksum recorded.
Manifest resource paths always use forward slashes, including on Windows.
The lockfile and checked-in license use LF bytes on every platform; the build
exports the upstream license from the pinned Git object rather than a potentially
CRLF-converted working copy. Checksums remain exact byte hashes.
CI uses Python 3.13.17, which has native distributions for all four runners.
For manual staging on macOS, collect the four target artifact
directories and run:

```sh
python3 scripts/package-server.py --artifacts .build/native --output .build/bin
```

Each native binary is smoke-tested on its own runner before universal packaging.
Assembly requires all four targets, exact provenance, system-only runtime closure,
an empty output directory and files strictly smaller than GitHub's 100 MiB limit
(104,857,600 bytes), including the **combined** universal Mac executable.
Unexpected resources, missing targets and external runtime DLLs fail before
replacement. No Git LFS conversion or partial matrix update is attempted.

### Native refresh, then quick component publication

1. Intentionally update `upstream.json`, `Cargo.lock` and the upstream license
   together when adopting new source. Run **Build server from source** for
   read-only validation; PR/push/build-only runs only upload artifacts.
2. After reviewing the source change on `main`, explicitly run
   [Update committed native resources](https://github.com/miyako/oxibonsai/blob/main/.github/workflows/native-update.yml)
   from `main` with **`update_git=true`**. This rebuilds the pinned source on all
   four native runners, then verifies and **commits/pushes** precisely these paths:
   `oxibonsai/Resources/bin/macOS/oxibonsai`,
   `oxibonsai/Resources/bin/Windows/oxibonsai.exe`,
   `oxibonsai/Resources/bin/WindowsARM/oxibonsai.exe`,
   `oxibonsai/Resources/bin/UPSTREAM-LICENSE.txt` and
   `oxibonsai/Resources/bin/source.json`. It does not modify models/tokenizers,
   wrapper filenames, other platforms or component version metadata.
3. Review the resulting resource commit, then separately dispatch
   [Publish](https://github.com/miyako/oxibonsai/blob/main/.github/workflows/publish.yml)
   on `main` with the desired component version increment. **A `GITHUB_TOKEN`
   push does not trigger other push workflows.** The native updater deliberately
   has no publication dispatch and no `actions: write` permission.

Configure required reviewers and `main` branch restrictions for the `native-update`
and `component-publish` GitHub environments. Only the gated updater job receives
`contents: write`; PR/native compilation jobs are read-only and do not receive
deployment secrets. Branch protection must permit the authorized bot's normal
fast-forward push; the updater never bypasses protection, force-pushes, rebases,
or retries against a changed main. Main freshness is checked before replacement
and commit, and a race at push is rejected by Git. Native updates and production
Publish share a non-cancelling concurrency group.

**Bootstrap requirement:** the old tracked executables have no `source.json`;
they are preserved, not assigned fabricated build provenance. The first complete
authorized native update must land before the new committed-resource Publish
and component PR compilation gates can pass. The old successful CI artifacts
also require an unbundled `vcruntime140.dll` on both Windows architectures and
are therefore not suitable for installing under the new contract. Run the new
static-CRT Windows builds rather than copying those artifacts into Git.
For a staged rollout, land the reviewed workflow/scripts/docs first without a
4D source/resource change: these paths do not trigger production Publish.
The native updater does **not** depend on Publish, the component compile job,
or an existing resource manifest, so it can perform the first refresh on `main`.
The initial component PR resource check is intentionally red until that verified
resource commit exists; it must not be interpreted as a native build failure or
waived with a legacy-success fallback. Then validate an ordinary 4D-only change
against the committed resources before authorizing a separate Publish dispatch.

Publish has **no native build job or native artifact download**. Normal 4D-only
changes use the committed resources, validate their checksums/runtime closure
before the version bump, compile 4D, and verify the packaged resources again
before signing. Both hosted and self-hosted modes use the same path; Python
3.12+ and native inspection tools must be available on the packaging host.
PRs compile/validate read-only and can never publish or use the self-hosted runner.
The component version (`package.json`) is independent of upstream 0.2.3.

The compiler helper is pinned, and `component-dependencies.json` pins
checksum-verified tcp/workers/event release archives. A structured `Compile project`
report must contain `success: true` and an empty diagnostics array; archive
existence alone is not success. Packaging also requires a `.4DZ` (case-insensitive),
generated Libraries and the unchanged tokenizer. Signing includes **every Mach-O
code object, including generated Libraries**, not just the CLI. Developer ID team,
timestamp, hardened runtime, notarization `Accepted`, DMG signing/stapling and
assessment are fail-closed gates. Only afterward are the local version commit and
tag pushed atomically without force and release assets uploaded.

`Resources/bin/source.json` describes **pre-component-signing** hashes.
Signing changes executable bytes; `Resources/signed-code.json` records final
signed code hashes, and the release `SHA256SUMS` records the final ZIP/DMG bytes.

Building/help checks need no model. Real inference and readiness testing require
a compatible GGUF/tokenizer and sufficient RAM; neither a successful compilation
nor the wrapper's start callback proves inference quality.

### Earlier source-build validation (2026-11-02)

Both macOS release targets were built from the pinned source. A universal binary
passed version/help checks on ARM64 and Intel via Rosetta, and both slices
accepted the wrapper's server flags and reported a missing GGUF explicitly.
Eight build/packaging tests, fourteen upstream HTTP/CLI regression tests
(using synthetic tiny models), workflow linting, and the Jekyll site build passed.
This does not validate production-model inference quality or Metal performance.

Windows x64/ARM64 builds require the native Windows CI jobs and were not run on
this Mac; Intel execution here used Rosetta, not physical Intel hardware.
Full 4D compilation/runtime integration and signing/notarization were not
exercised locally (tool4d and deployment credentials were not used).
No production GGUF was downloaded. The Metal dependency `block 0.1.6` emits a
Rust future-incompatibility warning; the pinned compiler still builds it.
No release workflow was triggered.

For the build-back-to-Git audit, actual artifacts from successful native run
`41401312312` measured **28,355,168 bytes** (universal Mac),
**13,504,000 bytes** (Windows x64) and **11,643,392 bytes** (Windows ARM64).
These are measured CI outputs, not the older Git copies and not measurements of
the new static-CRT Windows builds. They demonstrate size headroom only; the
Windows runtime audit above prevents their installation. Each future update
measures its own final files before committing. Local contract tests are not
evidence that unrun Windows builds, 4D compilation or credentialed signing passed.

The new local macOS builds passed version/help and system-library closure checks;
their combined universal executable is **28,354,688 bytes**, with both architectures
executed on Apple Silicon (Intel via Rosetta). New static-CRT Windows outputs
remain unrun and unmeasured.

The local 4D check used the **same tool4d 20.7 build 20.101905**, compiler revision
`b73a89a9eac2636f59bcbd020ccf0aad954cab64` and invocation flags as established CI.
With pinned dependencies, it emitted `{"success":true,"errors":[]}` and generated
a `.4DZ`, generic compiled code, an ARM64 Library and matching tokenizer.
However, tool4d exited **139 during shutdown on macOS 26.7**, including with the
unchanged compiler entry point and with a no-compilation/no-dependency control
method. This local runtime/environment failure is not specific to the new compile
invocation; its precise native crash cause is unresolved. The command's nonzero
exit is **not suppressed**, so this is not a successful packaging run or evidence
of credentialed signing/notarization. Hosted macOS 15 validation is still required.

## Credits and licensing

Engine: [cool-japan/oxibonsai](https://github.com/cool-japan/oxibonsai), Apache-2.0
([bundled license](https://github.com/miyako/oxibonsai/blob/main/oxibonsai/third%20party/LICENSE.txt)).
4D integration: [miyako/oxibonsai](https://github.com/miyako/oxibonsai), [MIT](https://github.com/miyako/oxibonsai/blob/main/LICENSE).
Native workflow conventions follow
[llama-cpp](https://github.com/miyako/llama-cpp),
[CTranslate2](https://github.com/miyako/CTranslate2), and
[onnx-genai](https://github.com/miyako/onnx-genai), adapted to this Rust CLI.
