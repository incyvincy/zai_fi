"""
Purpose: One-time script to fix existing data without guessing.

What it does:
1. Identifies questions with missing or suspicious tags
2. Sets needs_ai_tagging=True for untagged questions
3. Keeps existing client tags (does NOT delete anything)
4. Prepares queue for AI tagging

Usage:
    python manage.py repair_data              # Scan and flag
    python manage.py repair_data --run-ai     # Scan, flag, and run AI tagging
    python manage.py repair_data --dry-run    # Preview without changes
"""

from django.core.management.base import BaseCommand
from daksh_app.models import Question
from daksh_app.ai_tagging import batch_tag_questions


class Command(BaseCommand):
    help = 'Scan and repair questions with missing tags'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without modifying the database'
        )
        parser.add_argument(
            '--run-ai',
            action='store_true',
            help='Run AI tagging after flagging questions'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of questions to process'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        run_ai = options.get('run_ai', False)
        limit = options.get('limit')
        
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.WARNING("   DATA REPAIR SCRIPT (Day 1 - Backfill)"))
        if dry_run:
            self.stdout.write(self.style.WARNING("   [DRY RUN - NO CHANGES WILL BE MADE]"))
        self.stdout.write(self.style.WARNING("="*70 + "\n"))
        
        # Get all questions
        questions = Question.nodes.all()
        if limit:
            questions = questions[:limit]
        
        stats = {
            'total': 0,
            'missing_topic': 0,
            'missing_skill': 0,
            'missing_difficulty': 0,
            'missing_text': 0,
            'flagged': 0,
            'already_flagged': 0,
            'fully_tagged': 0,
        }
        
        flagged_ids = []
        
        self.stdout.write(self.style.HTTP_INFO("--- SCANNING QUESTIONS ---"))
        
        for q in questions:
            stats['total'] += 1
            
            # Check for missing text (critical)
            if not q.text or q.text.strip() == '':
                stats['missing_text'] += 1
                self.stdout.write(self.style.ERROR(
                    f"  [CRITICAL] Q{q.global_question_id}: Missing question text!"
                ))
                continue
            
            # Check for missing tags
            has_topic = len(q.topics.all()) > 0
            has_skill = len(q.skills.all()) > 0
            has_difficulty = len(q.difficulties.all()) > 0
            
            if not has_topic:
                stats['missing_topic'] += 1
            if not has_skill:
                stats['missing_skill'] += 1
            if not has_difficulty:
                stats['missing_difficulty'] += 1
            
            # Determine if flagging is needed
            needs_flagging = not (has_topic and has_skill and has_difficulty)
            
            if needs_flagging:
                if q.needs_ai_tagging:
                    stats['already_flagged'] += 1
                else:
                    stats['flagged'] += 1
                    flagged_ids.append(q.global_question_id)
                    
                    if not dry_run:
                        q.needs_ai_tagging = True
                        q.tagging_status = 'untagged'
                        q.save()
                    
                    missing = []
                    if not has_topic:
                        missing.append('topic')
                    if not has_skill:
                        missing.append('skill')
                    if not has_difficulty:
                        missing.append('difficulty')
                    
                    self.stdout.write(
                        f"  [FLAG] Q{q.global_question_id}: Missing {', '.join(missing)}"
                    )
            else:
                stats['fully_tagged'] += 1
        
        # Summary
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.SUCCESS("   REPAIR SCAN COMPLETE"))
        self.stdout.write(self.style.WARNING("="*70))
        self.stdout.write(f"""
  SCAN RESULTS:
    Total Questions:    {stats['total']}
    Fully Tagged:       {stats['fully_tagged']}
    Already Flagged:    {stats['already_flagged']}
    Newly Flagged:      {stats['flagged']}
    Missing Text:       {stats['missing_text']} (CRITICAL)
    
  MISSING BREAKDOWN:
    Missing Topic:      {stats['missing_topic']}
    Missing Skill:      {stats['missing_skill']}
    Missing Difficulty: {stats['missing_difficulty']}
""")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("  [DRY RUN] No changes were made."))
            self.stdout.write("  Run without --dry-run to apply changes.\n")
        
        # Optionally run AI tagging
        if run_ai and not dry_run and (stats['flagged'] + stats['already_flagged']) > 0:
            self.stdout.write(self.style.HTTP_INFO("\n--- RUNNING AI TAGGING ---"))
            try:
                total_to_tag = stats['flagged'] + stats['already_flagged']
                result = batch_tag_questions(limit=total_to_tag)
                self.stdout.write(self.style.SUCCESS(
                    f"  [OK] AI Tagging: {result['success']}/{result['processed']} successful"
                ))
                if result['failed'] > 0:
                    self.stdout.write(self.style.WARNING(f"  [WARN] {result['failed']} questions failed"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  [ERROR] AI Tagging failed: {e}"))
