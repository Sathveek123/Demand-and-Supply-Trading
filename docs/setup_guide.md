# Deployment & Setup Guide — SMC Trading Bot v2.1

## 1. Environment Configuration (`.env`)

Create a `.env` file in the root directory:

```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token_here"
TELEGRAM_CHAT_IDS="7168024869,1191689637"
GEMINI_API_KEY="your_gemini_api_key_1,your_gemini_api_key_2,your_gemini_api_key_3"
PORT=8000
HOST="0.0.0.0"
```

---

## 2. GitHub Push Instructions

```powershell
# Authenticate GitHub CLI
Remove-Item Env:\GITHUB_TOKEN -ErrorAction SilentlyContinue
gh auth setup-git

# Commit & Push
git add .
git commit -m "Update SMC Trading Bot v2.1 code & documentation"
git push origin main
```

---

## 3. Render Cloud Deployment

1. Log into **[Render.com](https://render.com)**.
2. Select **New Web Service** $\rightarrow$ Connect GitHub repo `Demand-and-Supply-Trading`.
3. Set configuration:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
4. Add Environment Variables under **Settings** $\rightarrow$ **Environment Variables**.
5. Deploy Web Service.

---

## 4. 24/7 UptimeRobot Safeguard Setup

1. Go to **[UptimeRobot.com](https://uptimerobot.com)**.
2. Click **+ Add New Monitor**:
   - **Type**: `HTTP(s)`
   - **Name**: `SMC Bot Keep-Alive`
   - **URL**: `https://your-app-name.onrender.com/`
   - **Interval**: `Every 5 minutes`
3. Click **Create Monitor**. Render will now run 24/7/365 without sleeping!
