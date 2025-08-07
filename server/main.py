from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import uuid
from typing import Dict, Any, List
from ebooklib import epub
from bs4 import BeautifulSoup
import re
import json

# Lightweight NLP utilities
import nltk
from collections import Counter
from textstat import textstat
from sklearn.feature_extraction.text import TfidfVectorizer

# Ensure data directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BOOKS_DIR = os.path.join(DATA_DIR, "books")
ANALYSES_DIR = os.path.join(DATA_DIR, "analyses")
os.makedirs(BOOKS_DIR, exist_ok=True)
(os.makedirs(ANALYSES_DIR, exist_ok=True))

# Try to ensure NLTK data is available (safe best-effort)
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
try:
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('averaged_perceptron_tagger', quiet=True)
try:
    nltk.data.find('chunkers/maxent_ne_chunker')
    nltk.data.find('corpora/words')
except LookupError:
    nltk.download('maxent_ne_chunker', quiet=True)
    nltk.download('words', quiet=True)

app = FastAPI(title="Epub AI Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UploadResponse(BaseModel):
    book_id: str
    filename: str


class AnalysisResponse(BaseModel):
    book_id: str
    characters: List[str]
    top_keywords: List[str]
    complexity: Dict[str, Any]


def extract_text_from_epub(epub_path: str) -> str:
    book = epub.read_epub(epub_path)
    texts: List[str] = []
    for item in book.get_items():
        if item.get_type() == epub.ITEM_DOCUMENT:
            try:
                soup = BeautifulSoup(item.get_content(), "html.parser")
                # Remove scripts/styles
                for tag in soup(["script", "style"]):
                    tag.decompose()
                text = soup.get_text(separator=" ")
                texts.append(text)
            except Exception:
                continue
    raw_text = "\n".join(texts)
    # Normalize spaces
    raw_text = re.sub(r"\s+", " ", raw_text)
    return raw_text


def extract_characters_simple(text: str, max_names: int = 25) -> List[str]:
    # Simple heuristic: Proper Noun sequences as names
    try:
        sentences = nltk.sent_tokenize(text)
        name_candidates: List[str] = []
        for sentence in sentences[:2000]:  # limit for speed
            tokens = nltk.word_tokenize(sentence)
            tagged = nltk.pos_tag(tokens)
            current_name: List[str] = []
            for word, tag in tagged:
                if tag in ("NNP", "NNPS") and re.match(r"^[A-Z][a-zA-Z\-']+$", word):
                    current_name.append(word)
                else:
                    if len(current_name) >= 1:
                        name = " ".join(current_name)
                        if len(name) > 2:
                            name_candidates.append(name)
                        current_name = []
            if len(current_name) >= 1:
                name = " ".join(current_name)
                if len(name) > 2:
                    name_candidates.append(name)
        counts = Counter([n.strip() for n in name_candidates if n.strip()])
        common = [name for name, _ in counts.most_common(max_names)]
        # Deduplicate similar names by lower-case
        seen = set()
        result: List[str] = []
        for nm in common:
            key = nm.lower()
            if key not in seen:
                seen.add(key)
                result.append(nm)
        return result
    except Exception:
        return []


def extract_keywords(text: str, top_k: int = 20) -> List[str]:
    try:
        # Split into paragraphs for tf-idf
        chunks = re.split(r"[\n\.]{2,}", text)
        chunks = [c.strip() for c in chunks if len(c.strip()) > 0]
        if len(chunks) < 3:
            chunks = re.split(r"[\.!?]", text)
            chunks = [c.strip() for c in chunks if len(c.strip()) > 0]
        if len(chunks) == 0:
            return []
        vectorizer = TfidfVectorizer(stop_words="english", max_features=5000, ngram_range=(1, 2))
        X = vectorizer.fit_transform(chunks)
        # Rank by max tf-idf across documents
        max_scores = X.max(axis=0).toarray().ravel()
        indices = max_scores.argsort()[::-1][: top_k * 3]
        features = vectorizer.get_feature_names_out()
        candidates = [features[i] for i in indices]
        # Filter out too short/long and digits
        filtered: List[str] = []
        for c in candidates:
            if any(ch.isdigit() for ch in c):
                continue
            if 3 <= len(c) <= 30:
                filtered.append(c)
        # Deduplicate while preserving order
        seen = set()
        top: List[str] = []
        for k in filtered:
            if k not in seen:
                seen.add(k)
                top.append(k)
            if len(top) >= top_k:
                break
        return top
    except Exception:
        return []


def compute_complexity(text: str) -> Dict[str, Any]:
    try:
        return {
            "flesch_reading_ease": textstat.flesch_reading_ease(text),
            "flesch_kincaid_grade": textstat.flesch_kincaid_grade(text),
            "dale_chall_readability_score": textstat.dale_chall_readability_score(text),
            "smog_index": textstat.smog_index(text),
            "automated_readability_index": textstat.automated_readability_index(text),
            "avg_sentence_length": textstat.avg_sentence_length(text),
            "lexicon_count": textstat.lexicon_count(text, removepunct=True),
        }
    except Exception:
        return {}


@app.post("/upload", response_model=UploadResponse)
async def upload_epub(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(status_code=400, detail="Only .epub files are supported")
    book_id = str(uuid.uuid4())
    save_path = os.path.join(BOOKS_DIR, f"{book_id}.epub")
    with open(save_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return UploadResponse(book_id=book_id, filename=file.filename)


@app.post("/scan/{book_id}")
async def scan_book(book_id: str):
    epub_path = os.path.join(BOOKS_DIR, f"{book_id}.epub")
    if not os.path.exists(epub_path):
        raise HTTPException(status_code=404, detail="Book not found")
    text = extract_text_from_epub(epub_path)
    characters = extract_characters_simple(text)
    keywords = extract_keywords(text)
    complexity = compute_complexity(text)
    result = {
        "book_id": book_id,
        "characters": characters,
        "top_keywords": keywords,
        "complexity": complexity,
    }
    with open(os.path.join(ANALYSES_DIR, f"{book_id}.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return JSONResponse(result)


@app.get("/analysis/{book_id}", response_model=AnalysisResponse)
async def get_analysis(book_id: str):
    path = os.path.join(ANALYSES_DIR, f"{book_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Analysis not found. Run /scan first.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse(data)


@app.get("/health")
async def health():
    return {"status": "ok"}