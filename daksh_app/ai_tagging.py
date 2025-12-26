"""
AI Tagging Service (Day 1 - Inference Support Module)

Purpose: Generate structured tags for questions missing metadata.

BOUNDARIES (Non-negotiable):
- Input: ONLY question_id + question_text
- Output: Structured tags with confidence scores
- NO access to: attempt logs, student data, exam context
- Does NOT overwrite/delete older AI tags (keeps history via versioning)

Usage:
    from daksh_app.ai_tagging import tag_question, batch_tag_questions
    
    # Single question
    tag_question(question_id=1001)
    
    # Batch processing (for questions flagged needs_ai_tagging=True)
    batch_tag_questions()
"""

import json
import time
from collections import deque
from google import genai
from google.genai import types
from django.conf import settings
from datetime import datetime, timezone

# Configure Gemini with new SDK
MODEL_NAME = 'gemini-2.5-flash'  # Better free tier quota

# Rate limiting: 5 requests per minute
RATE_LIMIT = 5  # Max requests per minute
RATE_WINDOW = 60  # Time window in seconds
request_timestamps = deque(maxlen=RATE_LIMIT)


def check_rate_limit():
    """
    Check if we can make another API request within rate limits.
    If rate limit exceeded, sleep until we can proceed.
    """
    current_time = time.time()
    
    # Remove timestamps older than the time window
    while request_timestamps and current_time - request_timestamps[0] > RATE_WINDOW:
        request_timestamps.popleft()
    
    # If we've hit the limit, wait until the oldest request expires
    if len(request_timestamps) >= RATE_LIMIT:
        wait_time = RATE_WINDOW - (current_time - request_timestamps[0]) + 0.1  # Add 0.1s buffer
        print(f"  ⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
        time.sleep(wait_time)
    
    # Record this request
    request_timestamps.append(time.time())


def tag_question(question_id: int, force_retag: bool = False) -> dict:
    """
    Tag a single question using AI.
    
    Args:
        question_id: The global_question_id of the question
        force_retag: If True, re-tag even if already tagged (creates new version)
    
    Returns:
        dict with status and tag details, or error info
    """
    from .models import Question, Concept, Skill, Difficulty
    
    # 1. Fetch Question Node
    try:
        question = Question.nodes.get(global_question_id=question_id)
    except Question.DoesNotExist:
        return {'success': False, 'error': f'Question {question_id} not found'}
    
    # 2. Check if tagging is needed
    if not force_retag and question.tagging_status == 'tagged' and not question.needs_ai_tagging:
        return {'success': True, 'status': 'already_tagged', 'question_id': question_id}
    
    # 3. Mark as pending
    question.tagging_status = 'pending'
    question.save()
    
    # 4. Check rate limit before calling API
    check_rate_limit()
    
    # 5. Call Gemini with ONLY the question text (NEW SDK)
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    
    prompt = f"""
You are a UNIVERSAL academic content classifier. Analyze this question and classify it.

Question: "{question.text}"

YOUR CAPABILITIES - Classify questions from ANY domain worldwide:
• SCIENCE: Physics, Chemistry, Biology, Mathematics (JEE, NEET, AP, A-Levels)
• COMMERCE: Accountancy, Economics, Business Studies, Finance (CA, CPA, MBA)
• LANGUAGE: Reading Comprehension, Vocabulary, Grammar (TOEFL, IELTS, GRE, SAT)
• APTITUDE: Logical Reasoning, Data Interpretation, Quantitative (CAT, GMAT, Bank PO)
• HUMANITIES: History, Geography, Political Science, Psychology, Literature
• COMPUTER SCIENCE: Programming, Algorithms, Data Structures
• LAW: Legal Reasoning, Constitution, Legal Awareness (CLAT, LSAT)
• MEDICAL: Anatomy, Physiology, Biochemistry (USMLE, PLAB)

CRITICAL - SYLLABUS AWARENESS:
⚠️ Before classifying, mentally recall the ACTUAL SYLLABUS of the exam type based on the question content.
⚠️ Only assign topics that are ACTUALLY part of that exam's official curriculum.
⚠️ Examples:
  - JEE Chemistry: Include Organic/Inorganic/Physical, but check if Nuclear Chemistry is in scope
  - NEET Biology: Include Cell Biology, Genetics, but check depth of topics
  - TOEFL: Only language proficiency topics, not subject knowledge
  - CA: Accounting standards, taxation, audit - not general business
  - CLAT: Legal aptitude, reasoning - stay within law entrance scope
⚠️ If unsure whether a topic is in syllabus, use the broader parent category.

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
        data = json.loads(response.text)
    except Exception as e:
        question.tagging_status = 'failed'
        question.save()
        return {'success': False, 'error': f'AI analysis failed: {str(e)}', 'question_id': question_id}
    
    # 5. Determine version (find highest existing AI version, increment)
    current_max_version = 0
    for topic in question.topics.all():
        rel = question.topics.relationship(topic)
        if rel.tag_source == 'ai_generated' and rel.version > current_max_version:
            current_max_version = rel.version
    for skill in question.skills.all():
        rel = question.skills.relationship(skill)
        if rel.tag_source == 'ai_generated' and rel.version > current_max_version:
            current_max_version = rel.version
    for diff in question.difficulties.all():
        rel = question.difficulties.relationship(diff)
        if rel.tag_source == 'ai_generated' and rel.version > current_max_version:
            current_max_version = rel.version
    
    new_version = current_max_version + 1
    
    # 6. Write Tags to Graph (DO NOT delete old tags - keeps history)
    tags_created = {}
    
    # -- Topic/Concept --
    topic_name = data.get('topic', 'Uncategorized')
    parent_topic = data.get('parent_topic', 'General')
    topic_conf = data.get('topic_confidence', 0.5)
    
    concept = Concept.nodes.first_or_none(name=topic_name)
    if not concept:
        concept = Concept(name=topic_name, parent_concept=parent_topic).save()
    
    question.topics.connect(concept, {
        'tag_source': 'ai_generated',
        'confidence': float(topic_conf),
        'version': new_version
    })
    tags_created['topic'] = {'name': topic_name, 'confidence': topic_conf}
    
    # -- Skill --
    skill_name = data.get('skill', 'Application')
    skill_conf = data.get('skill_confidence', 0.5)
    
    skill = Skill.nodes.first_or_none(name=skill_name)
    if not skill:
        skill = Skill(name=skill_name).save()
    
    question.skills.connect(skill, {
        'tag_source': 'ai_generated',
        'confidence': float(skill_conf),
        'version': new_version
    })
    tags_created['skill'] = {'name': skill_name, 'confidence': skill_conf}
    
    # -- Difficulty --
    diff_name = data.get('difficulty', 'Medium')
    diff_conf = data.get('difficulty_confidence', 0.5)
    
    diff = Difficulty.nodes.first_or_none(name=diff_name)
    if not diff:
        diff = Difficulty(name=diff_name).save()
    
    question.difficulties.connect(diff, {
        'tag_source': 'ai_generated',
        'confidence': float(diff_conf),
        'version': new_version
    })
    tags_created['difficulty'] = {'name': diff_name, 'confidence': diff_conf}
    
    # 7. Update Question Status
    question.needs_ai_tagging = False
    question.tagging_status = 'tagged'
    question.save()
    
    return {
        'success': True,
        'question_id': question_id,
        'version': new_version,
        'tags': tags_created
    }


def batch_tag_questions(limit: int = 100) -> dict:
    """
    Process all questions flagged for AI tagging.
    
    Args:
        limit: Maximum number of questions to process in one batch
    
    Returns:
        Summary dict with success/failure counts
    """
    from .models import Question
    print("Starting batch AI tagging...")
    # Find questions needing tagging
    questions = Question.nodes.filter(needs_ai_tagging=True)[:limit]
    print(f"Found {len(questions)} questions needing AI tagging.")
    results = {
        'processed': 0,
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    for q in questions:
        results['processed'] += 1
        result = tag_question(q.global_question_id)
        
        if result.get('success'):
            tags = result.get('tags', {})
            topic = tags.get('topic', {}).get('name', 'N/A')
            print(f"  [✓] Q{q.global_question_id}: {topic}")
            results['success'] += 1
        else:
            error_msg = result.get('error', 'Unknown error')
            print(f"  [✗] Q{q.global_question_id}: {error_msg}")
            results['failed'] += 1
            results['errors'].append({
                'question_id': q.global_question_id,
                'error': error_msg
            })
    
    return results


def get_effective_tags(question_id: int) -> dict:
    """
    Get the "effective" tags for a question, applying priority:
    1. Client tags (source='client') take precedence
    2. Latest AI tags (highest version) used as fallback
    
    Returns:
        dict with topic, skill, difficulty (each with name, source, confidence)
    """
    from .models import Question
    
    try:
        question = Question.nodes.get(global_question_id=question_id)
    except Question.DoesNotExist:
        return {'error': f'Question {question_id} not found'}
    
    result = {
        'topic': None,
        'skill': None,
        'difficulty': None
    }
    
    # Helper function to get best tag
    def get_best_tag(rel_manager):
        client_tag = None
        best_ai_tag = None
        best_ai_version = -1
        
        for node in rel_manager.all():
            rel = rel_manager.relationship(node)
            if rel.tag_source == 'client':
                # Client tags always win
                client_tag = {
                    'name': node.name,
                    'tag_source': 'client',
                    'confidence': rel.confidence
                }
            elif rel.tag_source == 'ai_generated' and rel.version > best_ai_version:
                best_ai_version = rel.version
                best_ai_tag = {
                    'name': node.name,
                    'tag_source': 'ai_generated',
                    'confidence': rel.confidence,
                    'version': rel.version
                }
        
        return client_tag if client_tag else best_ai_tag
    
    # Get effective tags for each type
    result['topic'] = get_best_tag(question.topics)
    result['skill'] = get_best_tag(question.skills)
    result['difficulty'] = get_best_tag(question.difficulties)
    
    return result
