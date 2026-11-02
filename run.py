"""Quick launcher for JM Vertex Hackathon 2027 platform."""
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from app.config import settings
from app.main import app

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("⚡ JM VERTEX HACKATHON 2027 · SERVER STARTING")
    print("=" * 65)
    print(f"🌐 Public Site:       http://{settings.HOST}:{settings.PORT}/")
    print(f"📝 Team Registration: http://{settings.HOST}:{settings.PORT}/register")
    print(f"🔐 Admin Dashboard:   http://{settings.HOST}:{settings.PORT}/admin")
    print(f"🔑 Admin Login:       http://{settings.HOST}:{settings.PORT}/admin/login")
    print(f"   (Admin User: {settings.ADMIN_USERNAME} | Password: {settings.ADMIN_PASSWORD})")
    print("=" * 65 + "\n")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info")
