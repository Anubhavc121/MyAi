# MyAi — Windows Setup Guide

Follow these steps to get MyAi running on your Windows laptop.

---

## Step 1: Install Prerequisites

### Python 3.11+
1. Download from [python.org](https://python.org)
2. **⚠️ Check "Add Python to PATH"** during install
3. Verify: `python --version`

### Ollama
1. Download from [ollama.com](https://ollama.com) (Windows installer)
2. Run the installer
3. Open PowerShell and run:
```powershell
ollama serve
```
4. In a **second PowerShell** window:
```powershell
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```
5. Verify: `curl http://localhost:11434/api/tags`

### ngrok
1. Sign up at [ngrok.com](https://ngrok.com) (free)
2. Download the Windows version
3. Unzip and add to PATH (or place in project folder)
4. Authenticate:
```powershell
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

---

## Step 2: Set Up the Project

Open PowerShell and run:

```powershell
cd C:\path\to\miai

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Install dependencies
pip install -e .
```

---

## Step 3: Configure .env

```powershell
copy .env.example .env
```

Open `.env` in Notepad or VS Code and fill in your Azure credentials:

```env
MICROSOFT_APP_ID=your-azure-app-id
MICROSOFT_APP_PASSWORD=your-azure-client-secret
```

These are the **same credentials** from your Azure App Registration.

---

## Step 4: Run (3 PowerShell Windows)

### Window 1 — Ollama
```powershell
ollama serve
```

### Window 2 — MyAi
```powershell
cd C:\path\to\miai
.venv\Scripts\activate
python -m app.main
```

You should see:
```
🐾  MyAi Agent Started
   Server:   http://0.0.0.0:8000
```

### Window 3 — ngrok
```powershell
ngrok http 8000
```

Copy the **https** URL (e.g., `https://xxxx.ngrok-free.app`)

---

## Step 5: Update Azure Messaging Endpoint

1. Go to [Azure Portal](https://portal.azure.com)
2. Open your Azure Bot resource → **Configuration**
3. Set **Messaging endpoint** to:
   ```
   https://YOUR-NGROK-URL.ngrok-free.app/api/messages
   ```
4. Click **Apply**

---

## Step 6: Test in Teams

1. Open Microsoft Teams
2. Find **MyAi** in your chats
3. Send: `Hello!`
4. Try: `/help` and `/status`
5. Grant file access: `/allow C:\path\to\your\files`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python` not found | Reinstall Python with "Add to PATH" checked |
| `pip install -e .` fails | Make sure venv is activated (`.venv\Scripts\activate`) |
| Ollama not reachable | Make sure `ollama serve` is running in Window 1 |
| Bot not responding | Check Window 2 for errors, verify ngrok URL in Azure |
| Permission denied | Run PowerShell as Administrator |
