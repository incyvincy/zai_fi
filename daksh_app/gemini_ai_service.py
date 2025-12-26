"""
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
        exam_context: Optional context (e.g., "JEE Main", "NEET", "TOEFL", "SAT")
                      Used only for better classification, NOT hardcoded logic
    
    Returns:
        dict with concept, sub_concept, skill_required
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""
You are a UNIVERSAL academic content classifier. You can classify questions from ANY domain:
- Science exams (JEE, NEET, AP Physics, A-Levels)
- Commerce/Business exams (CA, CPA, MBA entrance)
- Arts/Humanities (Literature, History, Psychology)
- Language proficiency (TOEFL, IELTS, GRE Verbal)
- Aptitude tests (SAT, CAT, GMAT, Civil Services)
- Competitive exams worldwide

Context: {exam_context}
Question: "{question_text}"

CRITICAL - SYLLABUS AWARENESS:
⚠️ Mentally recall the ACTUAL SYLLABUS of "{exam_context}" before classifying.
⚠️ Only assign topics that are part of that exam's official curriculum.
⚠️ If the question seems outside standard scope, use broader categories or mark as "Uncategorized".

DOMAIN DETECTION RULES:
- If about forces, energy, circuits → Science (Physics)
- If about reactions, compounds, bonds → Science (Chemistry)  
- If about cells, organisms, genetics → Science (Biology)
- If about accounting, finance, business → Commerce
- If about literature, art, philosophy → Humanities
- If about comprehension, grammar, vocabulary → Language
- If about logic, reasoning, data interpretation → Aptitude
- If about history, geography, civics → Social Sciences
- If about coding, algorithms → Computer Science

TOPIC GROUPING (use broader concepts, NOT ultra-specific):
- Use "Mechanics" not "Pulley Systems on Inclined Planes"
- Use "Grammar & Syntax" not "Subject-Verb Agreement in Complex Sentences"
- Use "Financial Accounting" not "Journal Entry for Depreciation"

Return a JSON object:
{{
    "concept": "Broad domain (e.g., Physics, Accountancy, English Language, Logical Reasoning)",
    "sub_concept": "Broader topic within domain (e.g., Mechanics, Cost Accounting, Reading Comprehension, Syllogisms)",
    "skill_required": "One of [Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving]",
    "difficulty": "One of [Easy, Medium, Hard]",
    "confidence": 0.0-1.0
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
    Universal prompt handles ANY exam type worldwide.
    
    Args:
        questions_list: List of dicts with 'question_id' and 'question_text'
        exam_context: Context string (exam name/type) for better classification
    
    Returns:
        Dict mapping question_id -> {concept, sub_concept, skill, difficulty, confidence}
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    # Build compact representation (truncate long questions)
    questions_block = "\n".join([
        f"Q{q['question_id']}: {q['question_text'][:300]}" 
        for q in questions_list[:50]  # Process max 50 at once for reliability
    ])
    
    prompt = f"""
You are a UNIVERSAL academic content classifier. Analyze questions from the exam: "{exam_context}"

YOUR CAPABILITIES - You can classify ANY type of question:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCIENCE EXAMS (JEE, NEET, AP, A-Levels, Olympiads):
  → Physics, Chemistry, Biology, Mathematics

COMMERCE/BUSINESS (CA, CPA, CFA, MBA, ACCA):
  → Accountancy, Economics, Business Studies, Finance

LANGUAGE PROFICIENCY (TOEFL, IELTS, GRE, GMAT Verbal):
  → Reading Comprehension, Vocabulary, Grammar, Writing

APTITUDE/REASONING (SAT, CAT, GRE Quant, Civil Services, Bank PO):
  → Quantitative Aptitude, Logical Reasoning, Data Interpretation, Verbal Ability

HUMANITIES/ARTS (UPSC, SAT Subject, AP):
  → History, Geography, Political Science, Psychology, Philosophy, Literature

COMPUTER SCIENCE (Coding tests, Tech interviews):
  → Programming, Data Structures, Algorithms, Databases

LAW EXAMS (CLAT, LSAT, Bar):
  → Legal Reasoning, Legal Awareness, Constitution

MEDICAL ENTRANCE (NEET, USMLE, PLAB):
  → Anatomy, Physiology, Biochemistry, Pathology, Pharmacology
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL - SYLLABUS AWARENESS:
⚠️ Before classifying, mentally recall the ACTUAL OFFICIAL SYLLABUS of "{exam_context}".
⚠️ Only assign topics that are ACTUALLY part of that exam's curriculum.
⚠️ Examples:
  - JEE Chemistry: Check if Nuclear Chemistry, Quantum Chemistry are in scope
  - NEET Biology: Verify depth (e.g., molecular details vs conceptual)
  - TOEFL: ONLY language skills, NO subject knowledge
  - CA Foundation: Accounting, Law, Economics - stay within CA Institute syllabus
  - CLAT: Legal aptitude + reasoning, not deep law subjects
⚠️ If a topic seems outside scope, use the broader parent category instead.

EXAMPLES OF CORRECT CLASSIFICATION:
┌─────────────────────────────────────────────────────────────────────────────┐
│ "A block slides down a frictionless incline..."                             │
│ → {{"concept": "Physics", "sub_concept": "Mechanics", "skill": "Application"}} │
├─────────────────────────────────────────────────────────────────────────────┤
│ "Which accounting standard governs revenue recognition?"                     │
│ → {{"concept": "Accountancy", "sub_concept": "Accounting Standards", "skill": "Recall"}} │
├─────────────────────────────────────────────────────────────────────────────┤
│ "Point A is 10km North of B. C is 5km East of A..."                        │
│ → {{"concept": "Logical Reasoning", "sub_concept": "Direction Sense", "skill": "Analysis"}} │
├─────────────────────────────────────────────────────────────────────────────┤
│ "The passage suggests that the author's attitude..."                        │
│ → {{"concept": "English Language", "sub_concept": "Reading Comprehension", "skill": "Analysis"}} │
├─────────────────────────────────────────────────────────────────────────────┤
│ "What is the time complexity of merge sort?"                                │
│ → {{"concept": "Computer Science", "sub_concept": "Algorithms", "skill": "Recall"}} │
├─────────────────────────────────────────────────────────────────────────────┤
│ "The Treaty of Westphalia (1648) established..."                            │
│ → {{"concept": "History", "sub_concept": "World History", "skill": "Recall"}} │
└─────────────────────────────────────────────────────────────────────────────┘

TOPIC GROUPING RULES (IMPORTANT!):
- Use BROADER topic names, NOT ultra-specific sub-sub-topics
- ✓ "Mechanics" (NOT "Pulley on Inclined Plane with Friction")
- ✓ "Organic Chemistry" (NOT "SN2 Reaction Mechanism of Primary Alkyl Halides")  
- ✓ "Financial Accounting" (NOT "Journal Entry for Prepaid Expenses")
- ✓ "Reading Comprehension" (NOT "Inference Questions in Academic Passages")

QUESTIONS TO ANALYZE:
{questions_block}

RESPONSE FORMAT - Return ONLY this JSON structure:
{{
  "question_id": {{"concept": "...", "sub_concept": "...", "skill": "Recall|Understanding|Application|Analysis|Evaluation|Problem-Solving", "difficulty": "Easy|Medium|Hard", "confidence": 0.0-1.0}},
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
