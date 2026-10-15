# Regression Explorer · GitHub Pages + FastAPI

A bilingual-friendly (Traditional Chinese interface) CRISP-DM multiple linear regression laboratory. Upload UTF-8 CSV files or use a public HTTPS CSV URL, choose any numerical target and input features, then train and compare **LinearRegression, Ridge, Lasso, ElasticNet, BayesianRidge** with Scikit-learn.

## Features

- CSV URL or upload; configurable numerical target / numeric and categorical input columns.
- 80/20 (or 75/25, 70/30) hold-out test split; **5-fold CV** where sample size permits.
- Feature selection using **all subsets of up to 5 selected original input columns** (a categorical column counts as one; One-Hot Encoding happens within each CV training fold).
- Inner training-only CV selects hyperparameters and feature subset for each method and feature count. Test set is never used to select the winner.
- Combined **two-panel** plot: RMSE left, R² right; five methods on each plot.
- Best-per-feature-count results, all tested subsets, test predictions and JSON download.
- No raw datasets or generated user results are persisted by the API.

## Project layout

```text
index.html              GitHub Pages frontend
assets/style.css        UI
assets/app.js           browser fetch and Chart.js
backend/main.py         FastAPI + sklearn
backend/requirements.txt
backend/.env.example    CORS origin example
backend/Procfile        Render start command alternative
examples/50_Startups.csv
README.md
docs/deployment.md
```

## Run locally (Windows CMD)

Requires Python 3.11–3.13 recommended and pip.

**Terminal 1 (backend):**

```cmd
cd /d D:\AIOT1014\Regression-Explorer-FastAPI-GitHub\backend
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

Test API: http://127.0.0.1:8001/docs or http://127.0.0.1:8001/api/health

**Terminal 2 (frontend):**

```cmd
cd /d D:\AIOT1014\Regression-Explorer-FastAPI-GitHub
python -m http.server 8000
```

Open http://localhost:8000, enter API URL `http://127.0.0.1:8001`, click **Load URL** or upload an example CSV, choose target and input features, then **Train & Compare 5 Models**.

## Online hosting

- **GitHub Pages** hosts the static frontend from repository `main` and `/(root)`.
- **Render** (or another persistent HTTPS Python host) runs the FastAPI application with root directory `backend`, build command `pip install -r requirements.txt`, and start command `uvicorn main:app --host 0.0.0.0 --port $PORT`.
- Render backend environment `ALLOWED_ORIGINS=https://YOUR_USERNAME.github.io` (allow your exact origin; no trailing slash). `https://YOUR_USERNAME.github.io/REPO/` is a *page URL*, not a CORS origin.
- After deployment, enter `https://YOUR-BACKEND.onrender.com` in the **FastAPI URL** field; frontend remembers it for subsequent visits in your browser. For a preconfigured URL, edit `assets/app.js` default API variable.

See [deployment guide](docs/deployment.md) for detailed Git + GitHub Pages + Render steps.

## Evaluation details

Five methods: OLS, Ridge alpha (0.01, 0.1, 1, 10, 100), Lasso alpha (0.1, 1, 10, 100, 1000), ElasticNet alpha (0.01, 0.1, 1) × l1_ratio (0.2, 0.5, 0.8), BayesianRidge tol (1e-3, 1e-5). These are small demo grids, not globally optimal settings.

One-Hot Encoding and imputation/scaling are **inside a sklearn Pipeline** in each cross-validation fold. Classification targets are not supported. This is a regression-only teaching example. The selected subset counts original features, so 1 categorical field may create several encoded coefficients. Maximum 12 input columns, maximum feature count 5, at most 400 combinations, 5,000 rows, 3 MB CSV, 80 columns; remote URL must use public HTTPS. Missing numerical target rows are dropped. Results vary by split and dataset.

**Methodological caution:** Comparison between feature counts uses held-out test metrics for descriptive analysis; best selection uses *training CV RMSE*, not test RMSE. Re-running many interactive experiments against the same test split may still overfit researchers' decisions; for final academic reporting consider a separate final test set or nested CV.

**Security caution:** Built-in public-IP checks, HTTPS restriction, disabled redirects and response-size limits are basic SSRF mitigations, **not a production security boundary** against DNS rebinding or all infrastructure-specific bypasses. For public production deployment, allow-list approved data hosts (e.g. raw.githubusercontent.com), enforce outbound egress controls, auth, rate limiting and CPU/time budgets. Uploaded data is processed in memory; do not send confidential data to a shared demo backend.

## License

Example application code may be reused for educational projects. Third-party example dataset is from the linked public upstream repository; verify its own license before redistributing.
