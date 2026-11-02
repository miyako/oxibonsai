# oxibonsai for 4D

Run the [OxiBonsai](https://github.com/cool-japan/oxibonsai) local HTTP server from **4D 20+**.
This repository is the MIT-licensed 4D component and its build/packaging integration,
not the upstream inference engine. The upstream Rust engine is Apache-2.0 licensed.

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
`.build/server/artifacts/<target>/`. It refuses host-specific `RUSTFLAGS`.
For an update, change the pin intentionally, regenerate `Cargo.lock` using the
pinned Rust toolchain against that source, and rerun all four native builds.
Use a fresh `--work-dir` when changing the source pin.

The [source-build workflow](https://github.com/miyako/oxibonsai/blob/main/.github/workflows/build-server.yml) runs on native
macOS ARM/Intel and Windows x64/ARM64 runners. It combines the Mac slices with
`lipo`, verifies both architectures, checks each artifact's source/lockfile/hash,
and uploads **`server-resource-bin`** with the complete 4D resource layout and
`source.json`. The upstream license is included in both native artifacts and
the final `Resources/bin/UPSTREAM-LICENSE.txt`, with its checksum recorded.
CI uses Python 3.13.17, which has native distributions for all four runners.
For manual staging on macOS, collect the four target artifact
directories and run:

```sh
python3 scripts/package-server.py --artifacts .build/native --output .build/bin
```

Copy the contents of `.build/bin/` into `oxibonsai/Resources/bin/` only after all
targets succeed. Generated files are ignored; builds do not commit binaries.
Each native binary is smoke-tested on its own runner before universal packaging.

The existing [Publish workflow](https://github.com/miyako/oxibonsai/blob/main/.github/workflows/publish.yml) now **requires**
this complete source build and stages its artifacts before 4D compilation,
then verifies the compiled component's resource checksums before
signing/notarization and release packaging. This applies to both hosted
and self-hosted publishing; self-hosted publishing still requires GitHub-hosted
native build jobs and Python 3.12+ on the packaging host. The component version
(`package.json`, currently 20.0.4) is
independent of upstream 0.2.3. **Publish increments that version and publishes a
release; use Build server from source alone for build-only validation.**
The provenance checksums describe the **pre-signing** artifacts; macOS code
signing changes executable bytes in the published component.

Building/help checks need no model. Real inference and readiness testing require
a compatible GGUF/tokenizer and sufficient RAM; neither a successful compilation
nor the wrapper's start callback proves inference quality.

### Validation of this update (2026-11-02)

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

## Credits and licensing

Engine: [cool-japan/oxibonsai](https://github.com/cool-japan/oxibonsai), Apache-2.0
([bundled license](https://github.com/miyako/oxibonsai/blob/main/oxibonsai/third%20party/LICENSE.txt)).
4D integration: [miyako/oxibonsai](https://github.com/miyako/oxibonsai), [MIT](https://github.com/miyako/oxibonsai/blob/main/LICENSE).
Native workflow conventions follow
[llama-cpp](https://github.com/miyako/llama-cpp),
[CTranslate2](https://github.com/miyako/CTranslate2), and
[onnx-genai](https://github.com/miyako/onnx-genai), adapted to this Rust CLI.
