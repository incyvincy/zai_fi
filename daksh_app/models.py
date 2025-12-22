from neomodel import (
    StructuredNode, StringProperty, IntegerProperty, FloatProperty, 
    RelationshipTo, RelationshipFrom, StructuredRel, JSONProperty
)

# ==========================================
# PLANE A: THE KNOWLEDGE LAYER (The "Map")
# ==========================================
class Concept(StructuredNode):
    """
    Represents a concept/topic in the syllabus hierarchy.
    Examples: Physics, Mechanics, Rotational Motion
    """
    name = StringProperty(unique_index=True)
    # Recursive Relationship: "Rotational Motion" IS_PART_OF "Mechanics" IS_PART_OF "Physics"
    part_of = RelationshipTo('Concept', 'PART_OF')


# ==========================================
# PLANE B: THE ASSESSMENT LAYER (The "Territory")
# ==========================================
class QuestionRel(StructuredRel):
    """Relationship properties between Question and Concept"""
    weight = FloatProperty(default=1.0)  # Difficulty or importance


class Question(StructuredNode):
    """
    Represents a single question in an exam.
    Links to Concept (Plane A) to show what knowledge it tests.
    """
    # Global unique ID: exam_id * 1000 + question_id (e.g., exam 1 q 5 = 1005)
    global_question_id = IntegerProperty(unique_index=True)
    exam_id = IntegerProperty()  # Which exam this question belongs to
    question_id = IntegerProperty()  # Original question number (1-90)
    text = StringProperty()
    options = JSONProperty()
    correct_option = StringProperty()
    
    # LINK B -> A: This is how we know what a question "means"
    tests_concept = RelationshipTo(Concept, 'TESTS', model=QuestionRel)


class Exam(StructuredNode):
    """
    Represents an exam/test containing multiple questions.
    """
    exam_id = IntegerProperty(unique_index=True)
    name = StringProperty()
    duration = StringProperty()
    
    # Exam contains Questions
    includes = RelationshipTo(Question, 'INCLUDES')


# ==========================================
# PLANE C: THE LEARNER LAYER (The "Traveler")
# ==========================================
class AttemptRel(StructuredRel):
    """
    Detailed edge storing exactly what happened during the attempt.
    This is the rich relationship between Student and Question.
    """
    selected_option = StringProperty()
    time_spent = StringProperty()
    outcome = StringProperty()  # 'correct', 'incorrect', 'skipped'


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
    enrollment_id = StringProperty()

    # LINK C -> C: Student belongs to Cohort
    member_of = RelationshipTo(Cohort, 'MEMBER_OF')

    # LINK C -> B: The most important edge.
    # The student didn't just 'take an exam', they 'attempted specific questions'.
    attempted = RelationshipTo(Question, 'ATTEMPTED', model=AttemptRel)
