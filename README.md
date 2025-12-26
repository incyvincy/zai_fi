📚 StudyBud - AI-Powered Exam Analytics

This project is a Neo4j-backed exam analysis system that uses Google Gemini AI to tag questions, detect exam types, and generate student insights.
🚀 Quick Start
1. Prerequisites

    Python 3.x

    Neo4j Database (Running locally or cloud)

    Google Gemini API Key

2. Configuration

Create a .env file in studybud/ with your credentials:
Ini, TOML

NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_HOST=127.0.0.1
NEO4J_PORT=7687
GOOGLE_API_KEY=your_gemini_api_key

🛠️ Command-Line Interface (CLI) Workflow

The system uses Django management commands to handle the data lifecycle. Here is the recommended order of operations:
1. Enhance Data (Pre-Seed)

File: studybud/daksh_app/management/commands/enhance_data.py

Before loading data into the database, use this to "enrich" your raw JSON files. It uses AI to fill in missing Concept, Skill, and Difficulty tags directly in your .json files.

Usage:
Bash

# Enhance all questions in mock_data/exams/
python manage.py enhance_data

# Specific Exam only
python manage.py enhance_data --exam-id 1

# Safety Mode (Recommended)
python manage.py enhance_data --backup --dry-run

Key Arguments:

    --backup: Creates a timestamped copy of your JSON file before modifying it (e.g., questions_exam_1_backup_2024...json). Always use this to prevent data loss.

    --dry-run: Shows you what would happen (how many questions would be tagged) without actually writing to the files.

    --exam-id <ID>: Limits the script to a specific exam ID (e.g., 1), useful if you only added one new file.

2. Clear Database (Reset)

File: studybud/daksh_app/management/commands/clear_db.py

Performs a "nuclear wipe" of the Neo4j database. It deletes ALL nodes and relationships to ensure a clean slate for ingestion.

Usage:
Bash

python manage.py clear_db

    Warning: This action is irreversible. It requires a manual "yes" confirmation in the prompt.

3. Feed Data (Ingestion)

File: studybud/daksh_app/management/commands/feed_data.py

Loads your JSON data (Exams, Questions, Students, Attempts) into the Neo4j graph. It automatically detects exam types (e.g., JEE, NEET, SAT) using AI if not specified.

Usage:
Bash

# Standard Load (Safe Mode - flags missing tags but doesn't guess)
python manage.py feed_data

# Load + Immediate AI Tagging for gaps
python manage.py feed_data --tag-with-ai

Key Features:

    Safe Handling: Never guesses missing tags. If a question lacks metadata, it sets needs_ai_tagging=True.

    Time Tracking: Loads time spent on questions only if valid data exists (prevents skewing stats with 0s).

4. Repair Data (Maintenance)

File: studybud/daksh_app/management/commands/repair_data.py

A maintenance script for the live database. It scans for questions that might have slipped through without tags or text and fixes them using AI.

Usage:
Bash

# Scan and flag broken questions
python manage.py repair_data

# Scan and immediately fix using AI
python manage.py repair_data --run-ai --limit 50

Key Arguments:

    --limit <int>: Process only a set number of questions (e.g., 50). Useful to avoid hitting API rate limits.

    --run-ai: Actually executes the AI tagging for flagged questions. Without this, it just marks them as "needing attention."

    --dry-run: Preview which questions would be flagged.

📂 Key File Breakdown
File	Purpose
models.py	The Schema. Defines the Graph structure using neomodel. It splits data into 3 Planes: Knowledge (Concepts/Skills), Assessment (Exams/Questions), and Learner (Students/Attempts).
gemini_ai_service.py	The Brain. Contains the logic to call Google Gemini. It handles question classification (Topic, Skill, Difficulty) and generating student insight summaries.
enhance_data.py	File Editor. Modifies the source JSON files on your disk. Use this during development/setup to prepare your mock data.
repair_data.py	DB Doctor. Modifies the Neo4j Database. Use this in production/maintenance to fix gaps in live data.
feed_data.py	The Loader. The bridge between JSON files and Neo4j. It orchestrates the creation of nodes and relationships.
