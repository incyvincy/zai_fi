"""
Purpose: Bridge between Django views/API and Neo4j graph database.
This file provides clean functions for CRUD operations on the graph.

USAGE:
    from daksh_app.neo4j_service import (
        create_student_if_not_exists,
        create_attempt,
        get_student_performance,
    )

RULES:
- No business logic here (just data access)
- No AI/ML calls (those go through ai_tagging.py)
- All Neo4j operations are atomic
"""

from daksh_app.models import (
    Student, Exam, Question, Concept, Skill, Difficulty, Cohort
)


# ==========================================
# CREATE OPERATIONS (Idempotent)
# ==========================================

def create_student_if_not_exists(student_id: int, name: str = None, cohort_name: str = None) -> Student:
    """
    Create or get a student node.
    Optionally links to a cohort.
    """
    student = Student.nodes.first_or_none(student_id=student_id)
    if not student:
        student = Student(
            student_id=student_id,
            name=name or f"Student {student_id}"
        ).save()
    
    # Link to cohort if provided
    if cohort_name:
        cohort = Cohort.nodes.first_or_none(name=cohort_name)
        if not cohort:
            cohort = Cohort(name=cohort_name).save()
        if not student.member_of.is_connected(cohort):
            student.member_of.connect(cohort)
    
    return student


def create_exam_if_not_exists(exam_id: int, name: str = None, exam_type: str = 'general', duration: int = None) -> Exam:
    """
    Create or get an exam node.
    """
    exam = Exam.nodes.first_or_none(exam_id=exam_id)
    if not exam:
        exam = Exam(
            exam_id=exam_id,
            name=name or f"Exam {exam_id}",
            exam_type=exam_type,
            duration=duration
        ).save()
    return exam


def create_question_if_not_exists(
    global_question_id: int,
    text: str,
    concept_name: str = None,
    skill_name: str = None,
    difficulty_name: str = None,
    tag_source: str = 'client'
) -> dict:
    """
    Create or get a question node.
    Returns dict with question and needs_ai_tagging flag.
    
    If concept/skill/difficulty are missing, flags for AI tagging.
    """
    question = Question.nodes.first_or_none(global_question_id=global_question_id)
    needs_ai_tagging = False
    
    if not question:
        question = Question(
            global_question_id=global_question_id,
            text=text,
            needs_ai_tagging=False,
            tagging_status='untagged'
        ).save()
    
    # Check if tags are provided
    has_tags = bool(concept_name and skill_name and difficulty_name)
    
    if has_tags:
        # Create and link tags with source='client'
        _link_question_tags(
            question=question,
            concept_name=concept_name,
            skill_name=skill_name,
            difficulty_name=difficulty_name,
            tag_source=tag_source
        )
        question.tagging_status = 'tagged'
        question.needs_ai_tagging = False
    else:
        # Flag for AI tagging
        question.needs_ai_tagging = True
        question.tagging_status = 'untagged'
        needs_ai_tagging = True
    
    question.save()
    
    return {
        'question': question,
        'needs_ai_tagging': needs_ai_tagging,
        'question_text': text if needs_ai_tagging else None
    }


def _link_question_tags(
    question: Question,
    concept_name: str,
    skill_name: str,
    difficulty_name: str,
    tag_source: str = 'client',
    model_id: str = None
):
    """
    Internal helper to link question to tag nodes.
    
    Uses production-ready relationships:
    - TESTS_CONCEPT: Question → Concept
    - REQUIRES_SKILL: Question → Skill  
    - HAS_DIFFICULTY: Question → Difficulty
    
    Edge metadata includes:
    - confidence_score: 0.0-1.0 (1.0 for client, varies for AI)
    - tag_source: 'client', 'llm', 'rule', 'hybrid'
    - model_id: AI model identifier (for audit/reproducibility)
    """
    
    # Concept - uses TESTS_CONCEPT relationship
    if concept_name:
        concept = Concept.nodes.first_or_none(name=concept_name)
        if not concept:
            concept = Concept(name=concept_name, level='specific_topic').save()
        question.tests_concepts.connect(concept, {
            'tag_source': tag_source,
            'confidence_score': 1.0 if tag_source == 'client' else 0.8,
            'version': 1,
            'model_id': model_id
        })
    
    # Skill - uses REQUIRES_SKILL relationship
    if skill_name:
        skill = Skill.nodes.first_or_none(name=skill_name)
        if not skill:
            skill = Skill(name=skill_name).save()
        question.requires_skills.connect(skill, {
            'tag_source': tag_source,
            'confidence_score': 1.0 if tag_source == 'client' else 0.8,
            'version': 1,
            'model_id': model_id
        })
    
    # Difficulty - uses HAS_DIFFICULTY relationship
    if difficulty_name:
        difficulty = Difficulty.nodes.first_or_none(name=difficulty_name)
        if not difficulty:
            difficulty = Difficulty(name=difficulty_name).save()
        question.has_difficulty.connect(difficulty, {
            'tag_source': tag_source,
            'confidence_score': 1.0 if tag_source == 'client' else 0.8,
            'version': 1,
            'model_id': model_id
        })


def create_attempt(
    student_id: int,
    question_id: int,
    outcome: str,
    time_spent_seconds: int = None
) -> dict:
    """
    Create an attempt relationship between student and question.
    
    Args:
        student_id: Student's ID
        question_id: Global question ID
        outcome: 'correct', 'incorrect', or 'skipped'
        time_spent_seconds: Optional (None for offline exams)
    
    Returns:
        dict with success status
    """
    try:
        student = Student.nodes.get(student_id=student_id)
        question = Question.nodes.get(global_question_id=question_id)
    except Exception as e:
        return {'success': False, 'error': f'Node not found: {str(e)}'}
    
    # Create attempt relationship
    student.attempted.connect(question, {
        'outcome': outcome,
        'time_spent_seconds': time_spent_seconds  # None is valid (offline exam)
    })
    
    return {'success': True}


def link_question_to_exam(exam_id: int, question_id: int):
    """Link a question to an exam."""
    try:
        exam = Exam.nodes.get(exam_id=exam_id)
        question = Question.nodes.get(global_question_id=question_id)
        
        if not exam.includes.is_connected(question):
            exam.includes.connect(question)
        
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}


# ==========================================
# READ OPERATIONS (Queries)
# ==========================================

def get_student_by_id(student_id: int) -> dict:
    """Get student info from graph."""
    student = Student.nodes.first_or_none(student_id=student_id)
    if not student:
        return None
    
    return {
        'student_id': student.student_id,
        'name': student.name,
        'cohorts': [c.name for c in student.member_of.all()]
    }


def get_student_attempts(student_id: int) -> list:
    """Get all attempts by a student."""
    student = Student.nodes.first_or_none(student_id=student_id)
    if not student:
        return []
    
    attempts = []
    for question in student.attempted.all():
        rel = student.attempted.relationship(question)
        attempts.append({
            'question_id': question.global_question_id,
            'outcome': rel.outcome,
            'time_spent': rel.time_spent_seconds
        })
    
    return attempts


def get_student_performance_summary(student_id: int) -> dict:
    """
    Get performance summary for a student.
    Used by views to generate reports.
    """
    student = Student.nodes.first_or_none(student_id=student_id)
    if not student:
        return {'error': f'Student {student_id} not found'}
    
    attempts = get_student_attempts(student_id)
    
    if not attempts:
        return {
            'student_id': student_id,
            'total_attempts': 0,
            'accuracy': 0,
            'message': 'No attempts recorded'
        }
    
    correct = sum(1 for a in attempts if a['outcome'] == 'correct')
    incorrect = sum(1 for a in attempts if a['outcome'] == 'incorrect')
    skipped = sum(1 for a in attempts if a['outcome'] == 'skipped')
    
    # Time metrics (only if available)
    timed_attempts = [a for a in attempts if a['time_spent'] is not None]
    avg_time = sum(a['time_spent'] for a in timed_attempts) / len(timed_attempts) if timed_attempts else None
    
    return {
        'student_id': student_id,
        'name': student.name,
        'total_attempts': len(attempts),
        'correct': correct,
        'incorrect': incorrect,
        'skipped': skipped,
        'accuracy': round(correct / len(attempts) * 100, 2) if attempts else 0,
        'avg_time_seconds': round(avg_time, 2) if avg_time else None,
        'time_data_available': len(timed_attempts) > 0
    }


def get_questions_needing_ai_tagging() -> list:
    """Get all questions flagged for AI tagging."""
    questions = Question.nodes.filter(needs_ai_tagging=True)
    return [
        {
            'question_id': q.global_question_id,
            'question_text': q.text
        }
        for q in questions
    ]


def get_exam_questions(exam_id: int) -> list:
    """Get all questions in an exam with tag metadata."""
    exam = Exam.nodes.first_or_none(exam_id=exam_id)
    if not exam:
        return []
    
    questions = []
    for q in exam.includes.all():
        # Get tags with audit metadata
        topics = []
        for t in q.tests_concepts.all():
            rel = q.tests_concepts.relationship(t)
            topics.append({
                'name': t.name,
                'confidence_score': rel.confidence_score,
                'tag_source': rel.tag_source
            })
        
        skills = []
        for s in q.requires_skills.all():
            rel = q.requires_skills.relationship(s)
            skills.append({
                'name': s.name,
                'confidence_score': rel.confidence_score,
                'tag_source': rel.tag_source
            })
        
        difficulties = []
        for d in q.has_difficulty.all():
            rel = q.has_difficulty.relationship(d)
            difficulties.append({
                'name': d.name,
                'confidence_score': rel.confidence_score,
                'tag_source': rel.tag_source
            })
        
        questions.append({
            'question_id': q.global_question_id,
            'text': q.text[:200] + '...' if len(q.text) > 200 else q.text,
            'topics': topics,
            'skills': skills,
            'difficulties': difficulties,
            'needs_ai_tagging': q.needs_ai_tagging
        })
    
    return questions
