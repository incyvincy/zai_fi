"""
Purpose: Centralized AI service for question classification and insight generation.

BOUNDARIES:
- Classifies questions into topic, skill, difficulty (universal, works for ANY exam worldwide)
- Generates human-readable insights from structured data
- NO access to raw attempt logs or graph data (receives only processed inputs)
"""

import json
from google import genai
from google.genai import types
from django.conf import settings

MODEL_NAME = 'gemini-2.5-flash'


def classify_question(question_text: str) -> dict:
    """
    Universal question classifier - works for ANY exam type worldwide.
    
    Args:
        question_text: The full question text to classify
    
    Returns:
        dict with:
        - topic: Broader topic (e.g., "Mechanics", "Organic Chemistry", "Reading Comprehension")
        - parent_topic: Subject/Domain (e.g., "Physics", "Chemistry", "English Language")
        - skill: Cognitive skill required (Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving)
        - difficulty: Easy, Medium, or Hard
        - topic_confidence, skill_confidence, difficulty_confidence: 0.0-1.0
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""
You are a UNIVERSAL academic content classifier. Analyze this question and classify it.

Question: "{question_text}"

YOUR CAPABILITIES - Classify questions from ANY domain worldwide:
• SCIENCE: Physics, Chemistry, Biology, Mathematics (JEE, NEET, AP, A-Levels, Olympiads)
• COMMERCE: Accountancy, Economics, Business Studies, Finance (CA, CPA, CFA, MBA)
• LANGUAGE: Reading Comprehension, Vocabulary, Grammar (TOEFL, IELTS, GRE, SAT)
• APTITUDE: Logical Reasoning, Data Interpretation, Quantitative (CAT, GMAT, Bank PO, Civil Services)
• HUMANITIES: History, Geography, Political Science, Psychology, Literature
• COMPUTER SCIENCE: Programming, Algorithms, Data Structures, Databases
• LAW: Legal Reasoning, Constitution, Legal Awareness (CLAT, LSAT, Bar)
• MEDICAL: Anatomy, Physiology, Biochemistry, Pathology (USMLE, PLAB, NEET)

CRITICAL - SYLLABUS AWARENESS:
⚠️ Mentally recall the ACTUAL SYLLABUS based on question content.
⚠️ Only assign topics that fit within standard exam curricula.
⚠️ Examples:
  - JEE Chemistry: Include Organic/Inorganic/Physical Chemistry topics
  - NEET Biology: Cell Biology, Genetics, Physiology within NEET scope
  - TOEFL: ONLY language proficiency, not subject knowledge
  - CA: Accounting standards, taxation, audit - stay within CA syllabus
  - CLAT: Legal aptitude and reasoning, not deep law subjects
⚠️ If unsure, use broader parent category.

TOPIC GROUPING (CRITICAL - Use broader concepts):
✓ "Mechanics" NOT "Pulley on Inclined Plane"
✓ "Organic Chemistry" NOT "Aldol Condensation Mechanism"
✓ "Reading Comprehension" NOT "Inference in Academic Passages"
✓ "Financial Accounting" NOT "Journal Entry for Bad Debts"
✓ "Algebra" NOT "Solving Quadratic Inequalities"

Return ONLY this JSON:
{{
    "topic": "Broader topic (e.g., Mechanics, Organic Chemistry, Reading Comprehension, Logical Reasoning)",
    "parent_topic": "Subject/Domain (e.g., Physics, Chemistry, English Language, Aptitude, Accountancy)",
    "skill": "One of [Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving]",
    "difficulty": "One of [Easy, Medium, Hard]",
    "topic_confidence": 0.0-1.0,
    "skill_confidence": 0.0-1.0,
    "difficulty_confidence": 0.0-1.0
}}
"""
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"AI classification failed: {e}")
        return {
            "topic": "Uncategorized",
            "parent_topic": "General",
            "skill": "Application",
            "difficulty": "Medium",
            "topic_confidence": 0.0,
            "skill_confidence": 0.0,
            "difficulty_confidence": 0.0
        }


def generate_insight_explanation(structured_summary: dict) -> str:
    """
    Converts a structured performance summary into human-readable explanation.
    
    This is the FINAL STAGE use of Gemini - it receives already-processed
    structured data from the graph, NOT raw attempt logs.
    
    Args:
        structured_summary: Pre-computed dict with metrics like:
            - weak_topics: [{name, error_rate, attempts}]
            - strong_topics: [{name, accuracy, attempts}]
            - trend: 'improving' | 'declining' | 'stable'
            - time_efficiency: 'good' | 'needs_work' | 'unavailable'
    
    Returns:
        Human-readable explanation string
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""
You are an educational insights generator. Convert this structured performance summary
into a clear, actionable explanation for a student.

Summary Data:
{json.dumps(structured_summary, indent=2)}

Write a 2-3 paragraph explanation that:
1. Highlights key strengths and areas for improvement
2. Provides specific, actionable advice
3. Is encouraging but honest

Do NOT invent data not present in the summary. If time_efficiency is 'unavailable', 
do not mention time-based insights.
"""
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.7)
        )
        return response.text.strip()
    except Exception as e:
        print(f"Explanation generation failed: {e}")
        return "Unable to generate explanation. Please review the structured summary directly."
