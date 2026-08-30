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
