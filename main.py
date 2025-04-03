from fastapi import FastAPI, UploadFile, Form, File, HTTPException
import uvicorn
import os
import shutil
import re
import fitz
import docx
import ollama
from sentence_transformers import SentenceTransformer
import resend
import torch
from dotenv import load_dotenv
from database import (
    save_application,  
    get_application_by_resume, 
    insert_error_log,
    init_db,
    update_email_status,
    get_exact_application_match
)
from fastapi_mcp import add_mcp_server

load_dotenv()

init_db()

app = FastAPI(
    title="Job Application Processor API",
    description="An API for processing job applications with integrated MCP server for automation tools.",
    version="0.1.0",
)

mcp_server = add_mcp_server(
    app,
    mount_path="/mcp",
    name="JobApplicationProcessorMCP",
    description="MCP server for job application processing tools, including resume extraction, scoring, and email notifications.",
    base_url="http://localhost:8000",
    describe_all_responses=False,
    describe_full_response_schema=False,    
)

@mcp_server.tool()
def extract_text(file_path: str) -> str:
    """
    Extracts text from DOCX or PDF files.
    
    Args:
        file_path (str): Path to the PDF or DOCX file.
    
    Returns:
        str: Extracted text from the file.
    
    Raises:
        ValueError: If the file format is not supported (must be PDF or DOCX).
    """
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(file_path)
            text = "\n".join([page.get_text("text") for page in doc])
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs])
        else:
            raise ValueError("Unsupported file format. Upload PDF or DOCX.")
        return text.strip()
    except Exception as e:
        error_message = f"Error occurred during extracting the text from the resume: {e}"
        insert_error_log(error_message)
        raise


@mcp_server.tool()
def generate_summary(job_description: str) -> str:
    """
    Uses Ollama to create a focused summary of job requirements in a single paragraph.
    
    Args:
        job_description (str): The job description text to summarize.
    
    Returns:
        str: A concise paragraph summarizing the key requirements and skills.
    """
    try:
        prompt = """
        Create a single, concise paragraph that summarizes ALL key requirements and skills from this job description. 
        Focus on technical skills, qualifications, experience levels, and essential requirements.
        Include specific technologies, tools, education, and experience requirements.
        
        Format: Return ONLY the summary paragraph, nothing else.
        
        Example output:
        "Looking for a Python developer with FastAPI experience, AWS cloud knowledge, and machine learning skills. Requires Bachelor's in Computer Science or related field, familiarity with Git version control, and REST APIs. Must have basic understanding of Docker, CI/CD pipelines, and database systems. Fresh graduates with 0-2 years experience and strong problem-solving skills are welcome."
        
        Job Description to analyze:
        {job_description}
        """
        
        response = ollama.chat(
            model='mistral:7b',
            messages=[
                {
                    'role': 'user',
                    'content': prompt.format(job_description=job_description)
                }
            ],
            stream=False,
            options={
                "temperature": 0.1,
            }
        )
        if not response or 'message' not in response:
            return "Failed to extract requirements: No response from model"
        return response['message']['content'].strip()
    except Exception as e:
        error_message = f"Error occurred during generating the summary of the job description from Ollama: {e}"
        insert_error_log(error_message)
        return str(e)

@mcp_server.tool()
def calculate_score(resume_text: str, job_summary: str) -> float:
    """
    Calculates similarity score using pure semantic analysis with SentenceTransformer.
    
    Args:
        resume_text (str): The extracted text from the resume.
        job_summary (str): The summarized job description.
    
    Returns:
        float: A similarity score between 0 and 100.
    """
    try:
        if not job_summary or job_summary.startswith("Failed to extract"):
            return 0.0
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        def get_semantic_embeddings(text: str):
            chunks = [s.strip() for s in text.lower().split('.') if s.strip()]
            chunks.extend([p.strip() for s in chunks for p in s.split(',') if p.strip()])
            return model.encode(chunks, convert_to_tensor=True)
        
        
        resume_embeddings = get_semantic_embeddings(resume_text)
        job_embeddings = get_semantic_embeddings(job_summary)
        
        similarity = torch.cosine_similarity(
            torch.mean(resume_embeddings, dim=0).unsqueeze(0),
            torch.mean(job_embeddings, dim=0).unsqueeze(0)
        ).item()
        
        final_score = round(min(100.0, max(0.0, similarity * 100)), 2)
        return final_score
        
    except Exception as e:
        error_message = f"Error occurred during calculating the cosine similarity score: {e}"
        insert_error_log(error_message)
        return str(e)

@mcp_server.tool()
def extract_email(text: str) -> str:
    """
    Extracts the first email address found in the text using regex.
    
    Args:
        text (str): The text to search for an email address.
    
    Returns:
        str: The first email address found, or an empty string if none is found.
    """
    try:
        match = re.search(r'[\w\.-]+@[\w\.-]+', text)
        result = match.group(0) if match else ""
        return result
    except Exception as e:
        error_message = f"Error occurred during extracting the email from the resume: {e}"
        insert_error_log(error_message)
        return str(e)
@mcp_server.tool()
def send_email(email: str, subject: str, body: str) -> bool:
    """
    Sends an email using Resend API.
    
    Args:
        email (str): The recipient's email address.
        subject (str): The email subject.
        body (str): The email body (plain text).
    
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    try:
        resend.api_key = os.getenv("RESEND_API_KEY")
        if not resend.api_key:
            raise Exception("Resend API key not found")
        response = resend.Emails.send({
            "from": "Your App <onboarding@resend.dev>",
            "to": email,
            "subject": subject,
            "text": body
        })
        return True
    except Exception as e:
        error_message = f"Error occurred during sending the email from Resend tool: {str(e)}"
        insert_error_log(error_message)
        return False

@mcp_server.tool()
def send_interview_invitation(email: str, score: float) -> bool:
    """
    Sends an initial interview invitation with a YouCanBook.me link.
    
    Args:
        email (str): The recipient's email address.
        score (float): The match score of the application.
    
    Returns:
        bool: True if the email was sent successfully, False otherwise.
    """
    try:
        booking_link = "https://interview-slot-test.youcanbook.me/"
        
        subject = "Interview Invitation - Next Steps"
        body = f"""
Congratulations! Based on your application review (Match Score: {score}%), we would like to invite you for an interview.
Once you select a time slot, you will receive a detailed confirmation email with meeting instructions.
Please schedule your interview using the link below:
{booking_link}
Best regards,
Your Company Name
"""
        
        if send_email(email, subject, body):
            update_email_status(email, True)
            return True
        return False
    except Exception as e:
        error_message = f"Error occurred during sending the interview invitation email: {str(e)}"
        insert_error_log(error_message)
        return False

@mcp_server.tool()
def check_existing_application(resume_text: str):
    """
    Checks if an application with the same resume content exists in the database.
    
    Args:
        resume_text (str): The extracted text from the resume.
    
    Returns:
        tuple: (email, score) if an existing application is found, (None, None) otherwise.
    """
    try:
        existing_app = get_application_by_resume(resume_text)
        if existing_app:
            return existing_app.email, existing_app.score
        return None, None
    except Exception as e:
        error_message = f"Error occurred during checking the existing application in the database: {e}"
        insert_error_log(error_message)
        return str(e)

@mcp_server.tool()
def validate_resume(text: str) -> bool:
    """
    Validates if the extracted text is from a resume document.
    
    Args:
        text (str): The extracted text from the document.
    
    Returns:
        bool: True if the document is a resume, False otherwise.
    """
    try:
        prompt = """
        Analyze the following text and determine if it is from a resume/CV document.
        A resume typically contains:
        - Personal information (name, contact details)
        - Professional summary or objective
        - Work experience with dates and descriptions
        - Education details
        - Skills and qualifications
        - Projects or achievements
        
        Return ONLY 'true' if it's a resume, 'false' if it's not.
        Do not include any explanations or additional text.
        Go through the text thoroughly and then decide if it's a resume or not. Don't be too quick to decide it in the middle of the text itself.
        
        Text to analyze:
        {text}
        """
        
        response = ollama.chat(
            model='mistral:7b',
            messages=[
                {
                    'role': 'user',
                    'content': prompt.format(text=text)
                }
            ],
            stream=False,
            options={
                "temperature": 0.1,
            }
        )
        
        if not response or 'message' not in response:
            return False
            
        result = response['message']['content'].strip().lower()
        return result == 'true'
    except Exception as e:
        error_message = f"Error occurred during resume validation: {str(e)}"
        insert_error_log(error_message)
        return False

@app.post("/job-application", tags=["job-application"])
async def process_application(
    file: UploadFile = File(..., description="The resume file in PDF or DOCX format"),
    job_description: str = Form(..., description="The job description text to compare against the resume")
):
    """
    Process a job application by extracting resume content, calculating a match score, and sending an interview invitation if the score is high.

    - Saves the uploaded resume file.
    - Extracts text and email from the resume.
    - Checks for existing applications in the database.
    - If same email exists:
        - If resume content is same: Return existing score
        - If resume content is different: Update resume and recalculate score
    - For new applications:
        - Generate job summary and calculate score
        - Save to database
    - Sends an interview invitation if the score is 80% or higher.

    Returns:
    - email: The extracted email from the resume.
    - score: The calculated match score (0-100).
    - email_status: The status of the email sent (True if sent, False if not sent)
    - job_description: The job description text used for processing the application
    - message: A status message about the processing result.

    Raises:
    - HTTPException(400): For invalid file formats or missing email
    - HTTPException(422): For text extraction or processing errors
    - HTTPException(500): For database or server errors
    """
    try:
        if not file.filename.lower().endswith(('.pdf', '.docx')):
            insert_error_log(f"Invalid file format. Only PDF and DOCX files are supported. File name: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only PDF and DOCX files are supported."
            ) 

        file_path = f"uploads/{file.filename}"
        os.makedirs("uploads", exist_ok=True)
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            insert_error_log(f"Failed to save uploaded file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save uploaded file: {str(e)}"
            )

        try:
            resume_content = extract_text(file_path)
        except ValueError as e:
            insert_error_log(f"Value error occurred during extracting the text from the resume: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        except Exception as e:
            insert_error_log(f"Failed to extract text from resume: {str(e)}")
            raise HTTPException(
                status_code=422,
                detail=f"Failed to extract text from resume: {str(e)}"
            )

        if not validate_resume(resume_content):
            insert_error_log("Uploaded document is not a resume")
            raise HTTPException(
                status_code=400,
                detail="The uploaded document does not appear to be a resume. Please upload a valid resume document."
            )

        email = extract_email(resume_content)
        if not email:
            insert_error_log("No email address found in resume")
            raise HTTPException(
                status_code=400,
                detail="No email address found in resume"
            )

        try:
            existing_app = get_exact_application_match(email, resume_content, job_description)
            email_sent = False
            email_message = ""
            
            if existing_app:
                return {
                    "email": email, 
                    "score": existing_app.score,
                    "email_status": existing_app.email_status,
                    "message": "Retrieved existing application score from database"
                }
            
            try:
                job_summary = generate_summary(job_description)
                if isinstance(job_summary, str) and job_summary.startswith("Error"):
                    insert_error_log(f"Not an exception but failed to generate job summary: {job_summary}")
                    raise HTTPException(
                        status_code=422,
                        detail=f"Failed to generate job summary: {job_summary}"
                    )
            except Exception as e:
                insert_error_log(f"Exception occured: Failed to generate job summary: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to generate job summary: {str(e)}"
                )

            try:
                score = calculate_score(resume_content, job_summary)
                if not isinstance(score, float):
                    insert_error_log(f"Not an exception but failed to calculate score: {score}")
                    raise HTTPException(
                        status_code=422,
                        detail=f"Failed to calculate score: {score}"
                    )
            except Exception as e:
                insert_error_log(f"Exception occured: Failed to calculate score: {str(e)}")
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to calculate score: {str(e)}"
                )
            
            if score >= 70:
                email_message = "Candidate has passed the eligibility for interview"
                try:
                    if send_interview_invitation(email, score):
                        email_sent = True
                        email_message += " and interview invitation sent successfully"
                    else:
                        email_message += ", but failed to send the email"
                except Exception as e:
                    email_message += ", but failed to send the email"
                    insert_error_log(f"Failed to send interview invitation: {str(e)}")
            else:
                email_message = "Candidate did not meet the minimum score requirement"
            
            try:
                save_application(email, resume_content, job_description, score, email_sent)
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to save application to database: {str(e)}"
                )

            return {
                "email": email, 
                "score": score,
                "email_status": email_sent,
                "message": email_message
            }
                
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        error_message = f"Error occurred during processing the job application: {str(e)}"
        insert_error_log(error_message)
        raise HTTPException(
            status_code=500,
            detail=error_message
        )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)