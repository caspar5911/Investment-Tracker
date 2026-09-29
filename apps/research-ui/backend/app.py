from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from investment_tracker.independent_audit.post_generation3.phase7_collector import Generation4Phase7CollectorError, prospective_status
app=FastAPI(title="Investment Tracker UI API",version="0.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173"],allow_methods=["GET"],allow_headers=["*"])
@app.get("/api/health")
def health(): return {"status":"ok","mode":"PAPER_ONLY"}
@app.get("/api/phase7/status")
def phase7_status():
    try: return prospective_status()
    except Generation4Phase7CollectorError as exc: return {"status":"PHASE7_UNKNOWN_ABSTAIN","detail":str(exc)}
    except Exception: return {"status":"PHASE7_UNKNOWN_ABSTAIN","detail":"status unavailable"}