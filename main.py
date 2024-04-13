import os
import threading
import argparse
import time
import subprocess
from modules.get_stream_link import main as get_stream_link_main
from modules.user_check import main as user_check_main
from modules.gui import main as gui_main

# Set up argument parsing
parser = argparse.ArgumentParser(description="Run the application with or without GUI.")
parser.add_argument('--nogui', action='store_true', help="Disable the GUI to save resources.")

# Parse arguments
args = parser.parse_args()

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BINARIES_DIR = os.path.join(BASE_DIR, 'binaries') 
LOCK_FILES_DIR = os.path.join(BASE_DIR, 'lock_files')
VIDEOS_DIR = os.path.join(BASE_DIR, 'videos')

def create_folders():
    # Ensure directories exist
    os.makedirs(LOCK_FILES_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)


def disable_quickedit():
    if not os.name == 'posix':
        try:
            import msvcrt
            import ctypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            device = r'\\.\CONIN$'
            with open(device, 'r') as con:
                hCon = msvcrt.get_osfhandle(con.fileno())
                kernel32.SetConsoleMode(hCon, 0x0080)
        except Exception as e:
            print('Cannot disable QuickEdit mode! ' + str(e))
            print('.. As a consequence the script might be automatically\
            paused on Windows terminal, please disable it manually!')
            
def clear_lock_files():
    # Remove all .lock files in the lock_files directory
    for file in os.listdir(LOCK_FILES_DIR):
        if file.endswith(".lock"):
            os.remove(os.path.join(LOCK_FILES_DIR, file))

def run_downloader():
    # Execute the download_live.exe within its directory
    executable_path = os.path.join(BINARIES_DIR, 'download_live.exe')
    subprocess.run([executable_path], cwd=BINARIES_DIR)

if __name__ == "__main__":
    
    disable_quickedit()
    create_folders()
    clear_lock_files()
    
    # Create threads for each module's main function
    get_stream_link_thread = threading.Thread(target=get_stream_link_main)
    user_check_thread = threading.Thread(target=user_check_main)

    # Only start GUI thread if --nogui is not specified
    if not args.nogui:
        gui_thread = threading.Thread(target=gui_main)
        gui_thread.start()
    
    # Start the threads
    user_check_thread.start()
    time.sleep(15)
    get_stream_link_thread.start()
    run_downloader()


    # Wait for all threads to finish
    get_stream_link_thread.join()
    user_check_thread.join()
    
    if not args.nogui:
        gui_thread.join()
