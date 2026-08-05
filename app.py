import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dhanhq import DhanContext, dhanhq  # Dhan SDK

app = FastAPI()

# Allow Frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Initialize Broker API (Dhan Example)
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")
dhan_context = DhanContext(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
dhan = dhanhq(dhan_context)

# 2. Stock Data Model & External Hyperlinks Map
@app.get("/api/stock/{symbol}")
def get_stock_details(symbol: str):
    symbol_clean = symbol.upper()
    return {
        "symbol": symbol_clean,
        "external_links": {
            "screener": f"https://www.screener.in/company/{symbol_clean}/",
            "tradingview": f"https://in.tradingview.com/symbols/NSE-{symbol_clean}/",
            "chartink": f"https://chartink.com/stocks/{symbol_clean}.html"
        }
    }

# 3. Strategy Trigger & Demat Order Execution
class StrategySignal(BaseModel):
    security_id: str  # e.g., '1333' for HDFC Bank
    symbol: str
    action: str      # BUY or SELL
    quantity: int

@app.post("/api/execute-strategy")
def execute_strategy(signal: StrategySignal):
    try:
        # Places order directly in your Demat / Trading Account
        order = dhan.place_order(
            security_id=signal.security_id,
            exchange_segment=dhan.NSE,
            transaction_type=dhan.BUY if signal.action == "BUY" else dhan.SELL,
            quantity=signal.quantity,
            order_type=dhan.MARKET,
            product_type=dhan.INTRA,
            price=0
        )
        return {"status": "SUCCESS", "order_details": order}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. AI Chatbot API Endpoint
class ChatQuery(BaseModel):
    prompt: str

@app.post("/api/ai-chat")
def ai_assistant(query: ChatQuery):
    user_msg = query.prompt.lower()
    
    # Custom logic or connection to OpenAI / Gemini API
    if "top performers" in user_msg:
        reply = "Currently, TATA MOTORS (+0.49%) and HYUNDAI (+0.81%) are showing strong bullish momentum."
    elif "strategy" in user_msg:
        reply = "Your active EMA Crossover strategy triggered 1 BUY order today on COALINDIA."
    else:
        reply = f"I am your Market AI. Analyzing '{query.prompt}'..."

    return {"response": reply}
    import React, { useState } from 'react';

const stocks = [
  { symbol: "TATAMOTORS", name: "Tata Motors Limited", price: "721.50", change: "+0.49%", status: "positive" },
  { symbol: "HYUNDAI", name: "Hyundai Motor India", price: "2,201.50", change: "+0.81%", status: "positive" },
  { symbol: "COALINDIA", name: "Coal India Ltd", price: "412.65", change: "-1.10%", status: "negative" }
];

export default function StockDashboard() {
  const [chatOpen, setChatOpen] = useState(false);
  const [messages, setMessages] = useState([{ sender: 'ai', text: 'Hi! Ask me about stock screeners, signals, or strategy status.' }]);
  const [input, setInput] = useState('');

  const handleSendMessage = async () => {
    if (!input.trim()) return;
    const userMessage = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMessage]);
    
    // Call FastAPI backend AI endpoint
    const res = await fetch('http://localhost:8000/api/ai-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: input })
    });
    const data = await res.json();
    
    setMessages(prev => [...prev, { sender: 'ai', text: data.response }]);
    setInput('');
  };

  return (
    <div className="bg-neutral-900 text-white min-h-screen p-6 font-sans">
      <h1 className="text-xl font-bold mb-6 text-gray-200">Market Screener & Strategy Dashboard</h1>

      {/* Stock Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {stocks.map((stock) => (
          <div key={stock.symbol} className="bg-neutral-800 p-4 rounded-lg border border-neutral-700">
            <div className="flex justify-between items-center mb-2">
              <span className="font-bold text-lg">{stock.symbol}</span>
              <span className={`text-sm px-2 py-0.5 rounded ${stock.status === 'positive' ? 'bg-emerald-900 text-emerald-300' : 'bg-rose-900 text-rose-300'}`}>
                {stock.change}
              </span>
            </div>
            <p className="text-gray-400 text-xs mb-3">{stock.name}</p>
            f"<p class='text-xl font-bold mb-4'>\u20b9{stock['price']}</p>"

            {/* Hyperlinks for Manual Stock Checks */}
            <div className="flex gap-2 text-xs border-t border-neutral-700 pt-3">
              <a 
                href={`https://in.tradingview.com/symbols/NSE-${stock.symbol}/`} 
                target="_blank" 
                rel="noreferrer" 
                className="text-blue-400 hover:underline"
              >
                TradingView
              </a>
              <span className="text-gray-600">•</span>
              <a 
                href={`https://www.screener.in/company/${stock.symbol}/`} 
                target="_blank" 
                rel="noreferrer" 
                className="text-blue-400 hover:underline"
              >
                Screener.in
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* AI Assistant Floating Widget */}
      <div className="fixed bottom-6 right-6">
        {!chatOpen ? (
          <button 
            onClick={() => setChatOpen(true)}
            className="bg-blue-600 hover:bg-blue-500 text-white p-4 rounded-full shadow-lg font-bold"
          >
            💬 AI Assistant
          </button>
        ) : (
          <div className="bg-neutral-800 border border-neutral-700 rounded-lg w-80 h-96 flex flex-col shadow-2xl">
            <div className="bg-neutral-700 p-3 flex justify-between items-center rounded-t-lg">
              <span className="font-bold text-sm">Trading Assistant AI</span>
              <button onClick={() => setChatOpen(false)} className="text-gray-400 hover:text-white">✕</button>
            </div>
            <div className="flex-1 p-3 overflow-y-auto space-y-2 text-sm">
              {messages.map((m, idx) => (
                <div key={idx} className={`p-2 rounded ${m.sender === 'user' ? 'bg-blue-600 self-end ml-8' : 'bg-neutral-700 self-start mr-8'}`}>
                  {m.text}
                </div>
              ))}
            </div>
            <div className="p-2 border-t border-neutral-700 flex gap-2">
              <input 
                value={input} 
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask AI..."
                className="bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-sm flex-1 text-white focus:outline-none"
              />
              <button onClick={handleSendMessage} className="bg-blue-600 px-3 py-1 rounded text-xs">Send</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

@app.route("/", methods=["GET", "POST"])
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

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    
    marquee_stocks, all_stocks = scan_stocks_parallel()
    return render_template_string(TEMPLATE, page="dashboard", marquee_stocks=marquee_stocks, all_stocks=all_stocks)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
