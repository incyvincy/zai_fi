from neomodel import (
    StructuredNode, StringProperty, IntegerProperty, 
    BooleanProperty, FloatProperty, DateTimeProperty,
    RelationshipTo, StructuredRel
)
from datetime import datetime, timezone


# ==========================================
# RELATIONSHIP MODELS: TAG METADATA (Day 1 Schema)
# ==========================================
class TagRel(StructuredRel):
    """
    Rich relationship for linking Questions to Tags (Concept/Skill/Difficulty).
    Enables:
    1. Source tracking (client vs ai_generated)
    2. Confidence scores (0-1 for AI, 1.0 for client)
    3. Versioning for AI re-runs without deleting history
    4. Timestamp for audit trail
    """
    tag_source = StringProperty(default='ai_generated')  # 'client' or 'ai_generated'
    confidence = FloatProperty(default=1.0)  # Client tags = 1.0, AI = 0.0-1.0
    version = IntegerProperty(default=1)     # Increment on AI re-runs
    created_at = DateTimeProperty(default_now=True)


# ==========================================
# PLANE A: THE KNOWLEDGE LAYER (The "Map")
# ==========================================
class Concept(StructuredNode):
    """
    Represents a concept/topic in the syllabus hierarchy.
    Examples: Physics > Mechanics > Rotational Motion
    Can be tagged by client OR AI (tracked via TagRel).
    """
    name = StringProperty(unique_index=True)
    parent_concept = StringProperty()  # e.g., "Physics"


class Skill(StructuredNode):
    """
    Cognitive skill required to solve a question.
    Examples: Recall, Application, Analysis, Evaluation, Problem-Solving
    """
    name = StringProperty(unique_index=True)


class Difficulty(StructuredNode):
    """
    Difficulty level of a question.
    Examples: Easy, Medium, Hard
    """
    name = StringProperty(unique_index=True)


# ==========================================
# PLANE B: THE ASSESSMENT LAYER (The "Territory")
# ==========================================
class Question(StructuredNode):
    """
    Represents a single question in an exam.
    Day 1 Schema: Robust handling of missing metadata.
    
    Key Fields:
    - text: Required for AI tagging
    - needs_ai_tagging: Flag for questions missing tags
    - tagging_status: Track tagging workflow state
    """
    global_question_id = IntegerProperty(unique_index=True)
    text = StringProperty(required=True)  # Essential for AI tagging
    
    # AI Tagging Control Flags
    needs_ai_tagging = BooleanProperty(default=False)
    tagging_status = StringProperty(default='untagged')  # untagged, pending, tagged, failed
    
    # Relationships to Tag Nodes (using rich TagRel for metadata)
    topics = RelationshipTo(Concept, 'HAS_TOPIC', model=TagRel)
    skills = RelationshipTo(Skill, 'HAS_SKILL', model=TagRel)
    difficulties = RelationshipTo(Difficulty, 'HAS_DIFFICULTY', model=TagRel)


class Exam(StructuredNode):
    """
    Represents an exam/test containing multiple questions.
    Now flexible: supports any exam type (JEE, NEET, CUET, Board exams, etc.)
    """
    exam_id = IntegerProperty(unique_index=True)
    name = StringProperty()
    exam_type = StringProperty(default='general')  # 'jee', 'neet', 'cuet', 'board', 'custom', etc.
    duration = IntegerProperty()  # Duration in minutes (optional)
    
    # Exam contains Questions
    includes = RelationshipTo(Question, 'INCLUDES')


# ==========================================
# PLANE C: THE LEARNER LAYER (The "Traveler")
# ==========================================
class AttemptRel(StructuredRel):
    """
    Stores attempt outcome and optionally time spent.
    
    IMPORTANT: Time spent is OPTIONAL.
    - If missing, time-based metrics are skipped (no fake values).
    - Use time_spent_seconds = None (not 0) when missing.
    """
    outcome = StringProperty()  # 'correct', 'incorrect', 'skipped'
    time_spent_seconds = IntegerProperty()  # Optional: None if missing (NOT 0)


class Cohort(StructuredNode):
    """
    Represents a batch/cohort of students.
    Example: "ABC", "2024-Batch1"
    """
    name = StringProperty(unique_index=True)


class Student(StructuredNode):
    """
    Represents a student in the system.
    Links to Cohort (group) and Questions (attempts).
    """
    student_id = IntegerProperty(unique_index=True)
    name = StringProperty()

    # LINK C -> C: Student belongs to Cohort
    member_of = RelationshipTo(Cohort, 'MEMBER_OF')

    # LINK C -> B: Student attempted specific questions
    attempted = RelationshipTo(Question, 'ATTEMPTED', model=AttemptRel)

