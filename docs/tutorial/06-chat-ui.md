# Part 6 - Chat UI

> **Series:** [Tutorial index](index.md) · [Part 5](05-chat-agent.md) · **You are here:** Part 6 · [Part 7](07-background-tasks.md)

In Part 5 you built a streaming chat endpoint. In Part 6 you will wire up a browser interface: a single HTML file served by the framework itself, connecting to the SSE endpoint with vanilla JavaScript.

**By the end of this part** you can open `http://127.0.0.1:8000` in a browser, log in, upload a PDF, and get a streamed AI answer, all from a plain HTML page with no build step required.

---

## Prerequisites

- Part 5 complete (`POST /agents/chat` working and streaming)
- Dev server not yet restarted (you will restart it after adding the frontend)
- A PDF already uploaded and indexed from Part 4 (for end-to-end testing)

---

## 1. Remove the placeholder root route

The `GET /` route in `docqa/routes.py` currently returns `{"message": "Hello from docqa!"}`. The frontend will serve at `/` instead, so remove it:

Delete these lines from `docqa/routes.py`:

```python
@router.get("/")
async def root(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"message": "Hello from docqa!"}
```

You can also remove the `Settings` and `get_settings` imports if no other route uses them.

---

## 2. Write the HTML page

Create `frontend/index.html` at the **project root** (same level as `pyproject.toml`, not inside `docqa/`). If you scaffolded with `include_frontend=True` the directory already exists (the `.gitkeep` placeholder is safe to leave). Otherwise create it first:

```bash
mkdir frontend   # from project root; skip if the directory already exists
```

Then create `frontend/index.html` with the following content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document Q&A</title>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --surface: #ffffff;
      --surface-2: #f8fafc;
      --border: #e2e8f0;
      --text: #0f172a;
      --text-muted: #64748b;
      --green: #059669;
      --red: #dc2626;
      --radius: 12px;
      --shadow: 0 1px 3px rgba(0,0,0,.08), 0 4px 16px rgba(0,0,0,.04);
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--surface-2);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Header bar */
    .topbar {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: var(--shadow);
    }

    .topbar h1 { font-size: 1.1rem; font-weight: 700; }

    .topbar-actions { display: flex; gap: 10px; align-items: center; }

    .topbar .user-email {
      font-size: 0.82rem;
      color: var(--text-muted);
    }

    .btn {
      padding: 8px 16px;
      background: var(--primary);
      color: #fff;
      border: none;
      border-radius: 8px;
      font-size: 0.85rem;
      font-weight: 500;
      cursor: pointer;
      transition: background .15s, opacity .15s;
      white-space: nowrap;
      font-family: inherit;
    }

    .btn:hover:not(:disabled) { background: var(--primary-hover); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-sm { padding: 6px 12px; font-size: 0.8rem; }
    .btn-outline {
      background: transparent;
      color: var(--primary);
      border: 1px solid var(--primary);
    }
    .btn-outline:hover:not(:disabled) { background: rgba(37,99,235,.06); }
    .btn-danger { background: var(--red); }
    .btn-danger:hover:not(:disabled) { background: #b91c1c; }

    /* Login screen */
    .login-screen {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 32px;
    }

    .login-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      padding: 32px;
      width: 100%;
      max-width: 380px;
    }

    .login-card h2 {
      font-size: 1.2rem;
      margin-bottom: 20px;
      text-align: center;
    }

    .form-group { margin-bottom: 14px; }

    .form-group label {
      display: block;
      font-size: 0.82rem;
      font-weight: 500;
      margin-bottom: 4px;
    }

    .form-group input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 0.92rem;
      color: var(--text);
      background: var(--surface);
      outline: none;
      transition: border-color .15s, box-shadow .15s;
      font-family: inherit;
    }

    .form-group input:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(37,99,235,.12);
    }

    .login-card .btn { width: 100%; margin-top: 8px; }

    .error-msg {
      font-size: 0.82rem;
      color: var(--red);
      margin-top: 10px;
      text-align: center;
    }

    /* Main app layout */
    .app-body {
      flex: 1;
      display: flex;
      flex-direction: column;
      max-width: 760px;
      width: 100%;
      margin: 0 auto;
      padding: 20px 16px;
    }

    /* Chat area */
    .chat-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      gap: 10px;
      overflow-y: auto;
      padding: 10px 0;
      min-height: 200px;
    }

    .bubble {
      padding: 10px 14px;
      border-radius: 10px;
      font-size: 0.92rem;
      line-height: 1.6;
      max-width: 85%;
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .bubble.user {
      background: var(--primary);
      color: #fff;
      align-self: flex-end;
      border-bottom-right-radius: 3px;
    }

    .bubble.assistant {
      background: var(--surface);
      border: 1px solid var(--border);
      align-self: flex-start;
      border-bottom-left-radius: 3px;
      box-shadow: var(--shadow);
    }

    .bubble.assistant.streaming::after {
      content: "\258D";
      animation: blink .7s step-end infinite;
    }

    @keyframes blink { 50% { opacity: 0; } }

    .empty-state {
      flex: 1;
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--text-muted);
      font-size: 0.95rem;
      text-align: center;
      padding: 40px;
    }

    /* Input bar */
    .input-bar {
      display: flex;
      gap: 8px;
      padding: 12px 0;
      border-top: 1px solid var(--border);
    }

    .input-bar textarea {
      flex: 1;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 10px;
      font-size: 0.92rem;
      color: var(--text);
      background: var(--surface);
      outline: none;
      resize: none;
      min-height: 44px;
      max-height: 120px;
      font-family: inherit;
      transition: border-color .15s, box-shadow .15s;
    }

    .input-bar textarea:focus {
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(37,99,235,.12);
    }

    /* Upload modal */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,.4);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100;
    }

    .modal {
      background: var(--surface);
      border-radius: var(--radius);
      box-shadow: 0 20px 60px rgba(0,0,0,.2);
      padding: 28px;
      width: 100%;
      max-width: 420px;
    }

    .modal h3 { font-size: 1rem; margin-bottom: 16px; }

    .modal input[type="file"] {
      width: 100%;
      padding: 10px;
      border: 2px dashed var(--border);
      border-radius: 8px;
      font-size: 0.88rem;
      cursor: pointer;
    }

    .modal-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 16px;
    }

    .success-msg {
      font-size: 0.82rem;
      color: var(--green);
      margin-top: 10px;
    }
  </style>
</head>
<body x-data="app()">

  <!-- Login Screen -->
  <template x-if="!token">
    <div class="login-screen">
      <div class="login-card">
        <h2>Document Q&A</h2>
        <div class="form-group">
          <label for="email">Email</label>
          <input id="email" type="email" x-model="email" placeholder="admin@docqa.local"
            @keydown.enter="login()">
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input id="password" type="password" x-model="password" placeholder="Password"
            @keydown.enter="login()">
        </div>
        <button class="btn" @click="login()" :disabled="logging_in"
          x-text="logging_in ? 'Logging in...' : 'Log in'"></button>
        <div class="error-msg" x-show="login_error" x-text="login_error"></div>
      </div>
    </div>
  </template>

  <!-- App (after login) -->
  <template x-if="token">
    <div style="display:flex; flex-direction:column; height:100vh;">
      <!-- Top bar -->
      <div class="topbar">
        <h1>Document Q&A</h1>
        <div class="topbar-actions">
          <button class="btn btn-sm btn-outline" @click="show_upload = true">Upload PDF</button>
          <span class="user-email" x-text="email"></span>
          <button class="btn btn-sm btn-danger" @click="logout()">Logout</button>
        </div>
      </div>

      <!-- Chat body -->
      <div class="app-body">
        <div class="chat-area" x-ref="chatArea">
          <template x-if="messages.length === 0">
            <div class="empty-state">
              <div>
                <template x-if="documents.length > 0">
                  <div style="text-align:left;">
                    <strong style="font-size:0.85rem; color:var(--text);">Your documents</strong>
                    <ul style="list-style:none; margin-top:8px;">
                      <template x-for="doc in documents" :key="doc.id">
                        <li style="padding:4px 0; font-size:0.85rem; display:flex; align-items:center; gap:8px;">
                          <span style="width:8px; height:8px; border-radius:50%; flex-shrink:0;"
                            :style="{ background: doc.status === 'ingested' ? 'var(--green)' : doc.status === 'failed' ? 'var(--red)' : '#f59e0b' }"></span>
                          <span x-text="doc.title" style="color:var(--text);"></span>
                          <span x-text="doc.status" style="color:var(--text-muted); font-size:0.75rem;"></span>
                        </li>
                      </template>
                    </ul>
                    <p style="margin-top:14px; font-size:0.88rem;">Ask a question about your documents above.</p>
                  </div>
                </template>
                <template x-if="documents.length === 0">
                  <div>
                    Upload a PDF and ask questions about its content.<br>
                    The AI will search your documents and stream an answer.
                  </div>
                </template>
              </div>
            </div>
          </template>
          <template x-for="(msg, i) in messages" :key="i">
            <div class="bubble" :class="msg.role + (msg.streaming ? ' streaming' : '')"
              x-text="msg.content"></div>
          </template>
        </div>

        <div class="input-bar">
          <textarea x-model="question" placeholder="Ask a question about your documents..."
            @keydown.enter.prevent="if (!$event.shiftKey) ask()"
            :disabled="asking" rows="1"></textarea>
          <button class="btn" @click="ask()" :disabled="asking || !question.trim()">Ask</button>
        </div>
      </div>

      <!-- Upload modal -->
      <template x-if="show_upload">
        <div class="modal-backdrop" @click.self="show_upload = false">
          <div class="modal">
            <h3>Upload a PDF document</h3>
            <input type="file" accept=".pdf" x-ref="fileInput">
            <div class="success-msg" x-show="upload_msg" x-text="upload_msg"></div>
            <div class="error-msg" x-show="upload_error" x-text="upload_error"></div>
            <div class="modal-actions">
              <button class="btn btn-outline" @click="show_upload = false">Cancel</button>
              <button class="btn" @click="uploadPdf()" :disabled="uploading"
                x-text="uploading ? 'Uploading...' : 'Upload'"></button>
            </div>
          </div>
        </div>
      </template>
    </div>
  </template>

  <script>
    function app() {
      return {
        // Auth state
        token: null,
        email: "",
        password: "",
        login_error: "",
        logging_in: false,

        // Chat state
        messages: [],
        question: "",
        asking: false,

        // Documents state
        documents: [],

        // Upload state
        show_upload: false,
        uploading: false,
        upload_msg: "",
        upload_error: "",

        async login() {
          this.logging_in = true;
          this.login_error = "";
          try {
            const resp = await fetch("/auth/token", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ email: this.email, password: this.password }),
            });
            const data = await resp.json();
            if (resp.ok) {
              this.token = data.access_token;
              this.password = "";
              this.loadDocuments();
            } else {
              this.login_error = data.detail || "Invalid credentials";
            }
          } catch (e) {
            this.login_error = "Connection failed";
          } finally {
            this.logging_in = false;
          }
        },

        logout() {
          this.token = null;
          this.messages = [];
          this.documents = [];
          this.email = "";
        },

        async loadDocuments() {
          try {
            const resp = await fetch("/documents", {
              headers: { "Authorization": `Bearer ${this.token}` },
            });
            if (resp.ok) {
              this.documents = await resp.json();
            }
          } catch (_) {}
        },

        async uploadPdf() {
          const file = this.$refs.fileInput?.files?.[0];
          if (!file) return;
          this.uploading = true;
          this.upload_msg = "";
          this.upload_error = "";
          try {
            const form = new FormData();
            form.append("file", file);
            const resp = await fetch("/documents/upload", {
              method: "POST",
              headers: { "Authorization": `Bearer ${this.token}` },
              body: form,
            });
            const data = await resp.json();
            if (resp.ok) {
              this.upload_msg = `Uploaded: ${file.name} (indexing in background)`;
              this.upload_error = "";
              this.loadDocuments();
            } else {
              this.upload_error = data.detail || "Upload failed";
            }
          } catch (e) {
            this.upload_error = "Connection failed";
          } finally {
            this.uploading = false;
          }
        },

        async ask() {
          const q = this.question.trim();
          if (!q) return;

          this.messages.push({ role: "user", content: q });
          this.question = "";
          this.asking = true;

          // Add streaming placeholder
          const aiIdx = this.messages.length;
          this.messages.push({ role: "assistant", content: "", streaming: true });

          this.$nextTick(() => {
            this.$refs.chatArea?.scrollTo(0, this.$refs.chatArea.scrollHeight);
          });

          try {
            const resp = await fetch("/agents/chat", {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${this.token}`,
              },
              body: JSON.stringify({
                messages: [{ role: "user", content: q }],
              }),
            });

            const reader = resp.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              const text = decoder.decode(value, { stream: true });
              for (const line of text.split("\n")) {
                if (line.startsWith("data: ")) {
                  try {
                    const chunk = JSON.parse(line.slice(6));
                    if (typeof chunk === "string") {
                      this.messages[aiIdx].content += chunk;
                      this.$nextTick(() => {
                        this.$refs.chatArea?.scrollTo(0, this.$refs.chatArea.scrollHeight);
                      });
                    }
                  } catch (_) {}
                }
              }
            }
          } catch (e) {
            this.messages[aiIdx].content += "\n\n[Connection error]";
          } finally {
            this.messages[aiIdx].streaming = false;
            this.asking = false;
          }
        },
      };
    }
  </script>
</body>
</html>
```

A few things to notice:

- **Alpine.js**: a 3KB reactive framework loaded via CDN script tag. No build step, no npm. It provides `x-model`, `x-if`, `x-for`, and event bindings that keep the UI in sync with state.
- **Wizard flow**: the login screen shows first. After authentication, it transitions to the app view with a top bar, document list, chat area, and upload modal.
- **Why `fetch()` + `getReader()`**: the browser's built-in SSE helper only supports GET requests. `POST /agents/chat` is a POST endpoint, so you must use the Fetch Streams API (`response.body.getReader()`) to consume the SSE response body.
- **SSE format**: each line from the server starts with `data: ` followed by a JSON-encoded string token. `JSON.parse(line.slice(6))` decodes it, and the result is appended to the chat bubble.
- **Same origin**: because the HTML page is served by the same FastAPI process at the same port, there is no CORS configuration needed between the UI and the API.

---

## 3. Serve the frontend

Open `docqa/app.py` and add one line at the very end, after `register_agents(_stack)`:

```python
_stack.frontend("./frontend")
```

That is all the Python you need. `frontend()` tells the framework to serve the `frontend/` directory at `/`. API routes always take priority, so your existing endpoints are unaffected. Any path that does not match an API route falls back to `index.html`, which is how single-page apps handle client-side routing.

---

## 4. Run and try it

Restart the dev server:

```bash
fas dev
```

Then open `http://127.0.0.1:8000` in a browser. You should see the login screen.

1. Enter the superuser credentials you created in Part 3 (`admin@docqa.local` and the password you chose) and click **Log in**.
2. After login you will see the app with your uploaded documents listed (with status indicators).
3. Click **Upload PDF** in the top bar to upload a new document via the modal popup.
4. Type a question in the input bar, for example: `What topics are covered in the uploaded documents?`
5. Click **Ask** and watch tokens appear word-by-word in the chat bubble as the LLM streams its answer.

Open the browser DevTools **Network** tab and find the `/agents/chat` request to watch the streaming chunks arrive in real time.

---

## What you built

- `frontend/index.html`: a single-page app with Alpine.js covering login, document list, PDF upload modal, and SSE-streamed chat
- `_stack.frontend("./frontend")`: one line in `app.py` that serves the entire directory alongside the API from the same process and port
- Wizard flow: login screen transitions to the app view after authentication
- Vanilla JS `fetch()` + `getReader()` pattern for consuming POST-based server-sent events

---

## Next steps

[Part 7 - Background Tasks](07-background-tasks.md)

In Part 7 you will move PDF ingestion off the request path into a Dramatiq background task, so uploads return immediately and processing happens asynchronously.
