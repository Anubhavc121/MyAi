# MyAi Setup Guide — Step by Step

Follow these steps in order. The whole process takes ~30-45 minutes.

---

## STEP 1: Install Prerequisites

### 1a. Install Ollama

Go to https://ollama.com and download for your OS.

After installing, open a terminal and run:

```bash
ollama serve
```

In a **second terminal**, pull the models:

```bash
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

Verify it's working:

```bash
curl http://localhost:11434/api/tags
```

You should see a JSON response listing your models.


### 1b. Install Python 3.11+

Check your version:

```bash
python --version
```

If < 3.11, install from https://python.org


### 1c. Install ngrok

Go to https://ngrok.com → Sign up (free) → Download ngrok.

After installing, authenticate:

```bash
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

(You'll find your auth token at https://dashboard.ngrok.com/get-started/your-authtoken)

---

## STEP 2: Set Up the MyAi Project

```bash
# Unzip the project (if downloaded as zip)
# cd into the project
cd miai

# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e .
```

Copy the env file:

```bash
cp .env.example .env
```

We'll fill in the Azure credentials in the next step.

---

## STEP 3: Register an Azure Bot (This is the critical step)

### 3a. Create an App Registration in Microsoft Entra ID

1. Go to https://portal.azure.com
2. Search for **"App registrations"** in the top search bar
3. Click **"+ New registration"**
4. Fill in:
   - **Name:** `MyAi Bot`
   - **Supported account types:** Select **"Accounts in this organizational directory only (Single tenant)"**
   - **Redirect URI:** Leave blank
5. Click **Register**
6. On the overview page, copy the **Application (client) ID** — this is your `MICROSOFT_APP_ID`
7. Also copy the **Directory (tenant) ID** — you'll need this

### 3b. Create a Client Secret

1. In the left sidebar of your app registration, click **"Certificates & secrets"**
2. Click **"+ New client secret"**
3. Description: `MyAi Bot Secret`
4. Expiry: **24 months**
5. Click **Add**
6. **⚠️ IMMEDIATELY copy the "Value" column** (NOT the "Secret ID") — this is your `MICROSOFT_APP_PASSWORD`. You can only see it once!

### 3c. Create the Azure Bot Resource

1. Go back to the Azure Portal home
2. Click **"+ Create a resource"**
3. Search for **"Azure Bot"**
4. Click **Create**
5. Fill in:
   - **Bot handle:** `miai-bot` (must be unique)
   - **Subscription:** Your subscription
   - **Resource group:** Create new → `miai-rg`
   - **Data residency:** Global
   - **Pricing tier:** **F0 (Free)** — 10K messages/month
   - **Type of App:** **Single Tenant**
   - **Creation type:** **Use existing app registration**
   - **App ID:** Paste the Application (client) ID from step 3a
   - **App tenant ID:** Paste the Directory (tenant) ID from step 3a
6. Click **Review + Create** → **Create**
7. Wait for deployment to complete, then click **Go to resource**

### 3d. Enable the Teams Channel

1. In your Azure Bot resource, click **"Channels"** in the left sidebar
2. Under **Available Channels**, click **Microsoft Teams**
3. Read and **Agree** to the terms of service
4. On the **Messaging** tab, select **Microsoft Teams Commercial**
5. Click **Apply**

### 3e. Set the Messaging Endpoint (we'll update this after starting ngrok)

1. In the Azure Bot resource, click **"Configuration"** in the left sidebar
2. You'll see **"Messaging endpoint"** — leave it blank for now
3. We'll come back to fill this in after starting ngrok in Step 5

---

## STEP 4: Update Your .env File

Open the `.env` file in your project and fill in:

```
MICROSOFT_APP_ID=paste-your-application-client-id-here
MICROSOFT_APP_PASSWORD=paste-your-client-secret-value-here
```

Leave everything else as default for now.

---

## STEP 5: Start Everything

You need **3 terminals** open:

### Terminal 1: Ollama
```bash
ollama serve
```
(Skip if already running)

### Terminal 2: MyAi Agent
```bash
cd miai
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
python -m app.main
```

You should see:
```
============================================================
🐾  MyAi Agent Started
   Model:    llama3.1:8b
   Server:   http://0.0.0.0:8000
   Webhook:  http://0.0.0.0:8000/api/messages
   Health:   http://0.0.0.0:8000/health
============================================================
Waiting for Teams messages...
```

### Terminal 3: ngrok Tunnel
```bash
ngrok http 8000
```

ngrok will display something like:
```
Forwarding   https://a1b2c3d4.ngrok-free.app -> http://localhost:8000
```

**Copy the https URL** (e.g., `https://a1b2c3d4.ngrok-free.app`)

---

## STEP 6: Set the Messaging Endpoint in Azure

1. Go back to Azure Portal → Your Bot → **Configuration**
2. In **Messaging endpoint**, paste your ngrok URL + `/api/messages`:
   ```
   https://a1b2c3d4.ngrok-free.app/api/messages
   ```
3. Click **Apply** / **Save**

---

## STEP 7: Create and Install the Teams App

### 7a. Update the Manifest

1. Open `teams-app/manifest.json`
2. Replace **both** instances of `{{MICROSOFT_APP_ID}}` with your actual Application (client) ID
3. Save

### 7b. Package the App

Zip the contents of the `teams-app/` folder into a file called `miai-teams-app.zip`:

```bash
cd teams-app
zip miai-teams-app.zip manifest.json color.png outline.png
```

The zip must contain these 3 files at the **root level** (not inside a subfolder).

### 7c. Enable Custom App Sideloading in Teams (Admin)

If you're a Teams admin:
1. Go to https://admin.teams.microsoft.com
2. Navigate to **Teams apps** → **Setup policies**
3. Select **Global (Org-wide default)** or create a custom policy
4. Turn ON **"Upload custom apps"**
5. Save — it may take a few hours to propagate

If you're NOT an admin, ask your admin to enable sideloading for your account.

### 7d. Install in Teams

1. Open **Microsoft Teams** (desktop or web)
2. Click **"Apps"** in the left sidebar
3. Click **"Manage your apps"** (bottom-left)
4. Click **"Upload an app"** → **"Upload a custom app"**
5. Select your `miai-teams-app.zip` file
6. Click **"Add"**
7. MyAi should now appear as a chat contact!

---

## STEP 8: Test It!

1. In Teams, find **MyAi** in your chat list
2. Send: `Hello!`
3. You should see a response from your local Ollama model
4. Try: `/help` to see all commands
5. Try: `/status` to check connectivity
6. Try: `/allow /path/to/your/project` then ask it to read files

---

## Troubleshooting

### Bot doesn't respond
- Check Terminal 2 (MyAi) for error logs
- Check Terminal 3 (ngrok) — the webhook URL must be active
- Verify the messaging endpoint in Azure matches your ngrok URL exactly
- Make sure the App ID and Secret in `.env` match Azure

### "Unauthorized" errors
- Double-check the client secret value (not the secret ID)
- Make sure you're using Single Tenant and the tenant ID is correct
- Restart the MyAi server after changing `.env`

### Ollama not reachable
- Make sure `ollama serve` is running in Terminal 1
- Test: `curl http://localhost:11434/api/tags`
- Check if the model is pulled: `ollama list`

### ngrok URL changes
- Free ngrok gives a new URL every time you restart it
- You must update the Azure Bot messaging endpoint each time
- Consider upgrading ngrok for a static domain, or use Cloudflare Tunnel

### Teams says "App not found" or sideloading blocked
- Custom app upload must be enabled by a Teams admin
- Go to Teams Admin Center → Setup policies → Enable "Upload custom apps"
- This can take up to 24 hours to propagate

---

## What's Next?

Once the bot is responding in Teams:

1. `/allow ~/projects` — Grant access to your projects folder
2. Ask: "What files are in my projects folder?"
3. `/search on` — Enable web search
4. Ask: "Search for the latest Python release"
5. `/index ~/projects` — Index for RAG
6. Ask: "What does my README say about deployment?"

Happy building! 🐾
