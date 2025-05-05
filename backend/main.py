from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain.chains.llm import LLMChain
from dotenv import load_dotenv
import os
import re
import tempfile
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pypdf import PdfReader
import streamlit as st
import pandas as pd

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')
EMAIL_SENDER = os.getenv('EMAIL_SENDER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'localhost')  # Default to localhost for local testing
SMTP_PORT = int(os.getenv('SMTP_PORT', 1025))  # Default port for local testing

def pdf_loader(pdf_file):
    """Extract text from PDF file."""
    temp_dir = tempfile.TemporaryDirectory()
    tempfile_path = os.path.join(temp_dir.name, pdf_file.name)
    with open(tempfile_path, 'wb') as f:
        f.write(pdf_file.getbuffer())
        pdf_reader = PdfReader(tempfile_path)
        text = ''
        for page in pdf_reader.pages:
            text += page.extract_text()
    
    temp_dir.cleanup()
    return text

def analyz_match(cv_text, job_description):
    """Analyze match between CV and job description."""
    template = """
    You are an expert in HR system analyzing job applications.
    TASK: Compare the CV content with the job description and determine if there's a good match.

    CV CONTENT:
    {cv_text}

    JOB DESCRIPTION:
    {job_description}

    Evaluate the match by identifying key skills, qualifications, and experience from the job description,
    and determining if they appear in the CV. Calculate an overall match percentage.

    Output your analysis in the following format:
    - Match Percentage: [percentage]
    - Matching Skills: [comma-separated list] 
    - Missing Skills: [comma-separated list]
    - Strengths: [brief summary]
    - Gaps: [brief summary]
    - Recommendation: [ACCEPT or REJECT]
    """
    
    prompt = PromptTemplate(template=template,
                          input_variables=['cv_text', 'job_description'])
    llm = ChatGroq(
        model_name="llama3-8b-8192",
        temperature=0,
        api_key=GROQ_API_KEY
    )

    chain = LLMChain(llm=llm, prompt=prompt)
    response = chain.invoke({
        'cv_text': cv_text,
        'job_description': job_description
    })
    
    # Handle the response based on its structure
    response_text = ""
    if isinstance(response, dict) and 'text' in response:
        response_text = response['text'] 
    elif isinstance(response, str):
        response_text = response
    else:
        # Try to convert to string if it's another type
        response_text = str(response)
    
    # Extracts Match Percentage
    match_percentage_pattern = r'Match Percentage:?\s*(\d+)'
    match = re.search(match_percentage_pattern, response_text)
    match_percentage = 0
    
    if match:
        match_percentage = int(match.group(1))
    else:
        # Try alternative patterns
        alt_patterns = [
            r'Match Percentage:?\s*(\d+)%',  # With percent sign
            r'Match Percentage.*?(\d+)',     # Any text between
            r'match.*?(\d+)%'                # Lowercase with percent
        ]
        
        for pattern in alt_patterns:
            alt_match = re.search(pattern, response_text, re.IGNORECASE)
            if alt_match:
                match_percentage = int(alt_match.group(1))
                break
    
    # Extracts Recommendation
    recommendation_patterns = [
        r'Recommendation:?\s*(ACCEPT|REJECT)',
        r'Recommendation:?\s*(Accept|Reject)',
        r'Recommendation.*?(ACCEPT|REJECT)',
        r'Recommendation.*?(Accept|Reject)'
    ]
    
    recommendation = None
    
    for pattern in recommendation_patterns:
        rec_match = re.search(pattern, response_text, re.IGNORECASE)
        if rec_match:
            recommendation = rec_match.group(1).upper()
            break
    
    # Default to REJECT if no recommendation found
    if recommendation is None:
        # Check if the text contains "accept" anywhere as fallback
        if re.search(r'\baccept\b', response_text, re.IGNORECASE):
            recommendation = "ACCEPT"
        else:
            recommendation = "REJECT"
    
    return (response_text, match_percentage, recommendation)

def email_content(applicant_name, job_title, is_match):
    """Generate email content based on match status."""
    if is_match:
        email_subject = f'Congratulations! Your Application for {job_title}'
        email_body = f'''Dear {applicant_name},

We are pleased to inform you that your CV has been reviewed and shows a strong match with our {job_title} position.
We would like to invite you to the next stage of our recruitment process.
Our team will contact you shortly with further details.

Before that you need to complete this MCQ based test.
MCQs.
1. What is the capital of France?
Option A: Paris
Option B: London
Option C: New York
Option D: Tokyo

Best regards,
Recruitment Team
'''
    else:
        email_subject = f'Regarding your application for {job_title}'
        email_body = f'''Dear {applicant_name},

Thank you for your interest in the {job_title} position.
After careful review of your application, we regret to inform you that we will not be moving forward with your candidacy at this time.
We appreciate your interest in our company and wish you the best in your job search.

Best regards,
Recruitment Team
'''
    
    return email_subject, email_body

def send_email(recipient_email, subject, body):
    """Send an email to the recipient."""
    try:
        # Create message
        message = MIMEMultipart()
        message['From'] = EMAIL_SENDER
        message['To'] = recipient_email
        message['Subject'] = subject

        # Attach body
        message.attach(MIMEText(body, 'plain'))

        # Connect to server and send
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()

            # Login only if credentials are provided
            if EMAIL_SENDER and EMAIL_PASSWORD:
                server.login(EMAIL_SENDER, EMAIL_PASSWORD)

            server.send_message(message)
        
        return True, 'Email sent successfully!'
    except Exception as e:
        return False, f'Failed to send email: {str(e)}'

def process_application(cv_file, applicant_name, applicant_email, job_title, job_description, match_threshold=70):
    """Process a job application by analyzing CV and sending appropriate email."""
    # Extract text from CV
    cv_text = pdf_loader(cv_file)
    
    # Analyze match
    analysis_text, match_percentage, recommendation = analyz_match(cv_text, job_description)

    if not analysis_text:
        return {
            'success': False,
            'message': 'Failed to analyze the CV.'
        }

    # Determine if the CV matches the job requirements
    # Use BOTH the match percentage AND recommendation for the final decision
    is_match = (match_percentage >= match_threshold or recommendation == "ACCEPT")
    
    # Generate email content based on match status
    email_subject, email_body = email_content(applicant_name, job_title, is_match)
    
    # Send email
    email_success, email_message = send_email(applicant_email, email_subject, email_body)

    # Return results with the keys exactly matching what the frontend expects
    return {
        'success': True,
        'applicant_name': applicant_name,
        'job_title': job_title,
        'match_percentage': match_percentage,
        'recommendation': "Accept" if is_match else "Reject",  # This is what the frontend uses
        'email_sent': email_success, 
        'email_message': email_message,
        'analysis': analysis_text
    }