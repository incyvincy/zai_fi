"""
Longitudinal analysis utilities for Day 4.

Provides functions to compute student-level metrics and store a lightweight
`StudentSummary` node in Neo4j.

Functions:
 - analyze_student(student_id)
 - update_student_summary(student_id)
 - compute_all_student_summaries()

Notes:
 - Works with `AttemptRel.outcome` values: 'correct'|'incorrect'|'skipped'
 - Uses `Exam` inclusion to compute per-exam accuracy when possible
"""

from datetime import datetime
from neomodel import db
from .models import Student, StudentSummary


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def analyze_student(student_id: int) -> dict:
    """Compute metrics for a single student.

    Returns dict with keys: total_attempts, correct_attempts, avg_accuracy,
    exams_participated, per_exam_accuracy (list of (exam_id, accuracy)),
    repeated_mistakes, attempt_density
    """
    try:
        student = Student.nodes.get(student_id=student_id)
    except Student.DoesNotExist:
        return {'error': 'student_not_found'}

    # Total attempts and correct
    total_attempts = 0
    correct_attempts = 0
    # Track incorrect attempts per concept name
    incorrect_by_concept = {}

    for q in student.attempted.all():
        rel = student.attempted.relationship(q)
        total_attempts += 1
        outcome = (rel.outcome or '').lower()
        if outcome == 'correct':
            correct_attempts += 1
        else:
            # collect concepts for incorrect attempts
            for c in q.topics.all():
                incorrect_by_concept[c.name] = incorrect_by_concept.get(c.name, 0) + 1

    avg_accuracy = (correct_attempts / total_attempts) if total_attempts else 0.0

    # Per-exam accuracy (use Cypher to group by exam)
    per_exam_query = f"""
    MATCH (s:Student {{student_id: {student_id}}})-[r:ATTEMPTED]->(q:Question)
    OPTIONAL MATCH (q)<-[:INCLUDES]-(e:Exam)
    WHERE exists(e.exam_id)
    RETURN e.exam_id AS exam_id,
      sum(CASE WHEN r.outcome = 'correct' THEN 1 ELSE 0 END) AS correct,
      count(r) AS total
    ORDER BY exam_id
    """

    per_exam_accuracy = []
    try:
        res, cols = db.cypher_query(per_exam_query)
        for row in res:
            exam_id = row[0]
            correct = int(row[1] or 0)
            total = int(row[2] or 0)
            acc = (correct / total) if total else 0.0
            per_exam_accuracy.append((exam_id, acc))
    except Exception:
        per_exam_accuracy = []

    exams_participated = len(per_exam_accuracy) if per_exam_accuracy else 0

    # repeated_mistakes: number of concepts with more than 1 incorrect attempt
    repeated_mistakes = sum(1 for v in incorrect_by_concept.values() if v > 1)

    attempt_density = (total_attempts / exams_participated) if exams_participated else 0.0

    return {
        'total_attempts': total_attempts,
        'correct_attempts': correct_attempts,
        'avg_accuracy': avg_accuracy,
        'exams_participated': exams_participated,
        'per_exam_accuracy': per_exam_accuracy,
        'repeated_mistakes': repeated_mistakes,
        'attempt_density': attempt_density
    }


def _slope_from_points(points: list) -> float:
    """Simple linear regression slope for y-values in order.
    points: list of floats (y). x is 0..n-1
    """
    n = len(points)
    if n < 2:
        return 0.0
    xs = list(range(n))
    ys = points
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n))
    return (num / den) if den != 0 else 0.0


def update_student_summary(student_id: int) -> dict:
    """Compute metrics and create/update a StudentSummary node.

    Returns the metrics dict stored.
    """
    metrics = analyze_student(student_id)
    if metrics.get('error'):
        return metrics

    per_exam = [m for (_, m) in metrics.get('per_exam_accuracy', [])]
    slope = _slope_from_points(per_exam)

    # create or update StudentSummary node
    summary = StudentSummary.nodes.get_or_none(student_id=student_id)
    if not summary:
        summary = StudentSummary(student_id=student_id)

    summary.avg_accuracy = _safe_float(metrics['avg_accuracy'])
    summary.accuracy_slope = _safe_float(slope)
    summary.repeated_mistakes = int(metrics['repeated_mistakes'])
    summary.attempt_density = _safe_float(metrics['attempt_density'])
    summary.last_updated = datetime.utcnow()
    summary.save()

    return metrics


def compute_all_student_summaries():
    """Compute and store summaries for all students in the graph."""
    students = Student.nodes.all()
    results = {'processed': 0, 'errors': []}
    for s in students:
        try:
            update_student_summary(s.student_id)
            results['processed'] += 1
        except Exception as e:
            results['errors'].append({'student_id': s.student_id, 'error': str(e)})
    return results
