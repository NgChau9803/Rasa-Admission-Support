import os
import glob
import time
import random
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

# Load API keys from .env
load_dotenv()

# Extract all GOOGLE_API_KEYs from environment for rotation
google_keys = [v.strip() for k, v in os.environ.items() if k.startswith("GOOGLE_API_KEY") and v.strip()]

if not google_keys and not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY or GOOGLE_API_KEY_1 is missing from .env")

# Ensure the primary key is available in the standard environment variable
if google_keys and not os.environ.get("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = google_keys[0]

if not os.getenv("PINECONE_API_KEY"):
    raise ValueError("PINECONE_API_KEY is missing from .env")

# --- Config ---
# Free tier: 100 embed requests per minute.
# We process chunks in small batches and sleep between them to stay under the limit.
BATCH_SIZE = 10          # Texts to embed per API call (1 call = 1 request)
BATCH_DELAY_SECS = 7     # Sleep time between batches (10 batches * 7s = 70s/min → safe under 100 RPM)
MAX_RETRIES = 5          # Number of retries on rate-limit errors
BASE_BACKOFF = 10        # Base wait in seconds for exponential backoff on 429

# --- 1. Load Data ---
data_dir = os.path.join("..", "data", "output")
print(f"Scanning for Markdown files in {data_dir}...")
md_files = glob.glob(os.path.join(data_dir, "**", "*.md"), recursive=True)

documents = []
for file_path in md_files:
    try:
        loader = TextLoader(file_path, encoding="utf-8")
        documents.extend(loader.load())
    except Exception as e:
        print(f"  [WARN] Could not load {file_path}: {e}")

print(f"Loaded {len(documents)} markdown files.")

# --- 2. Split Text into Chunks ---
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200,
    length_function=len
)
chunks = text_splitter.split_documents(documents)
print(f"Split into {len(chunks)} chunks.")

# --- 3. Initialize Embeddings ---
# gemini-embedding-001 is on the stable v1 API endpoint (dimension: 3072)
print("Initializing Gemini Embeddings (gemini-embedding-001 via v1)...")
embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
)

# --- 4. Initialize Pinecone ---
index_name = "soict-admission-rag"
pc = Pinecone()

existing_indexes = [idx["name"] for idx in pc.list_indexes()]
if index_name not in existing_indexes:
    print(f"Creating Pinecone index '{index_name}'...")
    pc.create_index(
        name=index_name,
        dimension=3072,
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region="us-east-1")
    )
    print("Waiting for index to become ready...")
    while not pc.describe_index(index_name).status['ready']:
        time.sleep(1)

index = pc.Index(index_name)
vector_store = PineconeVectorStore(index=index, embedding=embeddings)

# --- 5. Batch Upload with Rate-Limit Retry ---
total = len(chunks)
print(f"\nUploading {total} chunks to Pinecone in batches of {BATCH_SIZE}...")
print(f"Estimated time: ~{(total // BATCH_SIZE * BATCH_DELAY_SECS) // 60} min {(total // BATCH_SIZE * BATCH_DELAY_SECS) % 60} sec\n")

uploaded = 0
for i in range(0, total, BATCH_SIZE):
    batch = chunks[i: i + BATCH_SIZE]
    batch_num = i // BATCH_SIZE + 1
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            vector_store.add_documents(batch)
            uploaded += len(batch)
            print(f"  [Batch {batch_num}/{total_batches}] ✓ Uploaded {uploaded}/{total} chunks")
            break  # Success — move to next batch
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                # Exponential backoff: 10s, 20s, 40s, 80s, 160s
                wait = BASE_BACKOFF * (2 ** (attempt - 1)) + random.uniform(0, 2)
                print(f"  [Batch {batch_num}] Rate limit hit (attempt {attempt}/{MAX_RETRIES}). Retrying in {wait:.1f}s...")
                time.sleep(wait)
            else:
                print(f"  [Batch {batch_num}] ERROR: {e}")
                raise  # Re-raise unknown errors immediately
    else:
        print(f"  [Batch {batch_num}] FAILED after {MAX_RETRIES} retries. Skipping.")

    # Polite delay between successful batches to stay under free tier RPM
    if i + BATCH_SIZE < total:
        time.sleep(BATCH_DELAY_SECS)

print(f"\n{'='*50}")
print(f"✅ Done! Successfully uploaded {uploaded}/{total} chunks to Pinecone index '{index_name}'.")
