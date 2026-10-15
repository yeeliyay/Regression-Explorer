# Deployment guide: GitHub Pages + Render (Windows CMD)

## 1. Push repository to GitHub

Extract ZIP into `D:\AIOT1014\Regression-Explorer-FastAPI-GitHub`, then create an empty **public** repository on GitHub, for example `Regression-Explorer-FastAPI-GitHub`.

```cmd
cd /d D:\AIOT1014\Regression-Explorer-FastAPI-GitHub
git init
git add .
git commit -m "Build regression explorer frontend and FastAPI backend"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/Regression-Explorer-FastAPI-GitHub.git
git push -u origin main
```

If `origin` already exists, inspect `git remote -v` and change it with `git remote set-url origin URL` instead of adding again.

## 2. Frontend on GitHub Pages

GitHub repository → **Settings → Pages → Build and deployment → Deploy from a branch → main → /(root) → Save**.

Open `https://YOUR_USERNAME.github.io/Regression-Explorer-FastAPI-GitHub/` after deployment completes.

## 3. Backend on Render

Render → New → Web Service → select the GitHub repository.

- Language/runtime: Python
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Environment variable `ALLOWED_ORIGINS`: `https://YOUR_USERNAME.github.io`

Select a plan appropriate for the CPU and expected demand. Free tiers may cold-start, sleep or have usage limits; check the provider's current policy.

Once deployed, verify `https://YOUR-SERVICE.onrender.com/api/health` returns `{"status":"ok"}`.

## 4. Connect frontend to backend

On your GitHub Pages website, enter the HTTPS backend root in the **FastAPI URL** field, for example `https://YOUR-SERVICE.onrender.com` — without `/api/train` or trailing slash. Browser saves this setting locally. Click **Load URL**, use the provided GitHub Raw CSV example, select **Profit**, features, and **Train**.

For a baked-in backend address, update the `api` initializer near the top of `assets/app.js` with your deployed API root, commit and push again.

## 5. Troubleshooting

- **Failed to fetch / CORS:** Verify Render is running; verify `ALLOWED_ORIGINS` has only the origin e.g. `https://USER.github.io`, not `/REPO/`.
- **404 on backend:** Use API root (`https://service.onrender.com`), not a file URL.
- **422:** Your target must be numeric; check distinct categorical values (<=25), rows (>=12), max selected feature count/subset count.
- **CSV URL:** Use public **HTTPS raw CSV**, not GitHub HTML `/blob/` page. Redirected URLs are intentionally refused.
- **Slow or timeout:** Reduce selected input fields or max feature count. The backend performs many CV fits.
- **GitHub Pages 404:** Use `main` root deployment and ensure `index.html` is at the repo root; allow build a few minutes.

## Optional hardening before opening to anonymous users

Use approved-host allow-list with DNS/IP egress controls, an API gateway with auth and rate-limits, workload quotas and job queues, monitoring, a strict CORS allow-list, and isolate untrusted workloads. Current demo API is synchronous and may exceed small free-tier request timeouts.
