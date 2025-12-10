import os
import re
from typing import Dict, List, Optional
from loguru import logger
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

try:
    # Requires 'openai' package and OPENAI_API_KEY env var
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not available. Knowledge extraction will be basic/disabled.")

class KnowledgeLearner:
    def __init__(self, db=None):
        self.db = db
        self.openai_client = None
        self.learned_concepts: List[Dict] = []
        
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            try:
                self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                logger.info("OpenAI client initialized for knowledge learning")
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
                self.openai_client = None
    
    def learn_from_pdf(self, pdf_path: str) -> Dict:
        """Extracts text from PDF and stores concepts."""
        try:
            reader = PdfReader(pdf_path)
            text = ""
            
            for page in reader.pages:
                text += page.extract_text() + "\n"
            
            concepts = self._extract_trading_concepts(text)
            
            if self.db:
                for concept in concepts:
                    self.db.save_knowledge(
                        source=pdf_path,
                        category=concept["category"],
                        content=concept["content"],
                        summary=concept.get("summary"),
                        relevance_score=concept.get("relevance", 0.5)
                    )
            
            self.learned_concepts.extend(concepts)
            
            logger.info(f"Learned {len(concepts)} concepts from {pdf_path}")
            return {"status": "success", "concepts_learned": len(concepts)}
        except Exception as e:
            logger.error(f"Error learning from PDF: {e}")
            return {"status": "error", "message": str(e)}

    def _extract_trading_concepts(self, text: str) -> List[Dict]:
        """Simple keyword-based extraction (can be enhanced with AI)."""
        concepts = []
        
        keywords = {
            "Martingale": "Risk Management", "Fibonacci": "Technical Levels",
            "Bollinger Bands": "Indicators", "Japanese Candlesticks": "Patterns",
            "Economic News": "Fundamental Analysis"
        }
        
        for keyword, category in keywords.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text, re.IGNORECASE):
                # Simple extraction, needs advanced logic for real summary
                concept_content = f"Discussion of {keyword}..." 
                concepts.append({
                    "keyword": keyword,
                    "category": category,
                    "content": concept_content,
                    "summary": f"The document mentions {keyword} in the context of {category}.",
                    "relevance": 0.8
                })
        
        return concepts

    def get_relevant_knowledge(self, context: str) -> List[Dict]:
        """Fetches the top 5 relevant learned concepts for the given context."""
        if not self.learned_concepts:
            return []
        
        context_lower = context.lower()
        relevant = []
        
        # Simple relevance check based on context keywords (e.g., current asset/indicator)
        for concept in self.learned_concepts:
            keyword = concept.get("keyword", "")
            if keyword and keyword.lower() in context_lower:
                relevant.append(concept)
        
        return relevant[:5]
    
    def get_stats(self) -> Dict:
        categories = {}
        for concept in self.learned_concepts:
            cat = concept.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "total_concepts": len(self.learned_concepts),
            "categories": categories,
            "ai_available": self.openai_client is not None
        }
