# SOICT Admission Chatbot (Rasa Pro CALM + RAG)

An enterprise-grade conversational AI assistant designed to handle university admission inquiries for the **School of Information and Communication Technology (SOICT) - HUST**. This assistant utilizes the latest Rasa CALM (Conversational AI with Language Models) architecture, integrated with a Retrieval-Augmented Generation (RAG) pipeline using **Google Gemini** and **Pinecone**.

---

## 🚀 Quick Setup & Configuration

### 1. Prerequisites
- **Python 3.10.11** (recommended)
- **Rasa Pro License** (Required for CALM features)
- **Google Gemini API Keys** (Supports up to 5 keys for automatic rotation)
- **Pinecone API Key** (For the vector database)
- **Node.js / Playwright** (Required only if running the `data/scrape_extras.py` scraper)

### 2. Environment Setup
The project uses two separate environments:

#### A. Chatbot Environment
```powershell
cd chatbot
python -m venv venv_rasa
.\venv_rasa\Scripts\activate
pip install -r requirements.txt
```

#### B. Data Scraper Environment
```powershell
cd data
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Environment Variables
Create a `.env` file in the `./chatbot` directory with the following structure:
```env
# Gemini API Keys (Rotation Pool)
GEMINI_API_KEY_1=your_key_1
GEMINI_API_KEY_2=your_key_2
# ... add up to 5 keys as GEMINI_API_KEY_X

# Pinecone Config
PINECONE_API_KEY=your_pinecone_key

# Rasa Pro License
RASA_PRO_LICENSE=your_license_string

# Legacy Validation Bypass
OPENAI_API_KEY=dummy
```

---

## 🛠 Usage Options

### Option A: Run Pre-built Version (Data & Model Ready)
*Use this if the Pinecone index is already populated and a model exists in `/models`.*

1. **Activate Virtual Environment:**
   ```powershell
   cd chatbot
   .\venv_rasa\Scripts\activate
   ```
2. **Start Action Server (Terminal 1):**
   ```powershell
   rasa run actions
   ```
3. **Start Rasa Assistant (Terminal 2):**
   ```powershell
   python rasa_env_wrapper.py inspect --debug
   ```
   *Visit `http://localhost:5005/webhooks/socketio/inspect.html` to chat.*

---

### Option B: Build from Scratch (New Data / New Model)
*Use this to crawl fresh data, re-ingest documents, and train a fresh intelligence model.*

1. **Scrape Data (Source Knowledge):**
   ```powershell
   cd data
   .\venv\Scripts\activate
   
   # Version 1: Main WP Scraper (Categories, Posts, Pages)
   python run_scraper.py
   
   # Version 2: Administrative Procedures & Student Handbook (Playwright SPA Scraper)
   python scrape_extras.py
   ```
   *Scraped results are saved as Markdown in `data/output/posts/` and `data/output/procedures/`.*

2. **Build Vector Database:**
   ```powershell
   cd ../chatbot
   python build_vectordb.py
   ```
   *This will chunk the text, generate embeddings via Gemini, and upload them to Pinecone.*

3. **Train the Model:**
   ```powershell
   rasa train
   ```
4. **Follow Option A** to launch the assistant.

---

## ✨ Features

- **CALM Architecture:** Intentless dialogue management for fluid, natural conversations.
- **Advanced RAG Pipeline:** Retrieves top-6 contextually relevant chunks from Pinecone for high-accuracy answers.
- **API Key Rotation:** Automatic failover between multiple Gemini keys to bypass "429 Quota Exceeded" limits.
- **Multilingual Support:** Strict Vietnamese-only generation for SOICT branding, while handling multiple greeting languages.
- **Deep Debugging:** Real-time terminal logging of Pinecone chunks, LLM prompts, and raw responses.

## 📁 Project Structure
- `data/`: Contains the SOICT website scraper (`run_scraper.py`) and crawled Markdown content.
- `chatbot/actions/actions.py`: Custom RAG logic, Chitchat handling, and API rotation.
- `chatbot/data/flows.yml`: Dialogue business logic and fallback patterns.
- `chatbot/rasa_env_wrapper.py`: Middleware for environment injection and litellm patching.
- `chatbot/build_vectordb.py`: Automated ingestion pipeline for knowledge base.

---
*Developed for IT5431 - Chatbot Development Project*
