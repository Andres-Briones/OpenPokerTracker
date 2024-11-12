import os
from pathlib import Path

config_path  =  ".config/OpenHandTracker" #Change this path if you want the configs to be stored elsewhere
data_path  =  "OpenHandTracker" #Change this path if you want the data to be stored elsewhere

class Config:
    SECRET_KEY = 'sdfp2q984hgaelcan'
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = os.path.join(Path.home(), data_path, "sessions")
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    UPLOADS_PATH = os.path.join(Path.home(), data_path, "uploads/")
    DB_DIRECTORY = os.path.join(Path.home(), data_path, "databases/")


    # Ensure all directories exist
    @staticmethod
    def ensure_directories():
        directories = [
            Config.SESSION_FILE_DIR,
            Config.DB_DIRECTORY,
            Config.UPLOADS_PATH
        ]
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory)
                print(f"Created directory: {directory}")

# Call the directory creation function when the module is loaded
Config.ensure_directories()
