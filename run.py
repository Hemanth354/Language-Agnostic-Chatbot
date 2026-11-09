import os
import sys
import uvicorn
from app.config import HOST, PORT, DEBUG

if __name__ == "__main__":
    print("=" * 65)
    print("   LANGUAGE AGNOSTIC CHATBOT (SIH25104)")
    print("   Theme: Smart Education | Team TechTitans RGUKTN")
    print("=" * 65)
    print(f" * Server running on: http://localhost:{PORT}")
    print(f" * Student Chatbot UI: http://localhost:{PORT}/")
    print(f" * Volunteer Circulars: http://localhost:{PORT}/admin")
    print(f" * Faculty Portal:     http://localhost:{PORT}/faculty")
    print(f" * WhatsApp/Telegram:  http://localhost:{PORT}/simulator")
    print(f" * API Documentation:  http://localhost:{PORT}/docs")
    print("=" * 65)
    
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)

