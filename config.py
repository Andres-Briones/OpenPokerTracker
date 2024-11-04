import os
from pathlib import Path

config_path  =  ".config/OpenHandTracker" #Change this path if you want the data to be stored elsewhere

class Config:
    SECRET_KEY = 'sdfp2q984hgaelcan'
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(Path.home(), config_path, "sessions")
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    DB_PATH = os.path.join(Path.home(), config_path, "poker.db")
    UPLOADS_PATH = os.path.join(Path.home(), config_path, "uploads/")
