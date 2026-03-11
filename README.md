# 🐾 MyAi (built on OpenClaw)

A secure, locally-running AI agent powered by **Ollama** that integrates into **Microsoft Teams** as a personal assistant. Your data stays on your machine.

## Features

- **100% Local LLM** — Runs via Ollama, no data sent to cloud AI services
- **Teams Integration** — Chat with your AI agent directly in Microsoft Teams
- **Local File Access** — Read and search your files (permission-gated)
- **Web Search** — DuckDuckGo or Tavily search (opt-in)
- **RAG** — Index your documents for semantic search with ChromaDB
- **Secure** — Every action requires explicit user permission

## Quick Start

### Prerequisites

1. **Ollama** — Install from [ollama.com](https://ollama.com)
2. **Python 3.11+**
3. **Azure account** (free tier) for Bot Channel Registration
4. **ngrok** — For tunneling ([ngrok.com](https://ngrok.com))

### 1. Install & Configure

```bash
git clone https://github.com/Anubhavc121/MyAi.git
cd MyAi
pip install -e .

# Pull an Ollama model
ollama pull llama3.1:8b
ollama pull nomic-embed-text  # for RAG embeddings

# Set up environment
cp .env.example .env
# Edit .env with your Azure Bot credentials (see Azure Setup below)
```

### 2. Azure Bot Setup

1. Go to [Azure Portal](https://portal.azure.com) → Create a resource → **Azure Bot**
2. Choose **Multi-tenant** for bot type
3. Note your **Microsoft App ID** and create a **Client Secret**
4. Put both in your `.env` file
5. Under **Channels** → Add **Microsoft Teams**
6. Under **Configuration** → Set messaging endpoint to your ngrok URL + `/api/messages`

### 3. Run

```bash
# Terminal 1: Start Ollama
ollama serve

# Terminal 2: Start MyAi
python -m app.main

# Terminal 3: Start tunnel
ngrok http 8000
```

Copy the ngrok HTTPS URL and update your Azure Bot's messaging endpoint to:
`https://your-ngrok-url.ngrok.io/api/messages`

### 4. Install in Teams

1. In Azure Portal → Your Bot → Channels → Teams → Open in Teams
2. Or use Teams App Studio to create a custom app pointing to your bot

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/status` | Current config, model, and health |
| `/model <name>` | Switch Ollama model (e.g., `/model mistral:7b`) |
| `/allow <path>` | Grant file access to a directory |
| `/revoke` | Revoke all file permissions |
| `/search on\|off` | Toggle web search |
| `/index <path>` | Index directory for RAG search |
| `/clear` | Clear conversation history |

## Architecture

```
[Teams] → [Azure Bot Service] → [ngrok] → [FastAPI :8000]
                                                ↓
                                          [Agent Core]
                                         ↙     ↓      ↘
                                 [Ollama]  [Files]  [Web/RAG]
```

## Project Structure

```
openclaw/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── bot.py               # Teams bot handler + slash commands
│   ├── config.py            # Settings (pydantic-settings)
│   ├── agent/
│   │   ├── core.py          # ReAct agent loop
│   │   ├── prompts.py       # System prompts
│   │   └── tools.py         # Tool registry
│   ├── services/
│   │   ├── ollama.py        # Ollama API client
│   │   ├── file_access.py   # Sandboxed file operations
│   │   ├── web_search.py    # DuckDuckGo / Tavily
│   │   └── rag.py           # ChromaDB + embeddings
│   ├── security/
│   │   └── permissions.py   # Auth + permission tiers
│   └── storage/
│       ├── database.py      # SQLite store
│       └── models.py        # Data models
├── config/
│   ├── config.yaml          # Agent settings
│   └── permissions.yaml     # Directory allowlist
├── data/                    # SQLite + ChromaDB (gitignored)
├── .env.example
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Docker

```bash
docker compose up --build
```

Note: Ollama must be running on the host. The container connects via `host.docker.internal`.

## Security

- All LLM inference is local — nothing leaves your machine
- File access requires explicit directory grants
- Web search is off by default
- Conversation history stored locally in SQLite
- No telemetry or analytics
- Azure Bot auth validates JWT tokens

## License

MIT
