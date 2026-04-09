# SOICT Admission Chatbot (Rasa Pro CALM + RAG)

An enterprise-grade conversational AI assistant designed to handle university admission inquiries for the **School of Information and Communication Technology (SOICT) - HUST**. This assistant utilizes the latest Rasa CALM (Conversational AI with Language Models) architecture, integrated with a Retrieval-Augmented Generation (RAG) pipeline using **Google Gemini** and **Pinecone**.

---

## 🚀 Quick Setup & Configuration

### 1. Prerequisites
- **Python 3.10.11** (recommended)
- **Rasa Pro License** (Required for CALM features)
- **Google API Keys** (Supports up to 5 keys for automatic rotation)
- **Pinecone API Key** (For the vector database)
- **Node.js / Playwright** (Required only if running the `data/scrape_extras.py` scraper)

## 🚀 Setup & Installation

Before running the assistant, you must set up both the **Chatbot** and **Data Scraper** environments.

### 1. Prerequisites
- **Python 3.10.11** (Required)
- **Rasa Pro License** (Required)
- **API Keys**: Google Gemini (up to 5), Pinecone, and a dummy OpenAI key.

### 2. Install Dependencies (Mandatory)

#### A. Initialize Chatbot Environment
Used for running the Rasa engine, Action Server, and Building Vector DB.
```powershell
cd chatbot
python -m venv venv_rasa
.\venv_rasa\Scripts\activate
pip install -r requirements.txt
```

#### B. Initialize Data Scraper Environment
Used for crawling fresh data from the web.
```powershell
cd ../data
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure Environment Variables
Create a `.env` file in the `./chatbot` directory (see `.env.example` for details).

---

## 🛠 Usage Options

### Option A: Run Pre-built Version (Quick Start)
*Use this if you already have a model in `/models` but need to connect your local environment to Pinecone.*

1. **Activate Chatbot Environment:**
   ```powershell
   cd chatbot
   .\venv_rasa\Scripts\activate
   ```

2. **Populate Vector Database:**
   *Essential if your Pinecone index is empty.*
   ```powershell
   python build_vectordb.py
   ```

3. **Launch Services:**
   - **Terminal 1 (Action Server):** `rasa run actions`
   - **Terminal 2 (Rasa Core):** `python rasa_env_wrapper.py inspect --debug`

---

### Option B: Build from Scratch (Data Refresh)
*Use this to crawl fresh data, re-index Pinecone, and train a new model.*

1. **Scrape New Data:**
   ```powershell
   cd data
   .\venv\Scripts\activate
   python run_scraper.py
   python scrape_extras.py
   ```

2. **Re-build Vector Database:**
   ```powershell
   cd ../chatbot
   .\venv_rasa\Scripts\activate
   python build_vectordb.py
   ```

3. **Train fresh Model:**
   ```powershell
   python rasa_env_wrapper.py train
   ```

4. **Launch services** as described in Option A.

---

## 🧭 Data Ingestion Pipeline
The system utilizes a 4-step RAG pipeline:
1. **Scraping**: `data/` tools fetch raw data and save as Markdown.
2. **Indexing**: `build_vectordb.py` chunks and embeds data into **Pinecone** (3072 dimensions).
3. **Dialogue**: **Rasa CALM** manages the conversation flow.
4. **Synthesis**: **Gemini 3.1 Flash Lite** generates Vietnamese responses based on retrieved context.

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
