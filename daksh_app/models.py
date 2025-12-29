from neomodel import (
    StructuredNode, StringProperty, IntegerProperty, 
    BooleanProperty, FloatProperty, DateTimeProperty,
    RelationshipTo, StructuredRel
)
from datetime import datetime, timezone


# ==========================================
# RELATIONSHIP MODELS: TAG METADATA (Day 1 Schema - PRODUCTION READY)
# ==========================================
class AITagMetadataRel(StructuredRel):
    """
    Rich relationship for linking Questions to Tags (Concept/Skill/Difficulty).
    
    PRODUCTION AUDIT REQUIREMENTS:
    1. confidence_score: 0.0-1.0 (AI confidence, 1.0 for client-provided)
    2. tag_source: 'client' | 'llm' | 'rule' | 'hybrid' (for audit/trust control)
    3. version: Increment on AI re-runs (history preservation)
    4. created_at: Timestamp for audit trail
    5. model_id: Which AI model generated this tag (for reproducibility)
    
    AUDIT USE CASES:
    - Filter by tag_source to review AI vs client tags
    - Re-run tagging for low-confidence edges (< 0.7)
    - Track which model version produced the tag
    """
    # REQUIRED: Confidence score for trust control and re-generation
    confidence_score = FloatProperty(default=1.0)  # Client tags = 1.0, AI = 0.0-1.0
    
    # REQUIRED: Source tracking for audit (client/llm/rule/hybrid)
    tag_source = StringProperty(default='client')  # 'client', 'llm', 'rule', 'hybrid'
    
    # Versioning for AI re-runs without deleting history
    version = IntegerProperty(default=1)
    
    # Audit trail timestamp
    created_at = DateTimeProperty(default_now=True)
    
    # AI model identifier for reproducibility (e.g., 'gemini-2.5-flash-v1')
    model_id = StringProperty(default=None)


# Keep TagRel as alias for backward compatibility during migration
TagRel = AITagMetadataRel


class MasteryRel(StructuredRel):
    """
    Stores the ML-predicted state of a student for a specific Concept/Skill.
    Gemini/ML reads THIS, not the raw attempts.
    """
    mastery_score = FloatProperty(default=0.0)  # 0.0 to 1.0
    risk_level = StringProperty()               # 'High', 'Medium', 'Low'
    last_updated_at = DateTimeProperty(default_now=True)


# ==========================================
# PLANE A: THE KNOWLEDGE LAYER (The "Map")
# ==========================================
class Concept(StructuredNode):
    """
    Represents a concept/topic in the syllabus hierarchy (3-level structure).
    
    Hierarchy: Domain → Parent Topic → Specific Sub-Topic
    Examples: 
      - Physics → Thermodynamics → Carnot Engine
      - Chemistry → Organic Chemistry → Aldol Condensation
      - English Language → Reading Comprehension → Inference Questions
    
    GRAPH HIERARCHY via HAS_TOPIC:
    - HAS_TOPIC links ONLY Concept → Sub-Concept (parent to child)
    - Domain -[HAS_TOPIC]-> Parent Topic -[HAS_TOPIC]-> Specific Topic
    
    IMPORTANT: Question text is NEVER stored here or in HAS_TOPIC.
    Questions are separate nodes linked via TESTS_CONCEPT relationship.
    """
    name = StringProperty(unique_index=True)  # Can be Domain, Parent Topic, or Specific Topic
    level = StringProperty()  # 'domain', 'parent_topic', or 'specific_topic'
    
    # Hierarchical relationship: Parent Concept -[HAS_TOPIC]-> Child Sub-Concept
    # This is the ONLY use of HAS_TOPIC (Concept hierarchy only)
    sub_topics = RelationshipTo('Concept', 'HAS_TOPIC')


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
    Question is a FIRST-CLASS NODE (not embedded in relationship properties).
    This enables: queries, reuse, analytics, and scaling.
    
    Day 1 Schema: Robust handling of missing metadata.
    
    Key Fields:
    - text: Question text (required for AI tagging)
    - needs_ai_tagging: Flag for questions missing tags
    - tagging_status: Track tagging workflow state
    
    RELATIONSHIPS:
    - TESTS_CONCEPT: Links Question → Concept (with AI metadata on edge)
    - REQUIRES_SKILL: Links Question → Skill (with AI metadata on edge)
    - HAS_DIFFICULTY: Links Question → Difficulty (with AI metadata on edge)
    
    IMPORTANT: Question text lives HERE, never in relationships or Concept nodes.
    """
    global_question_id = IntegerProperty(unique_index=True)
    text = StringProperty(required=True)  # Question text - first-class property
    
    # AI Tagging Control Flags
    needs_ai_tagging = BooleanProperty(default=False)
    tagging_status = StringProperty(default='untagged')  # untagged, pending, tagged, failed
    
    # ==========================================
    # QUESTION → TAG RELATIONSHIPS (with audit metadata)
    # ==========================================
    # TESTS_CONCEPT: Question assesses this concept (NOT HAS_TOPIC)
    # Edge stores: confidence_score, tag_source (llm/client/rule/hybrid), version, model_id
    tests_concepts = RelationshipTo(Concept, 'TESTS_CONCEPT', model=AITagMetadataRel)
    
    # REQUIRES_SKILL: Question requires this cognitive skill
    requires_skills = RelationshipTo(Skill, 'REQUIRES_SKILL', model=AITagMetadataRel)
    
    # HAS_DIFFICULTY: Question has this difficulty level
    has_difficulty = RelationshipTo(Difficulty, 'HAS_DIFFICULTY', model=AITagMetadataRel)
    
    # Legacy aliases for backward compatibility (deprecated, use new names)
    @property
    def topics(self):
        """DEPRECATED: Use tests_concepts instead"""
        return self.tests_concepts
    
    @property  
    def skills(self):
        """DEPRECATED: Use requires_skills instead"""
        return self.requires_skills
    
    @property
    def difficulties(self):
        """DEPRECATED: Use has_difficulty instead"""
        return self.has_difficulty


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

    # NEW: Direct link to Skill/Concept with ML scores
    mastery_skills = RelationshipTo('Skill', 'HAS_SKILL_MASTERY', model=MasteryRel)
    mastery_concepts = RelationshipTo('Concept', 'HAS_CONCEPT_MASTERY', model=MasteryRel)


class StudentSummary(StructuredNode):
        """
        Lightweight summary node for longitudinal metrics.

        Stored metrics (all numeric):
            - avg_accuracy: float (0-1)
            - accuracy_slope: float (trend slope across exams)
            - repeated_mistakes: int (count of concepts repeatedly answered incorrectly)
            - attempt_density: float (attempts per exam)
            - last_updated: timestamp

        The node is linked to a `Student` by matching `student_id` property.
        """
        student_id = IntegerProperty(unique_index=True)
        avg_accuracy = FloatProperty(default=0.0)
        accuracy_slope = FloatProperty(default=0.0)
        repeated_mistakes = IntegerProperty(default=0)
        attempt_density = FloatProperty(default=0.0)
        last_updated = DateTimeProperty(default_now=True)

