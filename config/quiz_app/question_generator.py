"""
AI Question Generation Service
Integrates T5 and Gemini models for question generation
"""
import re
import json
import time
import os
from PyPDF2 import PdfReader
try:
    import docx
except ImportError:
    docx = None

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import google.generativeai as genai
from django.conf import settings


class QuestionGenerator:
    """Handles AI-powered question generation"""
    
    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.gemini_model = None
        self._init_models()
    
    def _init_models(self):
        """Initialize T5 and Gemini models"""
        # Initialize T5
        try:
            print("Loading T5 model...")
            self.tokenizer = AutoTokenizer.from_pretrained(settings.HF_MODEL)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(settings.HF_MODEL)
            print("T5 model loaded successfully.")
        except Exception as e:
            print(f"Error loading T5 model: {e}")
        
        # Initialize Gemini
        try:
            if settings.GEMINI_API_KEY:
                genai.configure(api_key=settings.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel('gemma-3n-e2b-it')
                print("Gemini model initialized.")
        except Exception as e:
            print(f"Error initializing Gemini: {e}")
    
    def extract_text(self, file_path):
        """Extract text from PDF, DOCX, or TXT files"""
        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        
        try:
            if ext == '.pdf':
                reader = PdfReader(file_path)
                for page in reader.pages:
                    content = page.extract_text()
                    if content:
                        text += content + "\n"
            
            elif ext == '.docx' and docx:
                doc = docx.Document(file_path)
                for para in doc.paragraphs:
                    text += para.text + "\n"
            
            elif ext == '.txt':
                with open(file_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)
            return text
        
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""
    
    def chunk_text(self, text, chunk_size=150, min_chunk_size=60):
        """Split text into manageable chunks"""
        words = text.split()
        return [
            " ".join(words[i:i + chunk_size])
            for i in range(0, len(words), chunk_size)
            if len(words[i:i + chunk_size]) > min_chunk_size
        ]
    
    def generate_question_t5(self, context):
        """Generate question using T5 model"""
        if not self.model or not self.tokenizer:
            return None
        
        try:
            lower_chunk = context.lower()
            
            # Determine question type based on context
            if any(w in lower_chunk for w in ["because", "due to", "reason"]):
                prefix, target = "cause and effect: ", context
            elif any(w in lower_chunk for w in ["step", "process", "how"]):
                prefix, target = "procedure: ", context
            else:
                prefix, target = "explanation: ", context.split(".")[0]
            
            input_text = f"answer: {prefix}{target} context: {context} </s>"
            
            inputs = self.tokenizer.encode(
                input_text,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            outputs = self.model.generate(
                inputs,
                max_length=100,
                num_beams=4,
                do_sample=True,
                top_p=0.92,
                temperature=0.7,
                no_repeat_ngram_size=3
            )
            
            question = self.tokenizer.decode(
                outputs[0],
                skip_special_tokens=True
            ).replace("Question: ", "").strip()
            
            return question
        
        except Exception as e:
            print(f"Error in T5 generation: {e}")
            return None
    
    def enrich_question_gemini(self, question, context, max_retries=3):
        """Enrich question with answer, distractors, and Bloom level using Gemini"""
        if not self.gemini_model:
            return None
        
        prompt = f"""
Context: {context}
Question: {question}

Using ONLY the context provided, generate:
1. Correct Answer (concise, 1-3 words if possible)
2. 3 Distractors (wrong but plausible options, similar length to correct answer)
3. Bloom's Taxonomy Level (choose one: Knowledge, Remembering, Understanding, Applying, Analyzing, Evaluating, Creating)

Return strictly in JSON format:
{{
  "correct_answer": "...",
  "distractors": ["...", "...", "..."],
  "bloom_level": "..."
}}
"""
        
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(prompt)
                
                # Extract JSON from response
                match = re.search(r"\{.*\}", response.text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                    
                    # Map Bloom level to difficulty
                    bloom = data.get("bloom_level", "Understanding")
                    data["difficulty"] = self.map_bloom_to_difficulty(bloom)
                    
                    return data
            
            except Exception as e:
                print(f"Gemini error (attempt {attempt + 1}): {e}")
                time.sleep(2)
        
        return None
    
    def map_bloom_to_difficulty(self, bloom_level):
        """Map Bloom's taxonomy level to difficulty"""
        if not bloom_level:
            return "Medium"
        
        bloom_level = bloom_level.strip().lower()
        
        easy_levels = ["remembering", "knowledge"]
        medium_levels = ["understanding", "applying"]
        hard_levels = ["analyzing", "analysis", "evaluating", "creating"]
        
        if bloom_level in easy_levels:
            return "Easy"
        elif bloom_level in medium_levels:
            return "Medium"
        elif bloom_level in hard_levels:
            return "Hard"
        else:
            return "Medium"
    
    def generate_questions_from_text(self, text, num_questions=10):
        """
        Generate questions from text
        Returns list of question dictionaries
        """
        questions = []
        chunks = self.chunk_text(text)
        
        for i, chunk in enumerate(chunks[:num_questions]):
            try:
                # Generate question using T5
                question = self.generate_question_t5(chunk)
                if not question:
                    continue
                
                # Enrich with Gemini
                enriched = self.enrich_question_gemini(question, chunk)
                if not enriched:
                    continue
                
                # Create question data
                question_data = {
                    'question': question,
                    'context': chunk,
                    'correct_answer': enriched.get('correct_answer', ''),
                    'distractors': enriched.get('distractors', ['', '', '']),
                    'bloom_level': enriched.get('bloom_level', 'Understanding'),
                    'difficulty': enriched.get('difficulty', 'Medium')
                }
                
                questions.append(question_data)
                print(f"Generated question {len(questions)}/{num_questions}")
            
            except Exception as e:
                print(f"Error generating question {i}: {e}")
                continue
        
        return questions


# Global instance
question_generator = QuestionGenerator()