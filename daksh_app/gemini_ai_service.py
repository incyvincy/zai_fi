"""
Gemini AI Service (Day 1 - Updated)

Purpose: AI-powered analysis for structured summaries and explanations.

BOUNDARIES (Gemini is allowed ONLY for):
1. Early stage: Tagging questions when metadata is missing
2. Final stage: Converting structured summaries into explanations

Gemini must NEVER:
- Read raw attempt logs
- Make predictions
- Fix graph errors

If Gemini needs raw data, the graph is wrong.
"""

import json
from google import genai
from google.genai import types
from django.conf import settings

# Configure Gemini with new SDK
MODEL_NAME = 'gemini-2.5-flash'  # Better free tier quota


def get_concept_analysis(question_text: str, exam_context: str = "Academic Exam") -> dict:
    """
    Analyzes a question and returns classification.
    
    Args:
        question_text: The full question text
        exam_context: Optional context (e.g., "JEE Main", "NEET", "CBSE Board")
                      Used only for better classification, NOT hardcoded logic
    
    Returns:
        dict with concept, sub_concept, skill_required
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""
    You are an expert academic content classifier.
    Analyze the following question and classify it into a hierarchical syllabus.
    
    Context: {exam_context}
    Question: "{question_text}"
    
    Return a JSON object with these keys:
    - "concept": The high-level unit (e.g., Mechanics, Calculus, Organic Chemistry, Biology)
    - "sub_concept": The specific topic (e.g., Rotational Motion, Integration, Alcohols, Cell Division)
    - "skill_required": One of [Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving]
    - "difficulty": One of [Easy, Medium, Hard]
    - "confidence": Float between 0.0 and 1.0
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
        print(f"AI Tagging failed: {e}")
        return {
            "concept": "Uncategorized",
            "sub_concept": "General",
            "skill_required": "Application",
            "difficulty": "Medium",
            "confidence": 0.0
        }


def batch_analyze_questions(questions_list: list, exam_context: str = "Academic Exam") -> dict:
    """
    BATCH PROCESSING: Analyze multiple questions in ONE API call.
    
    Args:
        questions_list: List of dicts with 'question_id' and 'question_text'
        exam_context: Context string (exam name/type) for better classification
    
    Returns:
        Dict mapping question_id -> {concept, sub_concept, skill, difficulty, confidence}
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    # Build compact representation (truncate long questions)
    questions_block = "\n".join([
        f"Q{q['question_id']}: {q['question_text'][:250]}..."
        for q in questions_list[:100]  # Process max 50 at once for reliability
    ])
    
    prompt = f"""
You are an expert academic content classifier for "{exam_context}".
Analyze ALL questions below and classify each into a hierarchical syllabus.

{questions_block}

Return a JSON object mapping question_id to tags:
{{
  "1": {{"concept": "Mechanics", "sub_concept": "Rotational Motion", "skill": "Application", "difficulty": "Medium", "confidence": 0.85}},
  "2": {{"concept": "Thermodynamics", "sub_concept": "Heat Transfer", "skill": "Understanding", "difficulty": "Easy", "confidence": 0.9}},
  ...
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
        print(f"Batch AI Tagging failed: {e}")
        # Fallback: return minimal data (marked as low confidence)
        return {
            str(q['question_id']): {
                "concept": "Uncategorized",
                "sub_concept": "General",
                "skill": "Application",
                "difficulty": "Medium",
                "confidence": 0.0
            }
            for q in questions_list
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


# Legacy compatibility alias (deprecated, use batch_analyze_questions)
def batch_analyze_exam(questions_list, subject_context="Academic Exam"):
    """Deprecated: Use batch_analyze_questions instead."""
    return batch_analyze_questions(questions_list, exam_context=subject_context)
