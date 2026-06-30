import sys, os

path = os.path.dirname(__file__)
if path not in sys.path:
    sys.path.append(path)

os.environ["SESSION_SECRET"] = os.environ.get("SESSION_SECRET", os.urandom(24).hex())
os.environ["ADMIN_PASSWORD"] = os.environ.get("ADMIN_PASSWORD", "admin123")

from app import app as application

if __name__ == "__main__":
    application.run()
