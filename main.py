import sqlite3
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Form, BackgroundTasks, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr

app = FastAPI(
    title="SubShield API",
    description="Automated trial protection, analytics, and reminder notifications.",
    version="2.0.0"
)

DB_FILE = "subshield.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            service_name TEXT NOT NULL,
            end_date TEXT NOT NULL,
            end_timestamp REAL NOT NULL,
            estimated_cost REAL NOT NULL DEFAULT 15.00,
            is_strict_no_refund INTEGER NOT NULL,
            alert_sent INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_analytics_summary():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT end_timestamp, estimated_cost FROM trials")
    rows = cursor.fetchall()
    conn.close()

    now_ts = datetime.now().timestamp()
    forty_eight_hours_ts = (datetime.now() + timedelta(hours=48)).timestamp()

    total_active = len(rows)
    expiring_soon = 0
    total_saved = 0.0

    for end_ts, cost in rows:
        total_saved += cost
        if now_ts <= end_ts <= forty_eight_hours_ts:
            expiring_soon += 1

    return {
        "total_active": total_active,
        "expiring_soon": expiring_soon,
        "total_saved": round(total_saved, 2)
    }

# ------------------------------------------------------------------------------
# REST API & OPENAPI SCHEMAS
# ------------------------------------------------------------------------------
class TrialCreateSchema(BaseModel):
    service_name: str
    user_email: EmailStr
    trial_days: int = 7
    estimated_cost: float = 15.00
    is_strict_no_refund: bool = False

class TrialResponseSchema(BaseModel):
    id: int
    service_name: str
    user_email: str
    end_date: str
    estimated_cost: float
    is_strict_no_refund: bool
    alert_sent: bool

@app.get("/api/v1/trials", response_model=List[TrialResponseSchema], tags=["REST API"])
def get_all_trials_api():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, service_name, user_email, end_date, estimated_cost, is_strict_no_refund, alert_sent FROM trials")
    rows = cursor.fetchall()
    conn.close()

    return [
        TrialResponseSchema(
            id=r[0], service_name=r[1], user_email=r[2], end_date=r[3],
            estimated_cost=r[4], is_strict_no_refund=bool(r[5]), alert_sent=bool(r[6])
        ) for r in rows
    ]

# ------------------------------------------------------------------------------
# WEB DASHBOARD (ANIMATED HERO + START DATE & TRIAL DAYS)
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def web_dashboard():
    analytics = get_analytics_summary()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_email, service_name, end_date, estimated_cost, is_strict_no_refund FROM trials")
    trials = cursor.fetchall()
    conn.close()

    trial_cards = ""
    for trial_id, email, service, end_date, cost, is_strict in trials:
        badge = (
            '<span class="bg-red-500/20 text-red-400 text-xs px-2.5 py-1 rounded-full font-bold">⚠️ Strict (No Refunds)</span>'
            if is_strict
            else '<span class="bg-green-500/20 text-green-400 text-xs px-2.5 py-1 rounded-full font-bold">Standard Trial</span>'
        )
        trial_cards += f"""
        <div class="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-4 shadow-lg hover:border-emerald-500/50 transition duration-300">
            <div class="flex justify-between items-center mb-2">
                <h3 class="text-xl font-bold text-white">{service}</h3>
                {badge}
            </div>
            <p class="text-slate-400 text-sm mb-1">Account: <span class="text-slate-200">{email}</span></p>
            <p class="text-slate-400 text-sm mb-1">Expiration Date: <span class="text-amber-400 font-semibold">{end_date}</span></p>
            <p class="text-slate-400 text-sm mb-4">Value Protected: <span class="text-emerald-400 font-semibold">${cost:.2f}</span></p>
            <div class="flex items-center space-x-3">
                <a href="https://www.google.com/search?q=how+to+cancel+{service}+subscription" target="_blank" class="bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs py-2 px-4 rounded-lg font-medium transition">
                    Cancel Shortcut &rarr;
                </a>
                <form action="/web/delete/{trial_id}" method="post" class="inline">
                    <button type="submit" class="bg-red-500/10 hover:bg-red-500/20 text-red-400 text-xs py-2 px-3 rounded-lg font-medium transition border border-red-500/30">
                        Dismiss Shield
                    </button>
                </form>
            </div>
        </div>
        """

    if not trial_cards:
        trial_cards = '<p class="text-slate-500 italic text-center py-8">No subscriptions shielded yet. Add one above!</p>'

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SubShield | Automated Trial Protection</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @keyframes pulseGlow {{
                0%, 100% {{ transform: scale(1); filter: drop-shadow(0 0 15px rgba(16, 185, 129, 0.4)); }}
                50% {{ transform: scale(1.08); filter: drop-shadow(0 0 30px rgba(16, 185, 129, 0.8)); }}
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; transform: translateY(-10px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .animate-shield {{ animation: pulseGlow 3s infinite ease-in-out; }}
            .animate-fade-in {{ animation: fadeIn 1s ease-out forwards; }}
        </style>
    </head>
    <body class="bg-slate-900 text-slate-100 min-h-screen font-sans">
        <div class="max-w-3xl mx-auto py-12 px-4 animate-fade-in">
            
            <!-- ANIMATED WELCOME HERO SECTION -->
            <div class="text-center py-8 mb-8 bg-gradient-to-b from-slate-800/80 to-slate-900 border border-slate-700/60 rounded-3xl p-6 shadow-2xl relative overflow-hidden">
                <div class="inline-block text-6xl mb-3 animate-shield">🛡️</div>
                <h1 class="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 tracking-tight mb-2">
                    Welcome to SubShield
                </h1>
                <p class="text-slate-300 text-base max-w-lg mx-auto mb-4">
                    Never get surprise-charged for a forgotten subscription trial again.
                </p>
                <div class="inline-flex items-center space-x-2 bg-emerald-500/10 border border-emerald-500/30 px-4 py-1.5 rounded-full text-emerald-400 text-xs font-semibold">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                    <span>Automated Monitoring Active</span>
                </div>
            </div>

            <!-- ANALYTICS / INSIGHTS SUMMARY TAB -->
            <div class="grid grid-cols-3 gap-4 mb-8">
                <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-center hover:border-slate-600 transition">
                    <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1">Active Shields</p>
                    <p class="text-3xl font-black text-white">{analytics["total_active"]}</p>
                </div>
                <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-center hover:border-slate-600 transition">
                    <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1">Due in 48h</p>
                    <p class="text-3xl font-black text-amber-400">{analytics["expiring_soon"]}</p>
                </div>
                <div class="bg-slate-800/80 border border-slate-700 rounded-xl p-4 text-center hover:border-slate-600 transition">
                    <p class="text-xs text-slate-400 uppercase tracking-wider font-semibold mb-1">Est. Money Saved</p>
                    <p class="text-3xl font-black text-emerald-400">${analytics["total_saved"]:.2f}</p>
                </div>
            </div>

            <!-- FORM WITH START DATE & TRIAL DAYS -->
            <div class="bg-slate-800/60 border border-slate-700 rounded-2xl p-6 mb-8 backdrop-blur-sm">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-bold text-white">Shield a New Free Trial</h2>
                    <a href="/docs" target="_blank" class="text-xs bg-slate-800 hover:bg-slate-700 text-emerald-400 border border-slate-700 px-3 py-1.5 rounded-lg font-mono transition">
                        OpenAPI Docs &rarr;
                    </a>
                </div>
                
                <form action="/web/add" method="post" class="space-y-4">
                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label class="block text-xs text-slate-400 font-medium mb-1">Service Name</label>
                            <input type="text" name="service_name" placeholder="e.g. Netflix, Spotify" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 text-white focus:outline-none focus:border-emerald-500 transition">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 font-medium mb-1">Your Email</label>
                            <input type="email" name="user_email" placeholder="you@example.com" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-2 text-white focus:outline-none focus:border-emerald-500 transition">
                        </div>
                    </div>
                    <div class="grid grid-cols-4 gap-3">
                        <div>
                            <label class="block text-xs text-slate-400 font-medium mb-1">Start Date</label>
                            <input type="date" id="start_date_input" name="start_date" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white text-xs focus:outline-none focus:border-emerald-500 transition">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 font-medium mb-1">Trial Days</label>
                            <input type="number" name="trial_days" value="7" min="1" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-emerald-500 transition">
                        </div>
                        <div>
                            <label class="block text-xs text-slate-400 font-medium mb-1">Est. Cost ($)</label>
                            <input type="number" step="0.01" name="estimated_cost" value="15.00" required class="w-full bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-white focus:outline-none focus:border-emerald-500 transition">
                        </div>
                        <div class="flex items-center pt-5">
                            <label class="inline-flex items-center cursor-pointer">
                                <input type="checkbox" name="is_strict_no_refund" value="true" class="sr-only peer">
                                <div class="relative w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-500"></div>
                                <span class="ms-2 text-xs font-medium text-slate-300">Strict</span>
                            </label>
                        </div>
                    </div>
                    <button type="submit" class="w-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2.5 px-4 rounded-xl transition shadow-lg shadow-emerald-500/20">
                        Activate Shield & Schedule Reminders
                    </button>
                </form>
            </div>

            <!-- ACTIVE SHIELDS LIST -->
            <h2 class="text-xl font-bold text-white mb-4">Protected Subscriptions ({len(trials)})</h2>
            <div>{trial_cards}</div>
        </div>

        <script>
            // Set Start Date input default to today
            document.getElementById('start_date_input').value = new Date().toISOString().split('T')[0];
        </script>
    </body>
    </html>
    """

@app.post("/web/add", include_in_schema=False)
def web_add_trial(
    service_name: str = Form(...),
    user_email: str = Form(...),
    start_date: str = Form(...),
    trial_days: int = Form(7),
    estimated_cost: float = Form(15.00),
    is_strict_no_refund: str = Form(None)
):
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = start_dt + timedelta(days=trial_days)
    end_timestamp = end_dt.timestamp()
    formatted_date = end_dt.strftime("%B %d, %Y")
    is_strict = 1 if is_strict_no_refund == "true" else 0

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trials (user_email, service_name, end_date, end_timestamp, estimated_cost, is_strict_no_refund)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_email, service_name.capitalize(), formatted_date, end_timestamp, estimated_cost, is_strict))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/", status_code=303)

@app.post("/web/delete/{trial_id}", include_in_schema=False)
def web_delete_trial(trial_id: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trials WHERE id = ?", (trial_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/", status_code=303)