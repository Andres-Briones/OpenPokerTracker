import os
from pathlib import Path

class Config:
    SECRET_KEY = 'sdfp2q984hgaelcan'
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(Path.home(), ".config/poker/sessions")
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    DB_PATH = os.path.join(Path.home(), ".config/poker/poker.db")
