from neomodel import db
from datetime import datetime, timezone
import math


def _slope_from_points(points):
    # points: list of (x, y)
    n = len(points)
    if n < 2:
        return 0.0
    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xx = sum(x * x for x, _ in points)
    sum_xy = sum(x * y for x, y in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0
    return (n * sum_xy - sum_x * sum_y) / denom


def run_student_analysis(student_id):
    print(f"[ML] Running student analysis for {student_id}")

    # 1) Trend analysis: accuracy per exam
    q = '''
    MATCH (s:Student {student_id:$student_id})-[a:ATTEMPTED]->(q:Question)<-[:INCLUDES]-(e:Exam)
    WITH e.exam_id AS exam_id, e.name AS exam_name, SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    RETURN exam_id, exam_name, correct, total, CASE WHEN total=0 THEN 0.0 ELSE toFloat(correct)/total END AS accuracy
    ORDER BY exam_id
    '''
    res, meta = db.cypher_query(q, {'student_id': student_id})
    exams = []
    for row in res:
        exam_id, exam_name, correct, total, accuracy = row
        exams.append({'exam_id': exam_id, 'exam_name': exam_name, 'correct': correct, 'total': total, 'accuracy': float(accuracy)})

    print(f"[ML] Found {len(exams)} exams for student {student_id}")

    points = [(i, e['accuracy']) for i, e in enumerate(exams)]
    slope = _slope_from_points(points)
    if slope > 0.01:
        trend = 'Improving'
    elif slope < -0.01:
        trend = 'Declining'
    else:
        trend = 'Volatile'

    print(f"[ML] Trend: {trend} (slope={slope:.4f})")

    # 2) Weakness detection (concept-level)
    q2 = '''
    MATCH (s:Student {student_id:$student_id})-[a:ATTEMPTED]->(q:Question)-[:HAS_TOPIC]->(c:Concept)
    WITH c.name AS concept, SUM(CASE WHEN a.outcome='incorrect' THEN 1 ELSE 0 END) AS incorrect, SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    WHERE incorrect > 3 AND (toFloat(correct)/total) < 0.5
    RETURN concept, incorrect, correct, total
    '''
    res2, _ = db.cypher_query(q2, {'student_id': student_id})
    weaknesses = []
    for concept, incorrect, correct, total in res2:
        score = float(correct) / total if total else 0.0
        weaknesses.append({'concept': concept, 'incorrect': int(incorrect), 'correct': int(correct), 'total': int(total), 'score': score})

    print(f"[ML] Weak concepts: {len(weaknesses)}")

    # Write-back: update HAS_CONCEPT_MASTERY edges for high-risk
    for w in weaknesses:
        concept = w['concept']
        score = w['score']
        print(f"[ML] Marking concept '{concept}' as High risk (score={score:.2f}) for student {student_id}")
        write_q = '''
        MERGE (s:Student {student_id:$student_id})
        MERGE (c:Concept {name:$concept})
        MERGE (s)-[r:HAS_CONCEPT_MASTERY]->(c)
        SET r.mastery_score = $score, r.risk_level = 'High', r.last_updated_at = $now
        RETURN r
        '''
        now = datetime.now(timezone.utc)
        db.cypher_query(write_q, {'student_id': student_id, 'concept': concept, 'score': score, 'now': now})

    # 3) Skill gap analysis
    q3 = '''
    MATCH (s:Student {student_id:$student_id})-[a:ATTEMPTED]->(q:Question)-[:HAS_SKILL]->(sk:Skill)
    WITH sk.name AS skill, SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    WHERE total > 0
    RETURN skill, correct, total, toFloat(correct)/total AS accuracy
    ORDER BY accuracy ASC
    '''
    res3, _ = db.cypher_query(q3, {'student_id': student_id})
    skills_low = []
    for skill, correct, total, accuracy in res3:
        acc = float(accuracy)
        if acc < 0.6:
            skills_low.append({'skill': skill, 'correct': int(correct), 'total': int(total), 'accuracy': acc})
            # Write-back
            print(f"[ML] Writing skill mastery for '{skill}' (accuracy={acc:.2f})")
            write_q = '''
            MERGE (s:Student {student_id:$student_id})
            MERGE (sk:Skill {name:$skill})
            MERGE (s)-[r:HAS_SKILL_MASTERY]->(sk)
            SET r.mastery_score = $score, r.risk_level = $risk, r.last_updated_at = $now
            RETURN r
            '''
            risk = 'High' if acc < 0.5 else 'Medium'
            score = acc
            now = datetime.now(timezone.utc)
            db.cypher_query(write_q, {'student_id': student_id, 'skill': skill, 'score': score, 'risk': risk, 'now': now})

    # 4) Consistency: attempt density
    q4 = '''
    MATCH (s:Student {student_id:$student_id})-[a:ATTEMPTED]->(q:Question)<-[:INCLUDES]-(e:Exam)
    RETURN COUNT(a) AS attempts, COUNT(DISTINCT e) AS exams
    '''
    res4, _ = db.cypher_query(q4, {'student_id': student_id})
    attempts = exams_count = 0
    if res4 and len(res4) > 0:
        attempts, exams_count = res4[0]
    attempts = int(attempts or 0)
    exams_count = int(exams_count or 0)
    attempt_density = float(attempts) / exams_count if exams_count else float(attempts)
    print(f"[ML] Attempt density: {attempt_density:.2f} (attempts={attempts}, exams={exams_count})")

    result = {
        'student_id': student_id,
        'trend': trend,
        'trend_slope': slope,
        'exams': exams,
        'weaknesses': weaknesses,
        'skill_gaps': skills_low,
        'attempts': attempts,
        'exams_count': exams_count,
        'attempt_density': attempt_density
    }

    return result


def run_cohort_analysis(cohort_name):
    print(f"[ML] Running cohort analysis for '{cohort_name}'")

    # Get cohort students
    q_students = '''
    MATCH (co:Cohort {name:$cohort})<-[:MEMBER_OF]-(s:Student)
    RETURN s.student_id AS student_id
    '''
    res_s, _ = db.cypher_query(q_students, {'cohort': cohort_name})
    student_ids = [r[0] for r in res_s]
    cohort_size = len(student_ids)
    print(f"[ML] Cohort size: {cohort_size}")

    if cohort_size == 0:
        return {'cohort': cohort_name, 'cohort_size': 0, 'cohort_accuracy': 0.0, 'alerts': [], 'leaderboard': {}}

    # Batch health: overall accuracy
    q_health = '''
    MATCH (co:Cohort {name:$cohort})<-[:MEMBER_OF]-(s:Student)-[a:ATTEMPTED]->(q:Question)
    WITH SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    RETURN CASE WHEN total=0 THEN 0.0 ELSE toFloat(correct)/total END AS accuracy
    '''
    res_h, _ = db.cypher_query(q_health, {'cohort': cohort_name})
    cohort_accuracy = float(res_h[0][0]) if res_h and len(res_h) > 0 else 0.0
    print(f"[ML] Cohort accuracy: {cohort_accuracy:.3f}")

    # Teacher Alert: Concepts failed by >40% students
    # We'll compute per-student per-concept accuracy then aggregate in Python for clarity
    q_concept = '''
    MATCH (co:Cohort {name:$cohort})<-[:MEMBER_OF]-(s:Student)-[a:ATTEMPTED]->(q:Question)-[:HAS_TOPIC]->(c:Concept)
    WITH s.student_id AS sid, c.name AS concept, SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    RETURN sid, concept, correct, total
    '''
    res_c, _ = db.cypher_query(q_concept, {'cohort': cohort_name})
    # organize per concept
    from collections import defaultdict
    per_concept = defaultdict(list)
    for sid, concept, correct, total in res_c:
        acc = float(correct) / total if total else 1.0
        per_concept[concept].append((sid, acc))

    alerts = []
    for concept, entries in per_concept.items():
        failing = [1 for sid, acc in entries if acc < 0.5]
        failing_count = sum(failing)
        student_count = len(entries)
        failing_ratio = float(failing_count) / student_count if student_count else 0.0
        if student_count and failing_ratio > 0.4:
            alerts.append({'concept': concept, 'failing_count': failing_count, 'student_count': student_count, 'failing_ratio': failing_ratio})
            print(f"[ML] Alert: {failing_ratio*100:.1f}% of cohort failing {concept} ({failing_count}/{student_count})")

    # Leaderboard / Risk groups
    # Exclude students with very few attempts from leaderboard to avoid 'lucky guesser' effect
    q_students_acc = '''
    MATCH (co:Cohort {name:$cohort})<-[:MEMBER_OF]-(s:Student)-[a:ATTEMPTED]->(:Question)
    WITH s.student_id AS sid, SUM(CASE WHEN a.outcome='correct' THEN 1 ELSE 0 END) AS correct, COUNT(a) AS total
    WHERE total > $min_attempts
    RETURN sid, CASE WHEN total=0 THEN 0.0 ELSE toFloat(correct)/total END AS accuracy
    ORDER BY accuracy DESC
    '''
    min_attempts = 5
    res_la, _ = db.cypher_query(q_students_acc, {'cohort': cohort_name, 'min_attempts': min_attempts})
    top = []
    stable = []
    at_risk = []
    for sid, acc in res_la:
        accf = float(acc)
        if accf > 0.8:
            top.append(sid)
        elif accf >= 0.5:
            stable.append(sid)
        else:
            at_risk.append(sid)

    leaderboard = {'top_performers': top, 'stable': stable, 'at_risk': at_risk}

    return {
        'cohort': cohort_name,
        'cohort_size': cohort_size,
        'cohort_accuracy': cohort_accuracy,
        'alerts': alerts,
        'leaderboard': leaderboard
    }
