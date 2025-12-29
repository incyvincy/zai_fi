"""
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

import time
from collections import deque
from .models import Question, Concept, Skill, Difficulty
from .gemini_ai_service import classify_question

# Rate limiting configuration

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
    
    # 5. Call centralized AI classification service
    try:
        data = classify_question(question.text)
        
        # Validate: Reject fallback values (means API failed silently)
        if data.get('domain') == 'General' and data.get('parent_topic') == 'Uncategorized':
            raise ValueError("API returned fallback values - likely quota exhausted or API error")
        
        # Validate: Check confidence scores exist
        if data.get('topic_confidence', 0.0) < 0.1:
            raise ValueError("Low or zero confidence - classification failed")
            
    except Exception as e:
        question.tagging_status = 'failed'
        question.save()
        return {'success': False, 'error': f'AI analysis failed: {str(e)}', 'question_id': question_id}
    
    # 6. Determine version (find highest existing AI version, increment)
    current_max_version = 0
    for topic in question.tests_concepts.all():
        rel = question.tests_concepts.relationship(topic)
        if rel.tag_source == 'llm' and rel.version > current_max_version:
            current_max_version = rel.version
    for skill in question.requires_skills.all():
        rel = question.requires_skills.relationship(skill)
        if rel.tag_source == 'llm' and rel.version > current_max_version:
            current_max_version = rel.version
    for diff in question.has_difficulty.all():
        rel = question.has_difficulty.relationship(diff)
        if rel.tag_source == 'llm' and rel.version > current_max_version:
            current_max_version = rel.version
    
    new_version = current_max_version + 1
    
    # Model identifier for audit trail
    model_id = 'gemini-2.5-flash'
    
    # 7. Write Tags to Graph (DO NOT delete old tags - keeps history)
    tags_created = {}
    
    # -- Topic/Concept (3-level hierarchy via HAS_TOPIC) --
    domain_name = data.get('domain', 'General')
    parent_topic_name = data.get('parent_topic', 'Uncategorized')
    specific_topic_name = data.get('specific_topic', 'General')
    topic_conf = data.get('topic_confidence', 0.5)
    
    # Create or get Domain node (level 1)
    domain_node = Concept.nodes.get_or_none(name=domain_name, level='domain')
    if not domain_node:
        domain_node = Concept(name=domain_name, level='domain').save()
    
    # Create or get Parent Topic node (level 2)
    parent_node = Concept.nodes.get_or_none(name=parent_topic_name, level='parent_topic')
    if not parent_node:
        parent_node = Concept(name=parent_topic_name, level='parent_topic').save()
    
    # HAS_TOPIC: Domain -[HAS_TOPIC]-> Parent Topic (Concept hierarchy ONLY)
    if not domain_node.sub_topics.is_connected(parent_node):
        domain_node.sub_topics.connect(parent_node)
    
    # Create or get Specific Topic node (level 3 - leaf node)
    specific_node = Concept.nodes.get_or_none(name=specific_topic_name, level='specific_topic')
    if not specific_node:
        specific_node = Concept(name=specific_topic_name, level='specific_topic').save()
    
    # HAS_TOPIC: Parent Topic -[HAS_TOPIC]-> Specific Topic (Concept hierarchy ONLY)
    if not parent_node.sub_topics.is_connected(specific_node):
        parent_node.sub_topics.connect(specific_node)
    
    # TESTS_CONCEPT: Question assesses the MOST SPECIFIC (leaf) concept
    # Edge stores: confidence_score, tag_source='llm', version, model_id (for audit)
    question.tests_concepts.connect(specific_node, {
        'tag_source': 'llm',
        'confidence_score': float(topic_conf),
        'version': new_version,
        'model_id': model_id
    })
    
    tags_created['topic'] = {
        'domain': domain_name,
        'parent_topic': parent_topic_name,
        'specific_topic': specific_topic_name,
        'confidence_score': topic_conf,
        'tag_source': 'llm'
    }
    
    # -- Skill (REQUIRES_SKILL with audit metadata) --
    skill_name = data.get('skill', 'Application')
    skill_conf = data.get('skill_confidence', 0.5)
    
    skill = Skill.nodes.first_or_none(name=skill_name)
    if not skill:
        skill = Skill(name=skill_name).save()
    
    question.requires_skills.connect(skill, {
        'tag_source': 'llm',
        'confidence_score': float(skill_conf),
        'version': new_version,
        'model_id': model_id
    })
    tags_created['skill'] = {
        'name': skill_name,
        'confidence_score': skill_conf,
        'tag_source': 'llm'
    }
    
    # -- Difficulty (HAS_DIFFICULTY with audit metadata) --
    diff_name = data.get('difficulty', 'Medium')
    diff_conf = data.get('difficulty_confidence', 0.5)
    
    diff = Difficulty.nodes.first_or_none(name=diff_name)
    if not diff:
        diff = Difficulty(name=diff_name).save()
    
    question.has_difficulty.connect(diff, {
        'tag_source': 'llm',
        'confidence_score': float(diff_conf),
        'version': new_version,
        'model_id': model_id
    })
    tags_created['difficulty'] = {
        'name': diff_name,
        'confidence_score': diff_conf,
        'tag_source': 'llm'
    }
    
    # 8. Update Question Status
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
            topic_data = tags.get('topic', {})
            topic = topic_data.get('specific_topic', 'N/A')
            parent = topic_data.get('parent_topic', '')
            print(f"  [✓] Q{q.global_question_id}: {parent} → {topic}")
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
    2. Latest AI tags (highest version, source='llm') used as fallback
    
    Returns:
        dict with topic, skill, difficulty (each with name, tag_source, confidence_score)
    """
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
                    'confidence_score': rel.confidence_score
                }
            elif rel.tag_source == 'llm' and rel.version > best_ai_version:
                best_ai_version = rel.version
                best_ai_tag = {
                    'name': node.name,
                    'tag_source': 'llm',
                    'confidence_score': rel.confidence_score,
                    'version': rel.version,
                    'model_id': rel.model_id
                }
        
        return client_tag if client_tag else best_ai_tag
    
    # Get effective tags for each type (using new relationship names)
    result['topic'] = get_best_tag(question.tests_concepts)
    result['skill'] = get_best_tag(question.requires_skills)
    result['difficulty'] = get_best_tag(question.has_difficulty)
    
    return result
