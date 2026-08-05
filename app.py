import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Stock Dashboard")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API ENDPOINTS ---

@app.get("/api/stocks")
def get_stocks():
    return [
        {
            "symbol": "TATAMOTORS",
            "name": "Tata Motors Limited",
            "price": "721.50",
            "change": "+0.49%",
            "status": "positive",
            "screener_url": "https://www.screener.in/company/TATAMOTORS/",
            "tradingview_url": "https://in.tradingview.com/symbols/NSE-TATAMOTORS/"
        },
        {
            "symbol": "HYUNDAI",
            "name": "Hyundai Motor India",
            "price": "2,201.50",
            "change": "+0.81%",
            "status": "positive",
            "screener_url": "https://www.screener.in/company/HYUNDAI/",
            "tradingview_url": "https://in.tradingview.com/symbols/NSE-HYUNDAI/"
        },
        {
            "symbol": "COALINDIA",
            "name": "Coal India Ltd",
            "price": "412.65",
            "change": "-1.10%",
            "status": "negative",
            "screener_url": "https://www.screener.in/company/COALINDIA/",
            "tradingview_url": "https://in.tradingview.com/symbols/NSE-COALINDIA/"
        }
    ]

class ChatQuery(BaseModel):
    prompt: str

@app.post("/api/ai-chat")
def ai_assistant(query: ChatQuery):
    user_msg = query.prompt.lower()
    if "top performers" in user_msg or "performer" in user_msg:
        reply = "Currently, TATA MOTORS (+0.49%) and HYUNDAI (+0.81%) are top gainers."
    elif "strategy" in user_msg or "trade" in user_msg:
        reply = "Strategy execution engine is active. No active signals triggered right now."
    else:
        reply = f"Market AI Assistant: Analyzing response for '{query.prompt}'..."
    return {"response": reply}

# --- FRONTEND (SINGLE FILE SERVING HTML/UI) ---

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Stock Screener & Strategy Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-neutral-900 text-white min-h-screen p-6 font-sans">
        <div class="max-w-6xl mx-auto">
            <h1 class="text-2xl font-bold mb-6 text-gray-100">Market Screener & Trading Strategy Dashboard</h1>

            <!-- Stock Cards Container -->
            <div id="stock-grid" class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                <!-- Stock cards dynamically injected here -->
            </div>
        </div>

        <!-- AI Assistant Floating Widget -->
        <div class="fixed bottom-6 right-6">
            <button id="chat-toggle" onclick="toggleChat()" class="bg-blue-600 hover:bg-blue-500 text-white px-5 py-3 rounded-full shadow-lg font-bold flex items-center gap-2">
                💬 AI Assistant
            </button>
            
            <div id="chat-box" class="hidden bg-neutral-800 border border-neutral-700 rounded-lg w-80 h-96 flex flex-col shadow-2xl mt-2">
                <div class="bg-neutral-700 p-3 flex justify-between items-center rounded-t-lg">
                    <span class="font-bold text-sm">Trading Assistant AI</span>
                    <button onclick="toggleChat()" class="text-gray-400 hover:text-white">✕</button>
                </div>
                <div id="messages" class="flex-1 p-3 overflow-y-auto space-y-2 text-sm">
                    <div class="bg-neutral-700 p-2 rounded self-start mr-8">
                        Hi! Ask me about top performers, screeners, or strategy execution.
                    </div>
                </div>
                <div class="p-2 border-t border-neutral-700 flex gap-2">
                    <input id="chat-input" type="text" placeholder="Ask AI..." class="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm flex-1 text-white focus:outline-none" onkeypress="handleKeyPress(event)">
                    <button onclick="sendMessage()" class="bg-blue-600 px-3 py-1 rounded text-xs font-semibold hover:bg-blue-500">Send</button>
                </div>
            </div>
        </div>

        <script>
            // Fetch and display stock data
            async function loadStocks() {
                const res = await fetch('/api/stocks');
                const stocks = await res.json();
                const grid = document.getElementById('stock-grid');
                grid.innerHTML = '';

                stocks.forEach(s => {
                    const statusClass = s.status === 'positive' ? 'bg-emerald-900 text-emerald-300' : 'bg-rose-900 text-rose-300';
                    const card = `
                        <div class="bg-neutral-800 p-4 rounded-lg border border-neutral-700">
                            <div class="flex justify-between items-center mb-2">
                                <span class="font-bold text-lg text-white">${s.symbol}</span>
                                <span class="text-xs px-2 py-0.5 rounded ${statusClass}">${s.change}</span>
                            </div>
                            <p class="text-gray-400 text-xs mb-3">${s.name}</p>
                            <p class="text-xl font-bold mb-4">&#8377;${s.price}</p>
                            <div class="flex gap-2 text-xs border-t border-neutral-700 pt-3">
                                <a href="${s.tradingview_url}" target="_blank" class="text-blue-400 hover:underline">TradingView</a>
                                <span class="text-gray-600">&bull;</span>
                                <a href="${s.screener_url}" target="_blank" class="text-blue-400 hover:underline">Screener.in</a>
                            </div>
                        </div>
                    `;
                    grid.innerHTML += card;
                });
            }

            // Chatbot toggling and logic
            function toggleChat() {
                const box = document.getElementById('chat-box');
                box.classList.toggle('hidden');
            }

            function handleKeyPress(e) {
                if (e.key === 'Enter') sendMessage();
            }

            async function sendMessage() {
                const input = document.getElementById('chat-input');
                const text = input.value.trim();
                if (!text) return;

                const msgContainer = document.getElementById('messages');
                msgContainer.innerHTML += `<div class="bg-blue-600 p-2 rounded self-end ml-8 text-right">${text}</div>`;
                input.value = '';
                msgContainer.scrollTop = msgContainer.scrollHeight;

                const res = await fetch('/api/ai-chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: text })
                });
                const data = await res.json();

                msgContainer.innerHTML += `<div class="bg-neutral-700 p-2 rounded self-start mr-8">${data.response}</div>`;
                msgContainer.scrollTop = msgContainer.scrollHeight;
            }

            // Initial load
            loadStocks();
        </script>
    </body>
    </html>
    """
@app.get("/", response_class=HTMLResponse)
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username in USERS and USERS[username] == password:
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid credentials! Try admin / admin123"
    return render_template_string(TEMPLATE, page="login", error=error)

@app.get("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    marquee_stocks, all_stocks = scan_stocks_parallel()
    return render_template_string(TEMPLATE, page="dashboard", marquee_stocks=marquee_stocks, all_stocks=all_stocks)

@app.get("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
