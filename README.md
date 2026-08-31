# 🦀 Claw Royale Bot v6.1 - AI Auto-Pilot

Bot otomatis untuk Claw Royale dengan **AI Auto-Pilot** yang cerdas.

## ✨ Fitur

### 🤖 AI Auto-Pilot
- **Perception Layer** - Memahami lingkungan game secara real-time
- **Analysis Layer** - Menganalisis situasi, threat, dan opportunity
- **Decision Engine** - Mengambil keputusan optimal berdasarkan AI
- **Risk Assessment** - Menilai risiko setiap action
- **Knowledge Base** - Belajar dari pengalaman

### 🎮 Game Features
- Auto-join free/paid rooms
- Adaptive survival-first strategy
- Cave detection & exit handling
- TARGET_DEAD retry handling
- Resume target dead handling (paid rooms)
- Auto-claim WELCOME bundle & rewards
- Loadout optimization

### 📊 Monitoring
- Health check endpoint (`/health`, `/ready`, `/metrics`)
- Performance tracking
- Knowledge insights

## 🚀 Deploy ke Railway

1. **Fork repository** ini ke GitHub
2. **Buka Railway** → "Deploy from GitHub"
3. **Set environment variables**:
   - `CLAW_API_KEY`: API key dari Claw Royale (wajib)
   - `ENTRY_TYPE`: `free` atau `paid` (default: free)
   - `PREFERRED_MODE`: `offchain` atau `onchain`
   - `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`

## 📁 Struktur
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLAW ROYALE BOT v6.1                           │
│                       Hybrid AI + Competitive v7                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ✅ LOGIN & AUTHENTICATION                                              │
│  │  ├─ Auto login dengan API key                                       │
│  │  └─ Auto register agent token                                       │
│                                                                         │
│  ✅ GAME MANAGEMENT                                                     │
│  │  ├─ Join game (free/paid)                                           │
│  │  ├─ Rejoin (resume after timeout)                                   │
│  │  └─ Auto restart after death                                        │
│                                                                         │
│  ✅ HYBRID AI ENGINE                                                    │
│  │  ├─ AI Auto-Pilot (ML-based)                                        │
│  │  ├─ Competitive v7 (Heuristic)                                      │
│  │  ├─ Threat Assessment                                               │
│  │  ├─ Risk Assessment                                                 │
│  │  └─ Priority-based decision                                         │
│                                                                         │
│  ✅ ITEM MANAGEMENT                                                     │
│  │  ├─ Item scanning & tracking                                        │
│  │  ├─ Use item (heal)                                                 │
│  │  ├─ Auto-equip best items                                           │
│  │  └─ Inventory management                                            │
│                                                                         │
│  ✅ STRATEGY                                                            │
│  │  ├─ Survival priority (heal first)                                  │
│  │  ├─ Loot priority (collect items)                                   │
│  │  ├─ Kill priority (attack enemies)                                  │
│  │  ├─ Explore priority (ruin farming)                                 │
│  │  └─ Guardian avoidance                                              │
│                                                                         │
│  ✅ MONITORING                                                          │
│  │  ├─ Health check (/health)                                          │
│  │  ├─ Metrics (/metrics)                                              │
│  │  ├─ Stats (/stats)                                                  │
│  │  └─ Dashboard (/dashboard)                                          │
│                                                                         │
│  ✅ KNOWLEDGE BASE                                                      │
│  │  ├─ Learning from experience                                        │
│  │  ├─ Performance tracking                                            │
│  │  └─ Pattern recognition                                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
============================================================
📊 Log yang Diharapkan

🦀 Starting Claw Royale Bot v6.1 - Hybrid AI
============================================================
📊 AI Knowledge:
   - Win Rate: 0.0%
   - Avg Survival: 0 turns
   - Kills/Game: 0.0
   - Success Rate: 0.0%
   - Total Games: 0
============================================================
✅ Health server started on port 8080
🔐 Starting authentication flow...
✅ LOGIN SUCCESSFUL
   Account: buy6_9sell
   ID: 6923280f-...
   Wallet: 0x1bdb...
============================================================
🎁 Checking rewards...
🎁 Welcome bundle claimed successfully!
🔧 Checking loadout...
✅ Loadout already full
🔧 Auto-equipping best items...
✅ Auto-equipped: ['Weapon: Moltz Expert']
============================================================
🚀 Starting Hybrid AI Auto-Pilot...
🧠 AI Engine: AI Auto-Pilot + Competitive v7
🎮 Ready to join games...
============================================================
🔧 Creating driver instance...
✅ Driver instance created
✅ Health server connected to driver
🚀 Starting driver task...
✅ Driver task created and scheduled
⏳ Waiting for driver to complete...
🚀 Driver run() started!
🔄 Driver loop iteration #1
📥 Checking version...
✅ Version: 1.15.0
🔍 Determining game state...
📊 State: GameState.READY_FREE -> start_free
🎮 Joining free game...
✅ WebSocket connected!
📤 Sent hello: free
⏳ Queued, waiting for match...
✅ assigned to game xxx-xxx-xxx
🎮 Starting Hybrid AI-powered gameplay loop...
🧠 Hybrid AI = AI Auto-Pilot + Competitive v7
👻 Only detecting OWN death, ignoring other agents
🧠 Hybrid AI [⚖️ Balanced]: pickup (Conf: 0.80, Risk: 0.33, Value: 0.67)
📤 Sending action: {'type': 'pickup', 'itemInstanceId': '...'}

============================================================
📋 Cek Endpoint
============================================================
# Health Check
curl http://localhost:8080/health

# Metrics
curl http://localhost:8080/metrics

# Stats
curl http://localhost:8080/stats

# Dashboard (HTML)
curl http://localhost:8080/dashboard
# atau buka di browser: http://localhost:8080/dashboard


