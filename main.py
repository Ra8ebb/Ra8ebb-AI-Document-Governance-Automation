import os
import time
import shutil
import logging
import fitz  # PyMuPDF
import google.generativeai as genai
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ==========================================
# 1. CONFIGURATION & GOVERNANCE (LOGGING)
# ==========================================
WATCH_DIR = "./dropzone"
PROCESSED_DIR = "./organized_docs"
LOG_FILE = "document_governance_audit.log"

# Set up audit logging to maintain document governance
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Configure AI REST API
# Ensure you have set your API key in your environment variables
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-flash')

# Ensure directories exist
Path(WATCH_DIR).mkdir(parents=True, exist_ok=True)
Path(PROCESSED_DIR).mkdir(parents=True, exist_ok=True)

# ==========================================
# 2. AI & NLP EXTRACTION LAYER
# ==========================================
def extract_text_from_pdf(file_path):
    """Extracts raw text from the PDF."""
    try:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        logging.error(f"Failed to read PDF {file_path}: {e}")
        return None

def analyze_document_with_ai(text):
    """Uses AI/NLP via REST API to classify and extract context."""
    prompt = """
    Analyze the following document text. 
    1. Classify it into ONE of these categories: Invoice, Contract, HR_Policy, Technical_Spec, or Other.
    2. Extract a brief, 3-word summary of the subject.
    
    Format your response EXACTLY like this:
    Category | Summary
    
    Text snippet:
    """ + text[:2000] # Send first 2000 chars to save tokens

    try:
        response = model.generate_content(prompt)
        result = response.text.strip().split('|')
        category = result[0].strip()
        summary = result[1].strip().replace(" ", "_")
        return category, summary
    except Exception as e:
        logging.error(f"AI API Error: {e}")
        return "Unclassified", "Unknown_Subject"

# ==========================================
# 3. PROCESS AUTOMATION WORKFLOW
# ==========================================
def process_new_file(file_path):
    """The main governance workflow for routing files."""
    filename = os.path.basename(file_path)
    logging.info(f"New file detected: {filename}. Starting processing...")

    # Step 1: Read
    text = extract_text_from_pdf(file_path)
    if not text:
        return

    # Step 2: AI Classification (REST API)
    category, context_summary = analyze_document_with_ai(text)

    # Step 3: Dynamic Renaming & Routing
    target_folder = os.path.join(PROCESSED_DIR, category)
    Path(target_folder).mkdir(exist_ok=True)

    # Create dynamic, standardized name
    timestamp = time.strftime("%Y%m%d")
    new_filename = f"{timestamp}_{category}_{context_summary}.pdf"
    new_file_path = os.path.join(target_folder, new_filename)

    # Move file
    try:
        shutil.move(file_path, new_file_path)
        logging.info(f"SUCCESS: Routed '{filename}' to '{new_file_path}'")
        print(f"✅ Processed: {new_filename}")
    except Exception as e:
        logging.error(f"Failed to route file {filename}: {e}")

# ==========================================
# 4. BACKGROUND MONITORING (WATCHDOG)
# ==========================================
class DocumentDropHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Ignore directories and non-PDFs
        if event.is_directory or not event.src_path.lower().endswith('.pdf'):
            return
        
        # Add a slight delay to ensure the file is fully downloaded/copied
        time.sleep(1) 
        process_new_file(event.src_path)

def start_automation():
    event_handler = DocumentDropHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=False)
    observer.start()
    print(f"👁️ Monitoring directory: {WATCH_DIR}")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopping automation...")
    observer.join()

if __name__ == "__main__":
    start_automation()
