import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI(title="SubShield")

DB_FILE = "subshield.db"

def get_db_columns(cursor):
    cursor.execute("PRAGMA table_info(trials)")
    return [col[1] for col in cursor.fetchall()]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            service_name TEXT NOT NULL,
            end_date TEXT NOT NULL,
            estimated_cost REAL DEFAULT 0.0,
            is_strict_no_refund INTEGER DEFAULT 0
        )
    """)
    cols = get_db_columns(cursor)
    if "is_strict_no_refund" not in cols:
        cursor.execute("ALTER TABLE trials ADD COLUMN is_strict_no_refund INTEGER DEFAULT 0")
    if "estimated_cost" not in cols:
        cursor.execute("ALTER TABLE trials ADD COLUMN estimated_cost REAL DEFAULT 0.0")
    if "end_date" not in cols:
        cursor.execute("ALTER TABLE trials ADD COLUMN end_date TEXT DEFAULT ''")
    conn.commit()
    conn.close()

init_db()

@app.get("/", response_class=HTMLResponse)
def web_dashboard():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cols = get_db_columns(cursor)
        
        select_cols = ["id", "user_email", "service_name"]
        select_cols.append("end_date" if "end_date" in cols else "end_timestamp")
        select_cols.append("estimated_cost" if "estimated_cost" in cols else "0.0 AS estimated_cost")
        select_cols.append("is_strict_no_refund" if "is_strict_no_refund" in cols else "0 AS is_strict_no_refund")
        
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM trials")
        trials = cursor.fetchall()
        conn.close()

        total_active = len(trials)
        total_saved = sum(float(t[4]) for t in trials if t[4] is not None)

        trial_cards = ""
        for t in trials:
            t_id, email, service, end_date, cost, is_strict = t
            cost_val = float(cost) if cost is not None else 0.0
            strict_flag = bool(is_strict)

            badge = (
                '<span class="bg-red-500/20 text-red-400 text-xs px-2.5 py-1 rounded-full font-bold">⚠️ Strict</span>'
                if strict_flag
                else '<span class="bg-emerald-500/20 text-emerald-400 text-xs px-2.5 py-1 rounded-full font-bold">Standard</span>'
            )

            trial_cards += f"""
            <div class="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-4 shadow-lg hover:border-emerald-500/50 transition duration-300">
                <div class="flex justify-between items-center mb-2">
                    <a href="/web/trials/{t_id}" class="text-xl font-bold text-white hover:text-emerald-400 transition">{service} &rarr;</a>
                    {badge}
                </div>
                <p class="text-slate-400 text-sm mb-1">Account: <span class="text-slate-200">{email}</span></p>
                <p class="text-slate-400 text-sm mb-4">Expiration Date: <span class="text-amber-400 font-semibold">{end_date}</span></p>
                <div class="flex items-center space-x-3">
                    <a href="/web/trials/{t_id}" class="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs py-2 px-4 rounded-lg font-medium transition">
                        View Entry Details &rarr;
                    </a>
                    <form action="/web/delete/{t_id}" method="post" class="inline">
                        <button type="submit" class="bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs py-2 px-3 rounded-lg font-medium transition border border-red-500/30">
                            Delete
                        </button>
                    </form>
                </div>
            </div>
            """

        if not trial_cards:
            trial_cards = '<p class="text-slate-500 text-sm italic">No active subscription shields added yet.</p>'

        return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>SubShield Dashboard</title>
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-slate-900 text-slate-100 min-h-screen font-sans py-10 px-4">
            <div class="max-w-3xl mx-auto space-y-8">
                <div class="text-center bg-slate-800 border border-slate-700 rounded-2xl p-8 shadow-xl">
                    <h1 class="text-4xl font-extrabold text-white mb-2">🛡️ Welcome to SubShield</h1>
                    <p class="text-slate-400 text-sm">Never get surprise-charged for a forgotten subscription trial again.</p>
                </div>

                <div class="grid grid-cols-3 gap-4 text-center">
                    <div class="bg-slate-800 border border-slate-700 p-4 rounded-xl">
                        <p class="text-xs text-slate-400 font-semibold uppercase">Active Shields</p>
                        <p class="text-2xl font-bold text-white">{total_active}</p>
                    </div>
                    <div class="bg-slate-800 border border-slate-700 p-4 rounded-xl">
                        <p class="text-xs text-slate-400 font-semibold uppercase">Est. Money Saved</p>
                        <p class="text-2xl font-bold text-emerald-400">${total_saved:.2f}</p>
                    </div>
                    <div class="bg-slate-800 border border-slate-700 p-4 rounded-xl">
                        <p class="text-xs text-slate-400 font-semibold uppercase">API Docs</p>
                        <a href="/docs" target="_blank" class="text-xs font-bold text-emerald-400 hover:underline block mt-2">OpenAPI Docs &rarr;</a>
                    </div>
                </div>

                <div class="bg-slate-800 border border-slate-700 rounded-2xl p-6 shadow-xl">
                    <h2 class="text-xl font-bold text-white mb-4">Shield a New Free Trial</h2>
                    <form action="/web/add" method="post" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-xs text-slate-400 font-semibold mb-1">Service Name</label>
                                <input type="text" name="service_name" placeholder="e.g. Netflix, Spotify" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-400 font-semibold mb-1">Your Email</label>
                                <input type="email" name="user_email" placeholder="you@example.com" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                            </div>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div>
                                <label class="block text-xs text-slate-400 font-semibold mb-1">Start Date</label>
                                <input type="date" name="start_date" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-400 font-semibold mb-1">Trial Days</label>
                                <input type="number" name="trial_days" value="7" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                            </div>
                            <div>
                                <label class="block text-xs text-slate-400 font-semibold mb-1">Est. Cost ($)</label>
                                <input type="number" step="0.01" name="estimated_cost" value="15.00" required class="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-emerald-500">
                            </div>
                        </div>
                        <div class="flex items-center space-x-2">
                            <input type="checkbox" id="strict" name="is_strict" class="rounded bg-slate-900 border-slate-700 text-emerald-500 focus:ring-0">
                            <label for="strict" class="text-xs text-slate-300 font-medium">Strict (No Refund Policy)</label>
                        </div>
                        <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2.5 rounded-xl transition">
                            Activate Shield & Schedule Reminders
                        </button>
                    </form>
                </div>

                <div>
                    <h2 class="text-xl font-bold text-white mb-4">Protected Subscriptions ({total_active})</h2>
                    {trial_cards}
                </div>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return HTMLResponse(content=f"<div style='color:white;background:#0f172a;padding:24px;font-family:sans-serif;'><h2>Dashboard Error</h2><p>{str(e)}</p><a href='/' style='color:#34d399;'>Reload Page</a></div>", status_code=500)

@app.post("/web/add")
def add_trial_web(
    service_name: str = Form(...),
    user_email: str = Form(...),
    start_date: str = Form(...),
    trial_days: str = Form("7"),
    estimated_cost: str = Form("15.00"),
    is_strict: Optional[str] = Form(None)
):
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except Exception:
        start_dt = datetime.now()

    try:
        days_int = int(trial_days)
    except Exception:
        days_int = 7

    try:
        cost_float = float(estimated_cost)
    except Exception:
        cost_float = 0.0

    end_dt = start_dt + timedelta(days=days_int)
    end_date_str = end_dt.strftime("%Y-%m-%d")
    strict_val = 1 if is_strict else 0

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cols = get_db_columns(cursor)
        
        insert_fields = ["user_email", "service_name", "estimated_cost", "is_strict_no_refund"]
        insert_values = [user_email, service_name, cost_float, strict_val]
        
        if "end_date" in cols:
            insert_fields.append("end_date")
            insert_values.append(end_date_str)
            
        if "end_timestamp" in cols:
            insert_fields.append("end_timestamp")
            insert_values.append(end_dt.isoformat())
            
        placeholders = ", ".join(["?"] * len(insert_fields))
        field_names = ", ".join(insert_fields)
        
        cursor.execute(f"INSERT INTO trials ({field_names}) VALUES ({placeholders})", tuple(insert_values))
        conn.commit()
        conn.close()
    except Exception as e:
        return HTMLResponse(content=f"<div style='color:white;background:#0f172a;padding:24px;font-family:sans-serif;'><h2>Failed to Save Entry</h2><p>{str(e)}</p><a href='/' style='color:#34d399;'>Return Home</a></div>", status_code=500)

    return RedirectResponse(url="/", status_code=303)

@app.get("/web/trials/{trial_id}", response_class=HTMLResponse)
def view_trial_detail(trial_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cols = get_db_columns(cursor)
    
    select_cols = ["id", "user_email", "service_name"]
    select_cols.append("end_date" if "end_date" in cols else "end_timestamp")
    select_cols.append("estimated_cost" if "estimated_cost" in cols else "0.0 AS estimated_cost")
    select_cols.append("is_strict_no_refund" if "is_strict_no_refund" in cols else "0 AS is_strict_no_refund")
    
    cursor.execute(f"SELECT {', '.join(select_cols)} FROM trials WHERE id = ?", (trial_id,))
    trial = cursor.fetchone()
    conn.close()

    if not trial:
        return HTMLResponse(content="<h1>Subscription not found</h1><a href='/'>&larr; Return Home</a>", status_code=404)

    t_id, email, service, end_date, cost, is_strict = trial
    cost_val = float(cost) if cost is not None else 0.0
    badge = "⚠️ Strict (No Refunds)" if is_strict else "Standard Trial"
    badge_bg = "bg-red-500/20 text-red-400" if is_strict else "bg-emerald-500/20 text-emerald-400"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>{service} Details | SubShield</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen font-sans py-12 px-4">
        <div class="max-w-xl mx-auto bg-slate-800 border border-slate-700 rounded-2xl p-8 shadow-2xl">
            <a href="/" class="text-xs text-emerald-400 hover:underline mb-4 inline-block">&larr; Back to Dashboard</a>
            
            <div class="flex justify-between items-center mb-6">
                <h1 class="text-3xl font-extrabold text-white">{service}</h1>
                <span class="{badge_bg} text-xs px-3 py-1 rounded-full font-bold">{badge}</span>
            </div>

            <div class="space-y-4 border-t border-b border-slate-700/60 py-6 mb-6">
                <div>
                    <p class="text-xs text-slate-400 uppercase font-semibold">Account Email</p>
                    <p class="text-lg text-slate-100 font-medium">{email}</p>
                </div>
                <div>
                    <p class="text-xs text-slate-400 uppercase font-semibold">Trial Expiration Date</p>
                    <p class="text-lg text-amber-400 font-semibold">{end_date}</p>
                </div>
                <div>
                    <p class="text-xs text-slate-400 uppercase font-semibold">Protected Cost Value</p>
                    <p class="text-lg text-emerald-400 font-bold">${cost_val:.2f}</p>
                </div>
            </div>

            <div class="flex items-center space-x-3">
                <a href="https://www.google.com/search?q=how+to+cancel+{service}+subscription" target="_blank" class="flex-1 text-center bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-sm py-2.5 rounded-xl font-bold transition">
                    Cancel {service} Guide &rarr;
                </a>
                <form action="/web/delete/{t_id}" method="post" class="inline">
                    <button type="submit" class="bg-red-500/10 hover:bg-red-500/20 text-red-400 text-sm py-2.5 px-4 rounded-xl font-medium transition border border-red-500/30">
                        Delete
                    </button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/web/delete/{trial_id}")
def delete_trial(trial_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trials WHERE id = ?", (trial_id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)