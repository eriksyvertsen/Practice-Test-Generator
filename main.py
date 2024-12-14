from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import PyPDF2
import openai
import os
from typing import List
import random
import json
from dotenv import load_dotenv
from io import BytesIO

# Create the app
app = FastAPI()

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Store PDF content in memory (in a real app, you'd want to use a database)
pdf_contents = []

# Get API key from Replit secrets
try:
    openai.api_key = os.environ['OPENAI_API_KEY']
except KeyError:
    print("Warning: OPENAI_API_KEY not found in environment variables!")
    print("Please add your OpenAI API key to Replit Secrets with the key 'OPENAI_API_KEY'")

def extract_text_from_pdf(pdf_bytes):
    # Convert bytes to BytesIO stream
    pdf_stream = BytesIO(pdf_bytes)
    pdf_reader = PyPDF2.PdfReader(pdf_stream)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def generate_questions(content: str, num_questions: int = 25):
    # Verify API key is available
    if not openai.api_key:
        raise Exception("OpenAI API key not configured. Please add it to Replit Secrets.")

    # Trim content to avoid token limits
    max_content_length = 3000  # Reduce content length to ensure we stay within limits
    trimmed_content = content[:max_content_length]

    prompt = f"""Create exactly {num_questions} multiple choice questions based on this content. 
    For each question, provide:
    1. The question text
    2. Four answer choices labeled A, B, C, D
    3. The correct answer (as the index 0-3)
    4. A brief explanation

    Format your response precisely as a JSON array of objects with these exact keys:
    {{
        "question": "question text",
        "options": ["A", "B", "C", "D"],
        "correct_answer": 0,
        "explanation": "explanation text"
    }}

    Content for questions: {trimmed_content}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",  # Using the latest model which handles JSON better
            messages=[
                {"role": "system", "content": "You are a quiz generator that outputs only valid JSON arrays containing question objects."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }  # Request JSON format specifically
        )

        # Extract the content from the response
        response_text = response.choices[0].message.content
        print("API Response:", response_text)  # Debug print

        # Parse the JSON response
        try:
            questions_data = json.loads(response_text)
            # If the response is wrapped in an extra object, extract the questions array
            if isinstance(questions_data, dict) and "questions" in questions_data:
                questions_data = questions_data["questions"]
            return questions_data
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {str(e)}")
            print(f"Response text: {response_text}")
            raise Exception("Failed to parse the generated questions. Please try again.")

    except Exception as e:
        print(f"Error generating questions: {str(e)}")
        raise Exception(f"Failed to generate questions: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    global pdf_contents
    pdf_contents = []

    try:
        for file in files:
            if file.filename.endswith('.pdf'):
                contents = await file.read()
                text = extract_text_from_pdf(contents)
                if text.strip():  # Only add non-empty content
                    pdf_contents.append(text)

        if not pdf_contents:
            return {"error": "No valid PDF content found in uploaded files"}

        return {"message": f"Successfully uploaded {len(pdf_contents)} files"}
    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        return {"error": f"Error processing files: {str(e)}"}

@app.post("/generate-quiz")
async def generate_quiz():
    if not pdf_contents:
        return {"error": "No PDF content available"}

    try:
        # Combine all PDF contents and generate questions
        combined_content = " ".join(pdf_contents)
        questions = generate_questions(combined_content)

        # Validate questions format
        if not isinstance(questions, list):
            raise Exception("Generated questions are not in the correct format")

        return {"questions": questions}
    except Exception as e:
        print(f"Quiz generation error: {str(e)}")
        return {"error": str(e)}

# Create necessary directories if they don't exist
os.makedirs("templates", exist_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)