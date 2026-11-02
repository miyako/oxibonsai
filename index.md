---
layout: default
title: Tiny weights. Full-grown intelligence.
landing: true
---
<section class="hero" aria-labelledby="hero-title">
  <div class="hero-copy">
    <p class="eyebrow"><span class="status-dot" aria-hidden="true"></span> Local inference / 4D integration</p>
    <h1 id="hero-title">Tiny weights.<br><span>Full-grown intelligence.</span></h1>
    <p class="hero-description">Bring OxiBonsai into your 4D application. Run a local model server on macOS or Windows, and connect through a familiar HTTP API.</p>
    <div class="actions">
      <a class="button button-primary" href="https://github.com/miyako/oxibonsai/releases">Get the component <span aria-hidden="true">&nearr;</span></a>
      <a class="button button-secondary" href="{{ "/guide.html#use-from-4d" | relative_url }}">Read the guide <span aria-hidden="true">&rarr;</span></a>
    </div>
    <p class="hero-note">4D 20+ <span aria-hidden="true">/</span> GGUF models <span aria-hidden="true">/</span> Open source</p>
  </div>
  <div class="hero-art">
    <div class="art-caption"><span>THE ENGINE, CLOSE AT HAND</span><span aria-hidden="true">01 /</span></div>
    <img class="hero-icon" src="{{ "/assets/icon.png" | relative_url }}" alt="OxiBonsai wrapper icon: a rose-colored geometric mark and oxibonsai wordmark on charcoal." width="1024" height="1024" fetchpriority="high">
    <div class="art-footer"><span class="status-dot" aria-hidden="true"></span><code>127.0.0.1:8080</code><span>Local by default</span></div>
  </div>
</section>

<section class="platform-section" aria-labelledby="platforms-title">
  <div class="section-heading">
    <p class="eyebrow">Choose your ground</p>
    <h2 id="platforms-title">One integration. Mac and Windows.</h2>
    <p>Native executables for the platforms your 4D app calls home.</p>
  </div>
  <div class="platform-grid">
    <article class="platform"><span class="card-index">01 / macOS</span><h3>Apple Silicon</h3><p>Metal acceleration</p><span class="tag">Universal Mac executable</span></article>
    <article class="platform"><span class="card-index">02 / macOS</span><h3>Intel</h3><p>CPU inference</p><span class="tag">Universal Mac executable</span></article>
    <article class="platform"><span class="card-index">03 / Windows</span><h3>x64 &amp; ARM64</h3><p>CPU inference</p><span class="tag">Native executables</span></article>
  </div>
  <p class="section-note">Bring your own compatible GGUF model and tokenizer, with enough disk space and RAM. Model downloads are separate. No Linux component or CUDA-enabled executable is packaged here.</p>
</section>

<section class="workflow-section" aria-labelledby="workflow-title">
  <div class="section-heading split-heading">
    <div><p class="eyebrow">Make it yours</p><h2 id="workflow-title">From a process<br>to part of your app.</h2></div>
    <p>Use the 4D component to manage the server, or work directly with the bundled command-line executable.</p>
  </div>
  <div class="workflow-grid">
    <article class="workflow-card">
      <span class="card-index">THE 4D ROUTE</span><h3>A local worker.<br>A familiar workflow.</h3>
      <p>Install the <code>.4dbase</code> in your application's <code>Components</code> folder and restart 4D. The wrapper selects the platform executable and starts the server with your model and options.</p>
      <p>Connect 4D AI Kit's OpenAI-compatible provider to <code>http://127.0.0.1:8080/v1</code>. Use the model ID returned by the server.</p>
      <a class="text-link" href="{{ "/guide.html#use-from-4d" | relative_url }}">See the 4D example <span aria-hidden="true">&rarr;</span></a>
    </article>
    <article class="workflow-card workflow-dark">
      <span class="card-index">THE HTTP ROUTE</span><h3>Your tools.<br>The same local server.</h3>
      <p>Run <code>oxibonsai serve</code> from a terminal, discover the loaded model, and send chat or completion requests from your own client.</p>
      <p>Keep the loopback binding by default. Deliberate network access needs deliberate protection; bearer authentication is available.</p>
      <a class="text-link" href="#quickstart">Start with HTTP <span aria-hidden="true">&rarr;</span></a>
    </article>
  </div>
</section>

<section id="quickstart" class="quickstart-section" aria-labelledby="quickstart-title">
  <div class="section-heading">
    <p class="eyebrow">A first conversation</p><h2 id="quickstart-title">Start. Check. Connect.</h2>
    <p>After <a href="{{ "/guide.html#installation-and-targets" | relative_url }}">installing the component</a>, open a terminal in its platform-specific <code>Resources/bin/</code> directory. The examples below use macOS; on Windows, use <code>oxibonsai.exe</code> and adapt the shell syntax.</p>
  </div>
  <div class="step">
    <div class="step-description"><span class="step-number">01</span><h3>Load your model</h3><p>Replace both paths with your GGUF and its compatible tokenizer. Keep this terminal running.</p></div>
    <div class="step-code">
{% highlight sh %}./oxibonsai serve \
  --model /path/to/model.gguf \
  --tokenizer /path/to/tokenizer.json \
  --host 127.0.0.1 \
  --port 8080
{% endhighlight %}
    </div>
  </div>
  <div class="step">
    <div class="step-description"><span class="step-number">02</span><h3>Wait for readiness</h3><p>In another terminal, repeat the health request until it succeeds. Then discover the model ID. A started process is not a ready server.</p></div>
    <div class="step-code">
{% highlight sh %}curl --fail http://127.0.0.1:8080/health
curl --fail http://127.0.0.1:8080/v1/models
{% endhighlight %}
    </div>
  </div>
  <div class="step">
    <div class="step-description"><span class="step-number">03</span><h3>Send a message</h3><p>Replace <code>MODEL_ID_FROM_RESPONSE</code> with the returned ID. For streaming, set <code>"stream": true</code> and use <code>curl -N</code>.</p></div>
    <div class="step-code">
{% highlight sh %}curl --fail http://127.0.0.1:8080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "MODEL_ID_FROM_RESPONSE",
    "messages": [{"role": "user", "content": "Hello from my app."}],
    "max_tokens": 128,
    "stream": false
  }'
{% endhighlight %}
    </div>
  </div>
  <div class="notice"><strong>Using a bearer token?</strong> Add <code>Authorization: Bearer YOUR_TOKEN</code> to model and inference requests. <code>/health</code> and <code>/metrics</code> are exempt from authentication. <a href="{{ "/guide.html#options-and-api" | relative_url }}">Read the server options &rarr;</a></div>
</section>

<section class="boundary-section" aria-labelledby="boundary-title">
  <div><p class="eyebrow">Know what is inside</p><h2 id="boundary-title">A focused API.<br>Clear boundaries.</h2><p>The integration runs upstream's <code>oxibonsai serve</code>, not the separate <code>oxibonsai-serve</code> binary. Capabilities belong to this entry point, not every upstream tool.</p><a class="text-link" href="{{ "/guide.html#options-and-api" | relative_url }}">Explore the API &amp; options <span aria-hidden="true">&rarr;</span></a></div>
  <dl class="capabilities">
    <div><dt>Models, chat &amp; completions</dt><dd><code>/v1/models</code>, <code>/v1/chat/completions</code> and <code>/v1/completions</code> are available.</dd></div>
    <div><dt>Lexical vectors, not model embeddings</dt><dd><code>/v1/embeddings</code> uses TF-IDF/byte-hash vectors, not learned semantic embeddings from your GGUF.</dd></div>
    <div><dt>No image, file or moderation API</dt><dd>These endpoints are not exposed by this server.</dd></div>
  </dl>
</section>

<section class="source-section" aria-labelledby="source-title">
  <div><p class="eyebrow">Open at the roots</p><h2 id="source-title">An engine you can trace.</h2><p>The integration is MIT-licensed; the upstream Rust engine is Apache-2.0. Source builds pin OxiBonsai v0.2.3, its dependencies, build features and Rust 1.99.0. An explicit native refresh commits verified resources to Git; component-only Publish reuses them without rebuilding Rust. Native refresh never dispatches a release. No performance or inference-quality guarantees.</p></div>
  <a class="button button-secondary" href="{{ "/guide.html#reproducible-source-builds" | relative_url }}">Build provenance <span aria-hidden="true">&rarr;</span></a>
</section>
