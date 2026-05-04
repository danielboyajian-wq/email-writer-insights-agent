# Deploy to Streamlit Cloud

End result: a public URL like `https://your-app.streamlit.app` that you can hit from anywhere, gated by a single shared password.

## ⚠️ Before you start

**Rotate your Anthropic API key.** Go to https://console.anthropic.com → API Keys → revoke the old key → create a new one. The new key is what you'll paste into Streamlit secrets — never put it in the repo.

## Step 1 — Create a private GitHub repo

1. Go to https://github.com/new
2. Repository name: `email-insights-agent` (or whatever)
3. **Private** ← important. Your tone examples and 6sense context shouldn't be public.
4. Do NOT check "Add a README" or ".gitignore" — we already have those.
5. Click "Create repository"
6. Copy the URL it shows (looks like `https://github.com/YOUR_USERNAME/email-insights-agent.git`)

## Step 2 — Push the code

Open Terminal and paste these commands one block at a time. Replace `YOUR_USERNAME` and the repo name with yours.

```bash
cd "~/Desktop/email insights agent"
git init
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/email-insights-agent.git
git push -u origin main
```

If git asks you to authenticate, easiest path is to install the GitHub CLI (`brew install gh`) then run `gh auth login`. Or use a Personal Access Token — GitHub docs walk you through it.

## Step 3 — Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Click "Sign in with GitHub" → authorize Streamlit
3. Click "New app"
4. Pick the repo you just pushed
5. Branch: `main`
6. Main file path: `app.py`
7. Click "Advanced settings" → paste this into the **Secrets** field:

```toml
ANTHROPIC_API_KEY = "sk-ant-...your-new-key..."
APP_PASSWORD = "pick-something-you-can-remember"
```

8. Click "Deploy"

First deploy takes ~2 minutes (it installs Python deps). When it's ready you'll get a URL.

## Step 4 — Use it

- Open the URL
- Enter the password you set in `APP_PASSWORD`
- You're in

## Updating the app later

Whenever you want to push changes (new tone examples, persona tweaks, etc.):

```bash
cd "~/Desktop/email insights agent"
git add .
git commit -m "describe what changed"
git push
```

Streamlit Cloud auto-redeploys on push, takes ~30 seconds.

## Useful settings

In the Streamlit Cloud app settings:

- **Sharing**: keep it "Anyone with the link" (the password gate is your real auth)
- **Resource limits**: free tier is fine for personal use
- **Custom domain**: paid feature; not needed for a POC

## Cost expectations

Streamlit Cloud: free.
Anthropic API: each draft costs ~$0.05–$0.10 with Sonnet 4.6. Each insights run costs ~$0.10–$0.20 (web_search adds tokens). Set a monthly cap in https://console.anthropic.com → Billing if you want a hard ceiling.

## If something goes wrong

- **Push fails with "permission denied"**: GitHub auth issue. Use `gh auth login` or set up an SSH key.
- **Streamlit shows a Python error**: check the "Manage app" → logs in the Streamlit Cloud dashboard.
- **Password doesn't work**: secrets are case-sensitive. Make sure no leading/trailing spaces.
- **API key rejected**: confirm the key is active in console.anthropic.com.
