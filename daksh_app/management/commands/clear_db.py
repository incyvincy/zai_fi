"""
Nuclear Database Wipe Command

Purpose: Complete "hard wipe" of Neo4j database.
Deletes ALL nodes and relationships - no orphans left behind.

Why DETACH DELETE:
1. Prevents "Ghost Data" (orphaned nodes without relationships)
2. Schema Freedom (rename/change relationships without old versions)
3. Analytics Accuracy (exact counts, no old data pollution)

Usage:
    python manage.py clear_db
"""

from django.core.management.base import BaseCommand
from studybud.neo4j_driver import run_cypher


class Command(BaseCommand):
    help = 'Complete Nuclear Wipe of Neo4j Database (Nodes + Relationships)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("\n" + "="*70))
        self.stdout.write(self.style.WARNING("   ⚠️  WARNING: NUCLEAR DATABASE WIPE ⚠️"))
        self.stdout.write(self.style.WARNING("="*70))
        self.stdout.write("\nThis will PERMANENTLY DELETE:")
        self.stdout.write("  • ALL nodes (Questions, Students, Exams, Concepts, Skills, etc.)")
        self.stdout.write("  • ALL relationships (ATTEMPTED, HAS_TOPIC, INCLUDES, etc.)")
        self.stdout.write("  • NO UNDO - This gives you a clean slate\n")
        
        confirm = input("Are you absolutely sure? (type 'yes' to confirm): ")
        
        if confirm.lower() == 'yes':
            self.stdout.write(self.style.WARNING("\n🚀 Launching nuclear wipe..."))
            
            # The Nuclear Query
            # MATCH (n) = Find every node in the database
            # DETACH DELETE n = Delete all relationships first, then destroy the node
            # This prevents orphaned nodes
            run_cypher("MATCH (n) DETACH DELETE n")
            
            self.stdout.write(self.style.SUCCESS("\n✅ Database completely wiped."))
            self.stdout.write(self.style.SUCCESS("   Clean slate ready for fresh data ingestion."))
            self.stdout.write(self.style.SUCCESS("\n💡 Next step: python manage.py feed_data\n"))
        else:
            self.stdout.write(self.style.ERROR("\n❌ Operation cancelled. Database unchanged.\n"))
