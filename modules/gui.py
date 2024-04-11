import json
import os
import threading
import requests
import logging
from colorama import Fore, init
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageOps
from io import BytesIO
import tkinter.font as tkFont

# Initialize global variables
image_cache = {}  # Global image cache
lock_file_cache = set()  # Global lock file cache
init(autoreset=True)
ctk.set_appearance_mode("dark")  # Set theme for CustomTkinter
stop_threads = False

script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_dir = os.path.join(script_dir, 'json')
lock_files_dir = os.path.join(script_dir, 'lock_files')

# Function to update lock file cache
def update_lock_file_cache():
    global lock_file_cache
    lock_file_path = 'lock_files'
    if not os.path.exists(lock_file_path):
        os.makedirs(lock_file_path)
    lock_file_cache = {filename.replace('.lock', '') for filename in os.listdir(lock_files_dir) if filename.endswith('.lock')}
    threading.Timer(30, update_lock_file_cache).start()  # Update lock file cache every 30 seconds

update_lock_file_cache()  # Initialize the lock file cache update

def lock_file_exists(username):
    return os.path.exists(os.path.join(lock_files_dir, f'{username}.lock'))

        
def load_image_from_url_async(url, callback, root, size=(50, 50)):
    def thread_target():
        if url in image_cache:
            root.after(0, lambda: callback(image_cache[url]))
        else:
            try:
                response = requests.get(url)
                img = Image.open(BytesIO(response.content))
                img.thumbnail(size)
                mask = Image.new('L', size, 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + size, fill=255)
                img = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
                img.putalpha(mask)
                photo_image = ImageTk.PhotoImage(img)
                image_cache[url] = photo_image
                root.after(0, lambda: callback(photo_image))
            except Exception as e:
                print(f"Error loading image: {e}")
    threading.Thread(target=thread_target).start()
    
    
def set_image(index, img, canvas):
    y_position = index * 80 + 35
    image_id = canvas.create_image(50, y_position, image=img)
    image_references.append(img)


def create_red_square(canvas, root, x, y):
    size = 8
    square_id = canvas.create_rectangle(x - size//2, y - size//2, x + size//2, y + size//2, fill="red", outline="red")
    return square_id


def update_gui(canvas, root, currently_live_label):
    global image_references
    image_references = []

    # Define fonts
    username_font = tkFont.Font(family="Helvetica", size=12, weight="bold")
    recording_font = tkFont.Font(family="Helvetica", size=8)

    # Initialize users as an empty list in case JSON loading fails
    users = []

    try:
        # Adjusted to use the json_dir for the correct path
        live_users_file_path = os.path.join(json_dir, 'live_users.json')
        with open(live_users_file_path, 'r') as file:
            file_content = file.read().strip()
            if file_content:  # Check if the file content is not empty
                users = json.loads(file_content)
            else:
                print("JSON file is empty")
        total_live_users = len(users)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
    except Exception as e:
        print(f"Unexpected error reading live users: {e}")

    # Ensure the lock_file_cache is updated.
    update_lock_file_cache()
    currently_recording_count = len(lock_file_cache)

    # Update the label with current recording and live user counts
    currently_live_label.configure(text=f"Currently Recording: {currently_recording_count}/{total_live_users}")

    canvas.delete("all")
    for index, user in enumerate(users):
        y_position = index * 80
        canvas.create_rectangle(0, y_position, canvas.winfo_width(), y_position + 70, fill="#1c1c1c", outline="")
        canvas.create_text(100, y_position + 35, text=user.get('username', 'N/A'), anchor="w", font=username_font, fill="white")
        if user.get('profile_picture'):
            # Use a lambda to correctly pass the index and img to set_image function
            load_image_from_url_async(user['profile_picture'], lambda img, index=index: set_image(index, img, canvas), root)
        if lock_file_exists(user.get('username', '')):
            text_x = canvas.winfo_width() - 35
            square_x = canvas.winfo_width() - 20
            canvas.create_text(text_x, y_position + 35, text="Recording", anchor="e", font=recording_font, fill="white")
            create_red_square(canvas, root, square_x, y_position + 35)

    canvas.config(scrollregion=canvas.bbox("all"))
    root.after(5000, lambda: update_gui(canvas, root, currently_live_label))

def on_mousewheel(event, canvas):
    canvas.yview_scroll(int(-1*(event.delta/120)), "units")

def run_gui():
    global stop_threads

    root = ctk.CTk()
    root.title("TTAutoRecord v4.1.0")
    root.geometry("500x800")

    canvas = tk.Canvas(root, bg="black", highlightthickness=0)
    
    top_frame = ctk.CTkFrame(root, fg_color="black")
    top_frame.pack(side="top", fill="x")

    # Create and pack the label inside the frame
    currently_live_label = ctk.CTkLabel(top_frame, text="Currently Recording: 0/0", fg_color="black", bg_color="black", font=("Helvetica", 18, "bold"), anchor="w")
    currently_live_label.pack(side="left", anchor="nw" , padx=10, pady=1)
    
    scrollbar = ctk.CTkScrollbar(root, command=canvas.yview, fg_color="gray", bg_color="black")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    canvas.bind_all("<MouseWheel>", lambda event: on_mousewheel(event, canvas))
    
    # Pass the label as an argument to update_gui
    root.after(1000, update_gui, canvas, root, currently_live_label)

    def on_closing():
        global stop_threads
        stop_threads = True
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
    
def main():
    run_gui()
    
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Script execution stopped by user.")
    except Exception as e:
        logging.critical(f"Critical error, stopping script: {e}")