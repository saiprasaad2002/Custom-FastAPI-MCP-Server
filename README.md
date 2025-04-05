# Job Application Agent

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)


## Overview

The **Job Application Agent** is a sophisticated, multi-agentic workflow orchestration system built using the **Model Context Protocol (MCP)** framework on top of **FastAPI**. This API automates the processing of job applications by integrating advanced natural language processing (NLP), semantic analysis, and email notification workflows. It leverages multiple specialized agents (tools) to extract resume content, generate job summaries, calculate semantic similarity scores, and dispatch interview invitations—all orchestrated through a modular MCP server.

The system is designed for scalability, extensibility, and robustness, making it suitable for HR automation, talent acquisition pipelines, and intelligent document processing use cases. It employs libraries such as `sentence-transformers` for semantic embeddings, `ollama` for LLM-driven workflow, and `resend` for email notifications, with persistent storage handled via SQLAlchemy and SQLite.

---

## Features

- **Resume Extraction**: Extracts text from PDF and DOCX files using `PyMuPDF` and `python-docx`.
- **Job Description Summarization**: Generates concise job requirement summaries using the `mistral:7b` model from `ollama`.
- **Semantic Scoring**: Computes a cosine similarity score (0-100) between resumes and job summaries using `sentence-transformers` (`all-MiniLM-L6-v2`).
- **Email Automation**: Sends interview invitations via the `resend` API for candidates scoring 70% or higher.
- **Duplicate Detection**: Identifies existing applications by email, resume content, and job description to prevent redundant processing.
- **Resume Validation**: Validates uploaded documents as resumes using LLM-based analysis.
- **Error Logging**: Persists detailed error logs in a SQLite database for debugging and auditing.
- **MCP Integration**: Orchestrates multi-agent workflows via a custom MCP server, exposing tools as reusable endpoints.

---

## Architecture

The application follows a modular, agent-based architecture orchestrated through the MCP framework:

1. **FastAPI**: Serves as the HTTP server, handling requests and responses with asynchronous endpoints.
2. **MCP Server**: Extends FastAPI with a `/mcp` mount path, providing a unified interface for agentic tools:
   - `extract_text`: Extracts content from resumes.
   - `generate_summary`: Summarizes job descriptions using an LLM.
   - `calculate_score`: Computes semantic similarity between resumes and job summaries.
   - `extract_email`: Identifies email addresses via regex.
   - `send_email` & `send_interview_invitation`: Manages email notifications.
   - `check_existing_application`: Detects duplicates in the database.
   - `validate_resume`: Ensures uploaded files are valid resumes.
3. **Database Layer**: Uses SQLAlchemy with SQLite to store application data (`applications`) and error logs (`error_logs`).
4. **File Handling**: Persists uploaded resumes in an `uploads/` directory.

### Workflow
1. A job application is submitted via the `/job-application` endpoint with a resume file and job description.
2. The MCP server orchestrates the following steps:
   - Validates and extracts resume content.
   - Checks for existing applications.
   - Summarizes the job description.
   - Scores the resume against the summary.
   - Sends an interview invitation if the score exceeds 70%.
3. Results are saved to the database, and errors are logged as needed.

---

## Technical Stack

| Component             | Technology             | Purpose                              |
|-----------------------|------------------------|--------------------------------------|
| **Framework**         | FastAPI               | Asynchronous API server             |
| **MCP**     | fastapi-mcp           | Standardized Multi-agent workflow orchestration  |
| **Database**          | SQLAlchemy, SQLite    | Persistent storage                  |
| **NLP**               | sentence-transformers | Semantic similarity scoring         |
| **LLM**               | ollama (mistral:7b)   | Job description summarization       |
| **Email**             | resend                | Notification delivery               |
| **File Processing**   | PyMuPDF, python-docx  | Resume text extraction              |
| **Dependency Mgmt**   | uv, pyproject.toml    | Package management                  |
| **Runtime**           | Python 3.10+          | Core language runtime               |

---

## API Endpoints

### POST `/job-application`
Processes a job application by analyzing a resume and job description.

- **Request**:
  - `file`: Resume file (PDF or DOCX)
  - `job_description`: Text of the job description
- **Response**:
  ```json
  {
    "email": "candidate@example.com",
    "score": 85.5,
    "email_status": true,
    "message": "Candidate has passed the eligibility for interview and invitation sent successfully",
    "job_description": "Full-stack developer with Python and AWS experience..."
  }

## Errors

The API may return the following HTTP error codes:

- **400**: Invalid file format or missing email
- **422**: Text extraction or processing errors
- **500**: Database or server errors

## MCP Tools

Accessible under the `/mcp` path, these tools are orchestrated internally by the MCP server but can be invoked individually for testing or extension:

- `/mcp/extract_text`
- `/mcp/generate_summary`
- `/mcp/calculate_score`
- `/mcp/extract_email`
- `/mcp/send_email`
- `/mcp/send_interview_invitation`
- `/mcp/check_existing_application`
- `/mcp/validate_resume`

## Database Schema

### `applications`

| Column            | Type      | Description                     |
|-------------------|-----------|---------------------------------|
| `id`              | Integer   | Primary key                     |
| `email`           | String    | Candidate email                 |
| `resume_content`  | Text      | Extracted resume text           |
| `job_description` | Text      | Job description text            |
| `score`           | Float     | Similarity score (0-100)        |
| `email_status`    | Boolean   | Email sent status               |
| `created_at`      | DateTime  | Timestamp of creation           |

### `error_logs`

| Column            | Type      | Description                     |
|-------------------|-----------|---------------------------------|
| `id`              | Integer   | Primary key                     |
| `error_message`   | Text      | Detailed error description      |
| `created_at`      | DateTime  | Timestamp of error occurrence   |

## Dependencies

Dependencies are managed via `pyproject.toml` using `uv`. Key libraries include:

- `fastapi`: API framework
- `fastapi-mcp`: MCP orchestration
- `sentence-transformers`: Semantic embeddings
- `ollama`: LLM integration
- `resend`: Email API
- `sqlalchemy`: ORM for database
- `PyMuPDF`, `python-docx`: File parsing

See `pyproject.toml` for the full list.

## Usage Notes

- Ensure the `RESEND_API_KEY` environment variable is set for email functionality.
- The `uploads/` directory must exist and be writable for resume storage.
- The SQLite database (`applications.db`) is initialized automatically via `init_db()` on startup.

## Resend API Note

This application currently uses a trial version of the Resend API without verifying or adding a domain. In this mode, email functionality is limited to specific test scenarios (e.g., sending to verified test emails). To extend this application for sending emails to all candidates, you must add and verify a domain in the Resend dashboard. Refer to the [Resend documentation](https://resend.com/docs) for instructions on domain verification.
