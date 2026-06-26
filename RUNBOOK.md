# Audiobook AI - Runbook

## Start the Server
Start the FastAPI server on port 8000:
```bash
cd /home/comma/Documents/kokoro_test
source .venv/bin/activate
uvicorn audiobook.server:app --host 0.0.0.0 --port 8000
```

Open the local UI at `http://localhost:8000`. Google/Firebase sign-in may reject `http://127.0.0.1:8000` unless `127.0.0.1` is added in Firebase Authentication authorized domains.

## Public HTTPS (Cloudflare Tunnel)
To expose this securely over HTTPS (required for phone lock-screen audio and PWA offline features), run a Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```
This gives you a public HTTPS URL (e.g. `https://random-words.trycloudflare.com`). Visit this URL on your phone to use the UI.

## Authentication (Optional)
If you want to protect your server from public access, set an authentication token before starting the server:

```bash
export AUDIOBOOK_TOKEN="my_super_secret_password"
uvicorn audiobook.server:app --host 0.0.0.0 --port 8000
```
Then, access your UI using the token query parameter on your first visit:
`https://random-words.trycloudflare.com/?token=my_super_secret_password`
The browser will cache the token for future requests.
