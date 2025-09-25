import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "uploads/commands"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}

# Make sure folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
