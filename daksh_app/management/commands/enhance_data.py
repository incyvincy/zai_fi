"""
Purpose: Enhance existing mock data with proper metadata using AI.
Works with ANY exam type (JEE, NEET, CUET, Boards, etc.)

What it does:
1. Reads existing question files
2. Uses AI to add concept, skill, difficulty if missing
3. Writes enhanced data back (preserves original in backup)
4. Makes data more specific without hardcoding exam types

Usage:
    python manage.py enhance_data                    # Enhance all exams
    python manage.py enhance_data --exam-id 1       # Enhance specific exam
    python manage.py enhance_data --dry-run         # Preview without saving
    python manage.py enhance_data --backup          # Create backup before enhancing
"""

import json
import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Enhance mock data with AI-generated metadata'

    def add_arguments(self, parser):
        parser.add_argument(
            '--exam-id',
            type=int,
            help='Enhance only a specific exam ID'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Create backup before modifying files'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=30,
            help='Number of questions to process per AI call'
        )

    def handle(self, *args, **options):
        from google import genai
        from google.genai import types
        
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        model_name = 'gemini-2.5-flash'  # Better free tier quota
        
        base_path = os.path.join(settings.BASE_DIR, 'mock_data')
        exams_dir = os.path.join(base_path, 'exams')
        
        dry_run = options.get('dry_run', False)
        backup = options.get('backup', False)
        exam_id_filter = options.get('exam_id')
        batch_size = options.get('batch_size', 30)
        
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.WARNING("   DATA ENHANCEMENT SCRIPT"))
        if dry_run:
            self.stdout.write(self.style.WARNING("   [DRY RUN - NO FILES WILL BE MODIFIED]"))
        self.stdout.write(self.style.WARNING("="*70 + "\n"))
        
        # Load exams metadata
        exams_file = os.path.join(exams_dir, 'exams.json')
        with open(exams_file, 'r', encoding='utf-8') as f:
            exams_data = json.load(f)
        
        stats = {
            'exams_processed': 0,
            'questions_processed': 0,
            'questions_enhanced': 0,
            'ai_calls': 0,
        }
        
        for exam in exams_data:
            exam_id = exam['exam_id']
            
            if exam_id_filter and exam_id != exam_id_filter:
                continue
            
            exam_name = exam.get('exam_name', f'Exam {exam_id}')
            self.stdout.write(self.style.HTTP_INFO(f"\n--- Processing: {exam_name} ---"))
            
            q_file = os.path.join(exams_dir, f'questions_exam_{exam_id}.json')
            if not os.path.exists(q_file):
                self.stdout.write(self.style.WARNING(f"  [SKIP] No questions file found"))
                continue
            
            # Create backup if requested
            if backup and not dry_run:
                backup_file = q_file.replace('.json', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
                shutil.copy(q_file, backup_file)
                self.stdout.write(f"  [BACKUP] Created: {os.path.basename(backup_file)}")
            
            with open(q_file, 'r', encoding='utf-8') as f:
                questions = json.load(f)
            
            # Find questions needing enhancement
            questions_to_enhance = []
            for q in questions:
                has_concept = q.get('concept') or q.get('topic')
                has_skill = q.get('skill') or q.get('skill_required')
                has_difficulty = q.get('difficulty')
                
                if not (has_concept and has_skill and has_difficulty):
                    questions_to_enhance.append(q)
            
            if not questions_to_enhance:
                self.stdout.write(f"  [OK] All {len(questions)} questions already have full metadata")
                stats['exams_processed'] += 1
                continue
            
            self.stdout.write(f"  [ENHANCE] {len(questions_to_enhance)} questions need metadata")
            
            # Process in batches
            enhanced_map = {}
            for i in range(0, len(questions_to_enhance), batch_size):
                batch = questions_to_enhance[i:i + batch_size]
                
                self.stdout.write(f"    Processing batch {i//batch_size + 1} ({len(batch)} questions)...", ending='')
                
                # Build prompt (exam-agnostic)
                questions_block = "\n".join([
                    f"Q{q['question_id']}: {q.get('question_text', '')[:300]}"
                    for q in batch
                ])
                
                prompt = f"""
Analyze these academic questions from "{exam_name}" and classify each one.

{questions_block}

For EACH question, provide a JSON object mapping question_id to metadata:
{{
  "<question_id>": {{
    "concept": "Specific topic (e.g., Rotational Motion, Organic Reactions, Quadratic Equations)",
    "parent_concept": "Broader subject (e.g., Physics, Chemistry, Mathematics)",
    "skill": "One of: Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving",
    "difficulty": "One of: Easy, Medium, Hard"
  }},
  ...
}}
"""
                
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.3
                        )
                    )
                    batch_result = json.loads(response.text)
                    enhanced_map.update(batch_result)
                    stats['ai_calls'] += 1
                    self.stdout.write(self.style.SUCCESS(" Done"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f" FAILED: {e}"))
                    continue
            
            # Apply enhancements to questions
            questions_enhanced = 0
            for q in questions:
                q_id = str(q['question_id'])
                if q_id in enhanced_map:
                    metadata = enhanced_map[q_id]
                    
                    # Only add if missing (don't overwrite existing client data)
                    if not (q.get('concept') or q.get('topic')):
                        q['concept'] = metadata.get('concept', 'General')
                        q['parent_concept'] = metadata.get('parent_concept', 'General')
                    
                    if not (q.get('skill') or q.get('skill_required')):
                        q['skill'] = metadata.get('skill', 'Application')
                    
                    if not q.get('difficulty'):
                        q['difficulty'] = metadata.get('difficulty', 'Medium')
                    
                    questions_enhanced += 1
                
                stats['questions_processed'] += 1
            
            stats['questions_enhanced'] += questions_enhanced
            
            # Save enhanced data
            if not dry_run and questions_enhanced > 0:
                with open(q_file, 'w', encoding='utf-8') as f:
                    json.dump(questions, f, indent=2, ensure_ascii=False)
                self.stdout.write(self.style.SUCCESS(f"  [SAVED] {questions_enhanced} questions enhanced"))
            elif dry_run:
                self.stdout.write(f"  [DRY RUN] Would enhance {questions_enhanced} questions")
            
            stats['exams_processed'] += 1
        
        # Summary
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.SUCCESS("   ENHANCEMENT COMPLETE"))
        self.stdout.write(self.style.WARNING("="*70))
        self.stdout.write(f"""
  STATISTICS:
    Exams Processed:      {stats['exams_processed']}
    Questions Processed:  {stats['questions_processed']}
    Questions Enhanced:   {stats['questions_enhanced']}
    AI API Calls:         {stats['ai_calls']}
""")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("  [DRY RUN] No files were modified."))
            self.stdout.write("  Run without --dry-run to apply changes.\n")
