import os
import platform
import sys
from pathlib import Path
from tkinter import messagebox, simpledialog
from dotenv import load_dotenv

class APIKeyManager:
    """Class to handle API key management operations."""

    @staticmethod
    def get_env_file_path():
        """
        Resolve the main .env file location.

        In development this points to the project root (next to text-to-mic.py).
        In a bundled build it points next to the generated executable.
        """
        return Path(sys.argv[0]).resolve().parent / ".env"
    
    @staticmethod
    def get_app_support_path_mac():
        """Get the application support path for macOS."""
        home = Path.home()
        app_support_path = home / 'Library' / 'Application Support' / 'scorchsoft-text-to-mic'
        app_support_path.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        return app_support_path
    
    @staticmethod
    def save_api_key_mac(api_key):
        """Save the API key using the shared root .env path on macOS."""
        return APIKeyManager.save_api_key(api_key)
    
    @staticmethod
    def save_api_key(api_key):
        """Save the API key to the root .env file."""
        try:
            env_path = APIKeyManager.get_env_file_path()
            env_path.parent.mkdir(parents=True, exist_ok=True)
            with open(env_path, 'w') as f:
                f.write(f"OPENAI_API_KEY={api_key}\n")

            # Reload environment to include the new API key
            load_dotenv(dotenv_path=env_path, override=True)
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save API key: {str(e)}")
            return False
    
    @staticmethod
    def load_api_key_mac():
        """Load the API key from the shared root .env path on macOS."""
        env_path = APIKeyManager.get_env_file_path()
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('OPENAI_API_KEY'):
                        return line.strip().split('=')[1]
        return None
    
    @staticmethod
    def get_api_key(parent=None):
        """Get the API key from environment variables or local file, or prompt the user."""
        # First, try to load the API key from environment variables or local file
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:  # Check for macOS and use the macOS-specific method
            if platform.system() == 'Darwin':  # Darwin is the system name for macOS
                api_key = APIKeyManager.load_api_key_mac()
            
            # If no API key is found, prompt the user
            if not api_key and parent:
                # Check if this is a first-time run by checking for settings file
                settings_file = Path(parent.get_settings_file_path("settings.json"))
                first_time_run = not settings_file.exists()
                
                # Don't show instructions automatically
                # parent.show_instructions()  # Show the "How to Use" modal after setting the key
                
                response = messagebox.askyesno(
                    "API Key Required",
                    "An OpenAI API Key is required for full functionality, such as speech to text and OpenAI voices.\n\n"
                    "Without an API key, you can still use basic system voices with text to speech.\n\n"
                    "Would you like to enter an API key now?",
                    parent=parent
                )
                
                if response:
                    # Show instructions only when user wants to add an API key
                    if first_time_run:
                        parent.show_instructions()
                        
                    if hasattr(parent, "prompt_string_modal"):
                        api_key = parent.prompt_string_modal(
                            "API Key",
                            "Enter your OpenAI API Key:",
                            mask_input=True
                        )
                    else:
                        api_key = simpledialog.askstring("API Key", "Enter your OpenAI API Key:", parent=parent)
                    if api_key:
                        try:
                            if platform.system() == 'Darwin':
                                APIKeyManager.save_api_key_mac(api_key)
                            else:
                                APIKeyManager.save_api_key(api_key)
                            
                            # Check if this is the first time setting the key
                            if first_time_run:
                                messagebox.showinfo(
                                    "API Key Set - Restarting",
                                    "The OpenAI API Key has been saved. The application will now restart to apply changes."
                                )
                                # Schedule a restart after the message dialog is closed
                                parent.after(200, lambda: APIKeyManager.restart_application(parent))
                            else:
                                messagebox.showinfo("API Key Set", "The OpenAI API Key has been updated successfully.")
                        except Exception as e:
                            messagebox.showerror("Error", f"Failed to save API key: {str(e)}")
                else:
                    messagebox.showinfo(
                        "Limited Functionality",
                        "You are using the basic version with system voices only.\n\n"
                        "To access OpenAI voices and other features, you can add an API key later in Settings."
                    )
        
        return api_key
    
    @staticmethod
    def change_api_key(parent):
        """Change the API key."""
        if hasattr(parent, "prompt_string_modal"):
            new_key = parent.prompt_string_modal(
                "API Key",
                "Enter new OpenAI API Key:",
                mask_input=True
            )
        else:
            new_key = simpledialog.askstring("API Key", "Enter new OpenAI API Key:", parent=parent)
        if new_key:
            success = APIKeyManager.save_api_key(new_key)
            if success:
                # Check if the first time adding a key (no existing key)
                is_first_key = not parent.has_api_key
                
                if is_first_key:
                    messagebox.showinfo(
                        "API Key Set - Restarting",
                        "The OpenAI API Key has been saved. The application will now restart to apply changes."
                    )
                    # Schedule a restart after the message dialog is closed
                    parent.after(200, lambda: APIKeyManager.restart_application(parent))
                else:
                    messagebox.showinfo("API Key Updated", "The OpenAI API Key has been updated successfully.")
                
                return new_key
        return None
    
    @staticmethod
    def restart_application(root):
        """Restart the application."""
        # Destroy the current instance
        root.destroy()
        
        # Restart the application
        python = sys.executable
        os.execl(python, python, *sys.argv) 
