# 📚 StudyBud - AI-Powered Exam Analytics Platform

> A Neo4j-backed exam analysis system powered by Google Gemini AI for intelligent question tagging, exam type detection, and student performance insights.

[![Django](https://img.shields.io/badge/Django-6.0-green.svg)](https://www.djangoproject.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Graph%20Database-blue.svg)](https://neo4j.com/)
[![Gemini AI](https://img.shields.io/badge/AI-Google%20Gemini%202.5%20Flash-orange.svg)](https://ai.google.dev/)

---

## 🌟 Features

- **Universal Exam Support**: Works with any exam type worldwide (JEE, NEET, SAT, TOEFL, CA, CLAT, etc.)
- **AI-Powered Question Tagging**: Automatic classification of topics, skills, and difficulty levels
- **Smart Exam Type Detection**: AI identifies exam types from names (Science, Commerce, Arts, Language, Aptitude)
- **Graph-Based Analytics**: Leverage Neo4j's power to track student performance across concepts and skills
- **Flexible Data Ingestion**: Safe handling of incomplete data - never guesses, always flags for AI review
- **Version Control for AI Tags**: Keep history of AI classification improvements without losing data

---

## 🏗️ Architecture Overview

### Three-Plane Graph Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLANE A: KNOWLEDGE LAYER                      │
│              (Concepts, Skills, Difficulty Levels)               │
│                         "The Map"                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HAS_TOPIC, REQUIRES_SKILL, HAS_DIFFICULTY
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  PLANE B: ASSESSMENT LAYER                       │
│                    (Exams, Questions)                            │
│                      "The Territory"                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ ATTEMPTED, BELONGS_TO_COHORT
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PLANE C: LEARNER LAYER                        │
│                  (Students, Attempts, Cohorts)                   │
│                       "The Journey"                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites

- **Python 3.11+** (3.13 recommended)
- **Neo4j Database** (v5.x) - [Download](https://neo4j.com/download/)
- **Google Gemini API Key** - [Get one free](https://ai.google.dev/)

### 2. Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd django/studybud

# Create virtual environment (if not exists)
python -m venv ../daksh_django

# Activate virtual environment
# Windows:
..\daksh_django\Scripts\activate
# Linux/Mac:
source ../daksh_django/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in `studybud/` directory:

```ini
# Neo4j Database Configuration
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password
NEO4J_HOST=127.0.0.1
NEO4J_PORT=7687

# Google Gemini AI Configuration
GOOGLE_API_KEY=your_gemini_api_key_here

# Django Settings (Optional)
SECRET_KEY=your-django-secret-key
DEBUG=True
```

### 4. Database Setup

```bash
# Start Neo4j database (ensure it's running)
# Then run Django migrations
python manage.py migrate

# Install neomodel schema
python manage.py install_labels
```

---

## 📋 CLI Workflow Guide

The system uses Django management commands for the complete data lifecycle. Follow this order:

### Step 1: Enhance Data (Pre-Processing) ✨

**Purpose**: Enrich your raw JSON files with AI-generated tags before loading into the database.

```bash
# Enhance all exam data with AI tags (with backup)
python manage.py enhance_data --backup

# Enhance specific exam only
python manage.py enhance_data --exam-id 1 --backup

# Preview changes without modifying files (Safe Mode)
python manage.py enhance_data --dry-run

# Enhance and immediately load into database
python manage.py enhance_data --backup --run-feed
```

**Arguments:**

- `--backup`: Creates timestamped backup (e.g., `questions_exam_1_backup_20241227_143022.json`) ⭐ **Always use this**
- `--dry-run`: Preview changes without writing to files
- `--exam-id <ID>`: Process only specific exam ID
- `--run-feed`: Automatically run `feed_data` after enhancement

**Example Output:**

```
✓ Enhanced: questions_exam_1.json (45/50 questions tagged)
✓ Backup saved: questions_exam_1_backup_20241227_143022.json
```

---

### Step 2: Clear Database (Reset) 🗑️

**Purpose**: Wipe the entire Neo4j database for a clean slate.

```bash
python manage.py clear_db
```

> ⚠️ **Warning**: This deletes ALL nodes and relationships. Requires manual "yes" confirmation.

---

### Step 3: Feed Data (Ingestion) 📥

**Purpose**: Load JSON data (Exams, Questions, Students, Attempts) into Neo4j graph database.

```bash
# Standard ingestion (safe mode - flags missing tags)
python manage.py feed_data

# Ingest + AI tagging for questions missing metadata
python manage.py feed_data --tag-with-ai
```

**Key Features:**

- ✅ **Safe Handling**: Never guesses missing tags - sets `needs_ai_tagging=True` instead
- ✅ **AI-Powered Exam Type Detection**: Automatically classifies exam types (JEE, SAT, TOEFL, etc.)
- ✅ **Time Tracking**: Only stores time_spent if valid data exists (no fake zeros)
- ✅ **Client Tag Priority**: Client-provided tags are marked with `source='client'` and take precedence

**Example Output:**

```
==========================================================================================
   SAFE DATA INGESTION (Day 1 - Missing Data Handling)
==========================================================================================

--- PHASE 1: INGESTING EXAMS & QUESTIONS ---
  [EXAM] 1: JEE Main 2024 Mock Test (type: science_engineering)
    +-- 50 questions loaded

--- PHASE 2: INGESTING STUDENTS & ATTEMPTS ---
  [STUDENT] 101: Rahul Kumar
    +-- 48 attempts recorded

  STATISTICS:
    Exams:     1
    Questions: 50 (30 tagged, 20 need AI)
    Students:  1
    Attempts:  48 (45 with time data)
```

---

### Step 4: Repair Data (Maintenance) 🔧

**Purpose**: Fix existing database by flagging/tagging questions that slipped through without proper metadata.

```bash
# Scan database and flag broken questions
python manage.py repair_data

# Scan + immediately fix using AI (limit to prevent rate limits)
python manage.py repair_data --run-ai --limit 50

# Preview which questions would be flagged
python manage.py repair_data --dry-run
```

**Arguments:**

- `--run-ai`: Execute AI tagging for flagged questions
- `--limit <int>`: Process max N questions (default: 100)
- `--dry-run`: Preview without making changes

**Use Cases:**

- Questions missing text content
- Questions without any tags (concept, skill, difficulty)
- Data integrity checks after manual edits

---

## 📂 Project Structure

```
django/
├── daksh_django/              # Virtual environment (activated)
│   ├── Lib/site-packages/    # Django, neomodel, google-genai, etc.
│   └── Scripts/               # activate, python, pip
│
└── studybud/                  # Django project root
    ├── manage.py              # Django CLI entry point
    ├── .env                   # Environment variables (DO NOT COMMIT)
    ├── studybud/              # Project settings
    │   ├── settings.py        # Django + Neo4j config
    │   ├── urls.py            # URL routing
    │   └── neo4j_driver.py    # Neo4j connection singleton
    │
    ├── daksh_app/             # Main application
    │   ├── models.py          # 🧬 Neo4j graph schema (3-plane architecture)
    │   ├── gemini_ai_service.py  # 🧠 AI classification logic
    │   ├── ai_tagging.py      # 🏷️ AI tagging + graph integration
    │   ├── neo4j_service.py   # 🔌 Neo4j CRUD operations
    │   ├── views.py           # API endpoints
    │   ├── urls.py            # App URL routing
    │   │
    │   └── management/commands/
    │       ├── enhance_data.py   # Pre-process JSON files with AI
    │       ├── feed_data.py      # Load data into Neo4j
    │       ├── repair_data.py    # Fix broken database records
    │       └── clear_db.py       # Nuclear DB wipe
    │
    └── mock_data/             # Sample data (JSON files)
        ├── exams/
        │   ├── exams.json
        │   ├── questions_exam_1.json
        │   └── questions_exam_2.json
        └── students/
            ├── student_101.json
            └── student_102.json
```

---

## 🔑 Key Files Explained

| File                       | Purpose                                                                                                                                                       | When to Use                                     |
| -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **`models.py`**            | 🧬 **The Schema** - Defines Neo4j graph structure using `neomodel`. Implements 3-plane architecture (Knowledge → Assessment → Learner).                       | Reference when understanding data relationships |
| **`gemini_ai_service.py`** | 🧠 **The Brain** - Centralized AI logic using Google Gemini. Handles question classification and insight generation. Single source of truth for all AI calls. | When adding new AI features                     |
| **`ai_tagging.py`**        | 🏷️ **Graph Tagger** - Integrates AI classifications into Neo4j. Handles versioning, rate limiting, and tag priority (client > AI).                            | For understanding tagging workflow              |
| **`enhance_data.py`**      | ✏️ **File Editor** - Modifies source JSON files on disk. Use during setup/development to prepare mock data.                                                   | Before initial ingestion                        |
| **`feed_data.py`**         | 📥 **The Loader** - Ingests JSON → Neo4j. Handles exams, questions, students, attempts. AI-powered exam type detection.                                       | Every time you reset DB                         |
| **`repair_data.py`**       | 🔧 **DB Doctor** - Fixes live database issues. Scans for missing tags/text and flags for AI review.                                                           | Production maintenance                          |
| **`clear_db.py`**          | 🗑️ **Nuclear Option** - Wipes entire Neo4j database. No undo.                                                                                                 | When starting fresh                             |

---

## 🎯 Common Workflows

### Scenario 1: Adding New Mock Data

```bash
# 1. Add your JSON files to mock_data/exams/ or mock_data/students/

# 2. Enhance with AI (creates backup automatically)
python manage.py enhance_data --backup --exam-id 3

# 3. Clear database (if you want a fresh start)
python manage.py clear_db

# 4. Load everything
python manage.py feed_data --tag-with-ai
```

### Scenario 2: Fixing Production Data

```bash
# 1. Scan for issues (safe - no changes)
python manage.py repair_data --dry-run

# 2. Fix in batches (prevents API rate limits)
python manage.py repair_data --run-ai --limit 50

# 3. Verify
python manage.py repair_data --dry-run  # Should show 0 issues
```

### Scenario 3: Updating AI Classification Logic

```bash
# 1. Edit gemini_ai_service.py classify_question() function

# 2. Re-tag all questions with new logic (creates v2 tags)
python manage.py repair_data --run-ai --force-retag
```

---

## 🔬 AI Capabilities

### Universal Question Classification

The system can classify questions from **any exam type worldwide**:

| Domain               | Supported Exams                    | Example Topics                         |
| -------------------- | ---------------------------------- | -------------------------------------- |
| **Science**          | JEE, NEET, AP, A-Levels, Olympiads | Physics, Chemistry, Biology, Math      |
| **Commerce**         | CA, CPA, CFA, MBA, ACCA            | Accounting, Economics, Finance         |
| **Language**         | TOEFL, IELTS, GRE Verbal, PTE      | Reading Comprehension, Grammar         |
| **Aptitude**         | SAT, CAT, GMAT, Civil Services     | Logical Reasoning, Quantitative        |
| **Humanities**       | UPSC, AP, A-Levels                 | History, Political Science, Psychology |
| **Computer Science** | Coding Tests, Interviews           | Algorithms, Data Structures            |
| **Law**              | CLAT, LSAT, Bar Exams              | Legal Reasoning, Constitution          |
| **Medical**          | USMLE, PLAB                        | Anatomy, Physiology, Pathology         |

### Classification Output

For each question, AI provides:

- **Topic**: Broader concept (e.g., "Mechanics", "Organic Chemistry", "Reading Comprehension")
- **Parent Topic**: Domain (e.g., "Physics", "Chemistry", "English Language")
- **Skill**: Cognitive level (Recall, Understanding, Application, Analysis, Evaluation, Problem-Solving)
- **Difficulty**: Easy, Medium, or Hard
- **Confidence Scores**: 0.0-1.0 for each classification

---

## 🛡️ Data Safety Features

1. **Never Guesses**: Missing metadata is flagged, not fabricated
2. **Client Tag Priority**: Manual tags always override AI
3. **Version Control**: AI re-runs create new versions (v1, v2, v3...) without deleting history
4. **Automatic Backups**: `enhance_data --backup` creates timestamped copies
5. **Dry Run Mode**: Preview changes before committing
6. **Rate Limiting**: Built-in 5 requests/min throttling for Gemini API

---

## 🔍 Troubleshooting

### Issue: "Connection refused" to Neo4j

**Solution:**

```bash
# Check if Neo4j is running
# Windows: Open Neo4j Desktop
# Linux: sudo systemctl status neo4j

# Verify connection details in .env file
NEO4J_HOST=127.0.0.1  # or localhost
NEO4J_PORT=7687        # default bolt port
```

### Issue: "GOOGLE_API_KEY not found"

**Solution:**

```bash
# Check .env file exists in studybud/ directory
# Verify API key is valid at https://aistudio.google.com/apikey

# Test API manually:
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('GOOGLE_API_KEY'))"
```

### Issue: "Rate limit exceeded" during AI tagging

**Solution:**

```bash
# Use --limit to process fewer questions per run
python manage.py repair_data --run-ai --limit 25

# The system auto-throttles to 5 req/min but smaller batches are safer
```

### Issue: Questions have no text after ingestion

**Solution:**

```bash
# Run repair to find and flag them
python manage.py repair_data --dry-run

# The issue is likely in your JSON files - check mock_data/exams/
# Ensure "question_text" field exists and is not empty
```

---

## 📊 Example Queries (Neo4j Browser)

```cypher
-- Find all questions tagged with "Mechanics"
MATCH (q:Question)-[:HAS_TOPIC]->(c:Concept {name: "Mechanics"})
RETURN q.global_question_id, q.text

-- Student performance on "Organic Chemistry" questions
MATCH (s:Student {student_id: 101})-[a:ATTEMPTED]->(q:Question)-[:HAS_TOPIC]->(c:Concept {name: "Organic Chemistry"})
RETURN q.global_question_id, a.outcome, a.time_spent_seconds

-- Find questions needing AI tagging
MATCH (q:Question)
WHERE q.needs_ai_tagging = true
RETURN count(q)

-- Get AI vs Client tag statistics
MATCH (q:Question)-[r:HAS_TOPIC]->()
RETURN r.tag_source, count(*) as count
```

---

## 🚧 Roadmap

- [ ] Web dashboard for visualizing student performance
- [ ] Batch API endpoints for external integrations
- [ ] Support for image-based questions (OCR + AI)
- [ ] Real-time learning path recommendations
- [ ] Multi-language support (Hindi, Spanish, etc.)
- [ ] Export reports to PDF/Excel

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 💬 Support

For questions or issues:

- Open an issue on GitHub
- Check existing documentation in code comments
- Review Neo4j query examples above

---

## 🙏 Acknowledgments

- **Django** - Web framework
- **neomodel** - Neo4j OGM for Python
- **Google Gemini** - AI classification engine
- **Neo4j** - Graph database platform

---

**Built with ❤️ for students and educators worldwide.**
