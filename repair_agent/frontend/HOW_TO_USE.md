# RepairAgent Web UI — Quick Start

## 1. Start the API server

```bash
cd repair_agent
python api_server.py
```

Server runs at **http://localhost:5050** — keep this terminal open.

## 2. Open the frontend

Double-click `repair_agent/frontend/index.html` in File Explorer,  
or paste this into your browser:

```
file:///c:/Users/yashg/OneDrive/Desktop/genai/repair_agent/frontend/index.html
```

---

## Pages

| Page | What you can do |
|------|-----------------|
| **Dashboard** | See environment status, benchmark comparison, experiment stats |
| **Run Agent** | Pick bugs, choose a model, set temperature & cycles, launch a run, watch live output |
| **Experiments** | Browse past experiment folders, view per-bug results, read full logs |
| **Results** | Filter & search the 164 bugs RepairAgent fixed (ICSE 2025 paper) |
| **Setup** | Save API keys, edit hyperparameters, see quick-start CLI commands |

---

## Running a repair

1. Go to **Run Agent**
2. Type bugs in the box — e.g. `Chart 1, Math 5`  
   *(or use the project picker dropdowns)*
3. Click a model card (or type a custom model name)
4. Hit **Launch RepairAgent**
5. Watch live output stream in the terminal panel on the right

> Requires Java 11, Perl, and Defects4J to be installed.  
> Run `python repairagent.py doctor` to check.

---

## API keys

Go to **Setup → API Keys**, paste your key, click **Save**.

| Provider | Key name | Where to get it |
|----------|----------|-----------------|
| OpenAI | `OPENAI_API_KEY` | platform.openai.com |
| Anthropic | `ANTHROPIC_API_KEY` | console.anthropic.com |
