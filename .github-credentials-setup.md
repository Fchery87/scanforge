# GitHub App Credentials Setup

Guide for setting up a GitHub App and obtaining the required credentials.

## Overview

To integrate with GitHub (e.g., for webhooks, API access, CI/CD), you need three credentials:

| Variable | Description |
|----------|-------------|
| `GITHUB_APP_ID` | Numeric ID for your GitHub App |
| `GITHUB_WEBHOOK_SECRET` | Secret string for validating webhook payloads |
| `GITHUB_PRIVATE_KEY` | RSA private key for authentication (base64-encoded for env vars) |

## Step 1: Create a GitHub App

1. Go to **GitHub Settings** → **Developer settings** → **GitHub Apps**
2. Click **New GitHub App**
3. Fill in the fields:

   | Field | Value |
   |-------|-------|
   | **GitHub App name** | e.g., `scanforge-dev` |
   | **Homepage URL** | `https://github.com/yourusername/scanforge` or `http://localhost` |
   | **Description** | `ScanForge GitHub integration (dev)` or any placeholder |

4. Under **Webhook**:
   - Check **Active**
   - **Webhook URL**: Use a webhook proxy URL (see below)
   - **Webhook secret**: Enter a random string (e.g., `openssl rand -hex 32`)
5. Set **Repository permissions** — request only the minimum permissions your app needs (e.g., Pull requests: Read & write). Avoid requesting broad access.
6. Click **Create GitHub App**

## Step 2: Get Credentials

### GITHUB_APP_ID
Found at the top of your GitHub App's settings page after creation. It's a numeric value (e.g., `123456`).

> **Note:** The **App ID** is different from the **Client ID** shown further down the page.

### GITHUB_WEBHOOK_SECRET
The secret string you entered in the Webhook section when creating/editing the app.

### GITHUB_PRIVATE_KEY
1. In your GitHub App settings, scroll to **Private keys**
2. Click **Generate a private key**
3. A `.pem` file downloads (contains `-----BEGIN RSA PRIVATE KEY-----`)
4. **Base64-encode it** before storing as an environment variable (see Step 4)

## Step 3: Development Webhook Proxy

For local development, you need a public URL that forwards GitHub webhooks to your machine.

### Option A: Smee.io (simple, no install)

1. Go to **https://smee.io**
2. Click **Start a new channel**
3. Copy the **Webhook Proxy URL** (e.g., `https://smee.io/abc123xyz`)
4. Use that URL as your **Webhook URL** in GitHub App settings

Then run the Smee client:

```bash
npx smee -u "https://smee.io/YOUR_CHANNEL_ID" -t "http://localhost:3000/api/webhooks/github"
```

> **Note:** Smee.io has no uptime guarantee and can be unreliable. For more robust local development, consider the alternatives below.

### Option B: ngrok (more reliable)

**Install (Ubuntu/Debian):**

```bash
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
  | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
  && echo "deb https://ngrok-agent.s3.amazonaws.com buster main" \
  | sudo tee /etc/apt/sources.list.d/ngrok.list \
  && sudo apt update \
  && sudo apt install ngrok
```

**Authenticate (one-time — requires a free account at ngrok.com):**

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN
```

Your auth token is available in the ngrok dashboard after signing up.

**Run:**

```bash
ngrok http 3000
# Copy the generated https:// URL and use it as your Webhook URL in GitHub App settings
```

### Option C: Gosmee (self-hosted, with replay)

```bash
# Install
go install github.com/chmouel/gosmee@latest

# Run
gosmee client https://smee.io/YOUR_CHANNEL_ID http://localhost:3000/api/webhooks/github
```

Gosmee supports replaying past webhook events, which is useful for debugging.

## Step 4: Configure Environment Variables

### Private Key Encoding

Many deployment platforms (Render, Vercel, AWS, etc.) handle multiline strings in environment variables unreliably. **Always base64-encode your private key** before storing it as an env var:

```bash
# Encode the key (outputs a single-line string)
base64 -w 0 your-private-key.pem
# Copy the output — this is your GITHUB_PRIVATE_KEY value
```

Then decode it in your application code before use:

```typescript
// Node.js / TypeScript
const privateKey = Buffer.from(process.env.GITHUB_PRIVATE_KEY!, 'base64').toString('utf8');
```

```python
# Python
import base64, os
private_key = base64.b64decode(os.environ['GITHUB_PRIVATE_KEY']).decode('utf-8')
```

### Local Development (.env)

For local development you can reference the `.pem` file directly by path (avoids needing to encode it):

```
GITHUB_APP_ID=your-app-id
GITHUB_WEBHOOK_SECRET=your-webhook-secret
GITHUB_PRIVATE_KEY_PATH=/path/to/your/private-key.pem
```

> If your code only supports `GITHUB_PRIVATE_KEY` (not `GITHUB_PRIVATE_KEY_PATH`), base64-encode locally too and store the encoded value in `.env`.

### Production (Render Secrets)

Add as secrets in your Render service environment:

| Secret Name | Value |
|-------------|-------|
| `GITHUB_APP_ID` | Numeric ID from app settings |
| `GITHUB_WEBHOOK_SECRET` | Secret string from app settings |
| `GITHUB_PRIVATE_KEY` | Base64-encoded `.pem` contents (output of `base64 -w 0 key.pem`) |

## Notes

- **Homepage URL** and **Description** can be placeholder values for development — they don't affect functionality
- **Minimum permissions**: Only request what the app actually needs. You can always add more later.
- **Never commit** private keys, `.pem` files, or secrets to version control — add `*.pem` to `.gitignore`
- Installation tokens expire after **1 hour**; your app must handle token refresh automatically
- Always **verify webhook signatures** using the `GITHUB_WEBHOOK_SECRET` — don't rely on IP whitelisting
- You can always update app details later when ready to publish
