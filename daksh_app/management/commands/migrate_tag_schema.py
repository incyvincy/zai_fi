"""
Purpose: Migrate existing tag relationships to new schema with audit metadata.

This command updates all existing Question→Tag relationships to include:
- confidence_score (float 0.0-1.0)
- tag_source ('client', 'llm', 'rule', 'hybrid')
- model_id (AI model identifier)
- version (int)
- created_at (timestamp)

RUN THIS AFTER UPDATING models.py TO NEW SCHEMA.

Usage:
    python manage.py migrate_tag_schema
    python manage.py migrate_tag_schema --dry-run  # Preview only
"""

from django.core.management.base import BaseCommand
from neomodel import db
from datetime import datetime


class Command(BaseCommand):
    help = 'Migrate existing tag relationships to new audit schema'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without applying them'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        
        self.stdout.write(self.style.WARNING("\n" + "="*80))
        self.stdout.write(self.style.WARNING("   TAG SCHEMA MIGRATION - Adding Audit Metadata"))
        self.stdout.write(self.style.WARNING("="*80 + "\n"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(">>> DRY RUN MODE - No changes will be made <<<\n"))
        
        stats = {
            'tests_concept_updated': 0,
            'requires_skill_updated': 0,
            'has_difficulty_updated': 0,
            'has_topic_updated': 0,
            'errors': 0
        }
        
        # ==========================================
        # MIGRATE TESTS_CONCEPT (Question → Concept)
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("--- Migrating TESTS_CONCEPT relationships ---"))
        
        # Find all TESTS_CONCEPT relationships missing confidence_score
        query_find = """
        MATCH (q:Question)-[r:TESTS_CONCEPT]->(c:Concept)
        WHERE r.confidence_score IS NULL
        RETURN q.global_question_id AS qid, c.name AS concept, 
               r.tag_source AS old_source, r.confidence AS old_conf
        """
        
        results, _ = db.cypher_query(query_find)
        self.stdout.write(f"  Found {len(results)} TESTS_CONCEPT relationships to migrate")
        
        if not dry_run and results:
            # Update relationships - migrate old 'confidence' to 'confidence_score'
            # and 'ai_generated' to 'llm'
            query_update = """
            MATCH (q:Question)-[r:TESTS_CONCEPT]->(c:Concept)
            WHERE r.confidence_score IS NULL
            SET r.confidence_score = COALESCE(r.confidence, 1.0),
                r.tag_source = CASE 
                    WHEN r.tag_source = 'ai_generated' THEN 'llm'
                    WHEN r.tag_source IS NULL THEN 'client'
                    ELSE r.tag_source
                END,
                r.version = COALESCE(r.version, 1),
                r.created_at = COALESCE(r.created_at, datetime()),
                r.model_id = CASE 
                    WHEN r.tag_source = 'ai_generated' OR r.tag_source = 'llm' THEN 'gemini-2.5-flash-legacy'
                    ELSE NULL
                END
            RETURN count(r) AS updated
            """
            result, _ = db.cypher_query(query_update)
            stats['tests_concept_updated'] = result[0][0] if result else 0
            self.stdout.write(self.style.SUCCESS(f"  ✓ Updated {stats['tests_concept_updated']} TESTS_CONCEPT relationships"))
        
        # ==========================================
        # MIGRATE REQUIRES_SKILL (Question → Skill)
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("\n--- Migrating REQUIRES_SKILL relationships ---"))
        
        query_find_skill = """
        MATCH (q:Question)-[r:REQUIRES_SKILL]->(s:Skill)
        WHERE r.confidence_score IS NULL
        RETURN count(r) AS count
        """
        results, _ = db.cypher_query(query_find_skill)
        count = results[0][0] if results else 0
        self.stdout.write(f"  Found {count} REQUIRES_SKILL relationships to migrate")
        
        if not dry_run and count > 0:
            query_update = """
            MATCH (q:Question)-[r:REQUIRES_SKILL]->(s:Skill)
            WHERE r.confidence_score IS NULL
            SET r.confidence_score = COALESCE(r.confidence, 1.0),
                r.tag_source = CASE 
                    WHEN r.tag_source = 'ai_generated' THEN 'llm'
                    WHEN r.tag_source IS NULL THEN 'client'
                    ELSE r.tag_source
                END,
                r.version = COALESCE(r.version, 1),
                r.created_at = COALESCE(r.created_at, datetime()),
                r.model_id = CASE 
                    WHEN r.tag_source = 'ai_generated' OR r.tag_source = 'llm' THEN 'gemini-2.5-flash-legacy'
                    ELSE NULL
                END
            RETURN count(r) AS updated
            """
            result, _ = db.cypher_query(query_update)
            stats['requires_skill_updated'] = result[0][0] if result else 0
            self.stdout.write(self.style.SUCCESS(f"  ✓ Updated {stats['requires_skill_updated']} REQUIRES_SKILL relationships"))
        
        # ==========================================
        # MIGRATE HAS_DIFFICULTY (Question → Difficulty)
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("\n--- Migrating HAS_DIFFICULTY relationships ---"))
        
        query_find_diff = """
        MATCH (q:Question)-[r:HAS_DIFFICULTY]->(d:Difficulty)
        WHERE r.confidence_score IS NULL
        RETURN count(r) AS count
        """
        results, _ = db.cypher_query(query_find_diff)
        count = results[0][0] if results else 0
        self.stdout.write(f"  Found {count} HAS_DIFFICULTY relationships to migrate")
        
        if not dry_run and count > 0:
            query_update = """
            MATCH (q:Question)-[r:HAS_DIFFICULTY]->(d:Difficulty)
            WHERE r.confidence_score IS NULL
            SET r.confidence_score = COALESCE(r.confidence, 1.0),
                r.tag_source = CASE 
                    WHEN r.tag_source = 'ai_generated' THEN 'llm'
                    WHEN r.tag_source IS NULL THEN 'client'
                    ELSE r.tag_source
                END,
                r.version = COALESCE(r.version, 1),
                r.created_at = COALESCE(r.created_at, datetime()),
                r.model_id = CASE 
                    WHEN r.tag_source = 'ai_generated' OR r.tag_source = 'llm' THEN 'gemini-2.5-flash-legacy'
                    ELSE NULL
                END
            RETURN count(r) AS updated
            """
            result, _ = db.cypher_query(query_update)
            stats['has_difficulty_updated'] = result[0][0] if result else 0
            self.stdout.write(self.style.SUCCESS(f"  ✓ Updated {stats['has_difficulty_updated']} HAS_DIFFICULTY relationships"))
        
        # ==========================================
        # MIGRATE LEGACY HAS_TOPIC (Question → Concept) -> TESTS_CONCEPT
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("\n--- Migrating legacy HAS_TOPIC (Question→Concept) to TESTS_CONCEPT ---"))
        
        query_find_legacy = """
        MATCH (q:Question)-[r:HAS_TOPIC]->(c:Concept)
        RETURN count(r) AS count
        """
        results, _ = db.cypher_query(query_find_legacy)
        count = results[0][0] if results else 0
        self.stdout.write(f"  Found {count} legacy HAS_TOPIC (Question→Concept) to convert")
        
        if not dry_run and count > 0:
            # Create new TESTS_CONCEPT relationships from old HAS_TOPIC
            query_migrate = """
            MATCH (q:Question)-[r:HAS_TOPIC]->(c:Concept)
            WITH q, c, r,
                 COALESCE(r.confidence, r.confidence_score, 1.0) AS conf,
                 CASE 
                    WHEN r.tag_source = 'ai_generated' THEN 'llm'
                    WHEN r.tag_source IS NULL THEN 'client'
                    ELSE r.tag_source
                 END AS source,
                 COALESCE(r.version, 1) AS ver
            MERGE (q)-[new:TESTS_CONCEPT]->(c)
            SET new.confidence_score = conf,
                new.tag_source = source,
                new.version = ver,
                new.created_at = datetime(),
                new.model_id = CASE WHEN source = 'llm' THEN 'gemini-2.5-flash-legacy' ELSE NULL END
            DELETE r
            RETURN count(new) AS migrated
            """
            result, _ = db.cypher_query(query_migrate)
            stats['has_topic_updated'] = result[0][0] if result else 0
            self.stdout.write(self.style.SUCCESS(f"  ✓ Migrated {stats['has_topic_updated']} HAS_TOPIC → TESTS_CONCEPT"))
        
        # ==========================================
        # MIGRATE LEGACY HAS_SKILL (Question → Skill) -> REQUIRES_SKILL
        # ==========================================
        self.stdout.write(self.style.HTTP_INFO("\n--- Migrating legacy HAS_SKILL to REQUIRES_SKILL ---"))
        
        query_find_has_skill = """
        MATCH (q:Question)-[r:HAS_SKILL]->(s:Skill)
        RETURN count(r) AS count
        """
        results, _ = db.cypher_query(query_find_has_skill)
        count = results[0][0] if results else 0
        self.stdout.write(f"  Found {count} legacy HAS_SKILL to convert")
        
        if not dry_run and count > 0:
            query_migrate = """
            MATCH (q:Question)-[r:HAS_SKILL]->(s:Skill)
            WITH q, s, r,
                 COALESCE(r.confidence, r.confidence_score, 1.0) AS conf,
                 CASE 
                    WHEN r.tag_source = 'ai_generated' THEN 'llm'
                    WHEN r.tag_source IS NULL THEN 'client'
                    ELSE r.tag_source
                 END AS source,
                 COALESCE(r.version, 1) AS ver
            MERGE (q)-[new:REQUIRES_SKILL]->(s)
            SET new.confidence_score = conf,
                new.tag_source = source,
                new.version = ver,
                new.created_at = datetime(),
                new.model_id = CASE WHEN source = 'llm' THEN 'gemini-2.5-flash-legacy' ELSE NULL END
            DELETE r
            RETURN count(new) AS migrated
            """
            result, _ = db.cypher_query(query_migrate)
            self.stdout.write(self.style.SUCCESS(f"  ✓ Migrated {result[0][0] if result else 0} HAS_SKILL → REQUIRES_SKILL"))
        
        # ==========================================
        # SUMMARY
        # ==========================================
        self.stdout.write(self.style.WARNING("\n" + "="*80))
        self.stdout.write(self.style.SUCCESS("   MIGRATION COMPLETE"))
        self.stdout.write(self.style.WARNING("="*80))
        
        total = sum([
            stats['tests_concept_updated'],
            stats['requires_skill_updated'],
            stats['has_difficulty_updated'],
            stats['has_topic_updated']
        ])
        
        self.stdout.write(f"""
  UPDATED RELATIONSHIPS:
    TESTS_CONCEPT:   {stats['tests_concept_updated']}
    REQUIRES_SKILL:  {stats['requires_skill_updated']}
    HAS_DIFFICULTY:  {stats['has_difficulty_updated']}
    HAS_TOPIC→TESTS: {stats['has_topic_updated']}
    ────────────────────────
    TOTAL:           {total}
  
  VERIFY WITH CYPHER:
    MATCH (q:Question)-[r:TESTS_CONCEPT]->(c:Concept)
    RETURN q.global_question_id, c.name, r.confidence_score, r.tag_source, r.model_id
    LIMIT 5
""")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n  >>> This was a DRY RUN. Run without --dry-run to apply changes. <<<\n"))
