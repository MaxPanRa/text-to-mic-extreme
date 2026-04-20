import tkinter as tk
import platform
import os
import threading
import ctypes
import pyaudio
import wave
import webbrowser
import json
import sys
import time
import re
import requests
import pyttsx3
import tempfile
import base64

from pystray import Icon as icon, MenuItem as item, Menu as menu
from PIL import Image, ImageDraw, ImageTk
from tkinter import ttk, messagebox, Menu, Frame, Canvas, Scrollbar
import customtkinter as ctk
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from pydub import AudioSegment

# Import our refactored classes
from utils.api_key_manager import APIKeyManager
from utils.hotkey_manager import HotkeyManager
from utils.resource_utils import ResourceUtils
from utils.tone_presets_manager import TonePresetsManager
from utils.presets_manager import PresetsManager
from utils.ai_editor_manager import AIEditorManager
from utils.settings_manager import SettingsManager
from utils.app_text import AppText
from utils.version_checker import VersionChecker

def load_env_file():
    env_path = APIKeyManager.get_env_file_path()
    load_dotenv(dotenv_path=env_path, override=True)

class TextToMic(tk.Tk):

    def __init__(self):
        super().__init__()

        self.version = "1.4.1"
        self.title(f"Text to Mic by Scorchsoft.com - v{self.version}")
        
        # Add these lines to set up the window icon
        icon_path = self.resource_path("assets/logo-circle-32.png")
        self.iconphoto(False, tk.PhotoImage(file=icon_path))
        
        # For Windows compatibility, also set the iconbitmap
        try:
            self.iconbitmap(self.resource_path("assets/icon.ico"))
        except:
            # This might fail on Mac, which is fine as we have iconphoto as backup
            pass
        
        # Fixed window dimensions for all states - DEFINED ONCE as class constants
        # These are the ONLY values that should be used throughout the application
        self.BASE_WIDTH = 860
        self.BASE_HEIGHT_WITH_BANNER = 970
        self.BASE_HEIGHT_NO_BANNER = 800
        self.COLLAPSED_HEIGHT_WITH_BANNER = 700
        self.COLLAPSED_HEIGHT_NO_BANNER = 582
        self.COMPACT_WIDTH = 1120
        self.COMPACT_HEIGHT = 60
        
        # Initial window geometry - start with base size
        self.geometry(f"{self.BASE_WIDTH}x{self.BASE_HEIGHT_WITH_BANNER}")
        
        # Center the window immediately before any popups appear
        self.center_window()
        
        # Withdraw window temporarily to prevent flashing before everything is ready
        self.withdraw()
        
        # Initialize system TTS engine
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 150)
        self.system_voices = self.engine.getProperty('voices')

        self.available_models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo"]
        self.default_model = "gpt-4o-mini"
        self.available_speech_models = [
            ("4o Mini TTS", "gpt-4o-mini-tts"),
            ("TTS-1 HD", "tts-1-hd"),
            ("Audio 1.5", "gpt-audio-1.5")
        ]
        self.default_speech_model = "gpt-4o-mini-tts"
        self.voice_descriptors = {
            "alloy": "neutra",
            "ash": "grave",
            "ballad": "expresiva",
            "cedar": "mas grave",
            "coral": "brillante",
            "echo": "firme",
            "fable": "narrador",
            "marin": "suave",
            "nova": "clara",
            "onyx": "grave",
            "sage": "calmada",
            "shimmer": "ligera",
            "verse": "robusta",
        }

        # Cache for icons - will store loaded and resized icon images
        self.icon_cache = {}
        self.normal_bg_color = "#f5f5f7"
        self.compact_bg_color = "#1c2f45"

        self.style = ttk.Style(self)
        if self.tk.call('tk', 'windowingsystem') == 'aqua':
            self.style.theme_use('aqua')
            self.style.configure('CompactDark.TFrame', background=self.compact_bg_color)
            self.configure(background=self.normal_bg_color)
        else:
            # Create a custom theme instead of using 'clam'
            self.style.theme_use('clam')
            
            # Define a modern color scheme with clean light greys
            bg_color = self.normal_bg_color  # Very light grey background
            accent_color = "#e0e0e4"   # Slightly darker grey for accents
            text_color = "#333333"     # Dark grey for text
            button_bg = "#e8e8ec"      # Light grey for buttons
            
            # Configure default styles for various widgets
            self.style.configure('TFrame', background=bg_color)
            self.style.configure('CompactDark.TFrame', background=self.compact_bg_color)
            self.style.configure('TLabel', background=bg_color, foreground=text_color)
            self.style.configure('TButton', background=button_bg, foreground=text_color)
            self.style.configure('TCheckbutton', background=bg_color, foreground=text_color)
            self.style.configure('TRadiobutton', background=bg_color, foreground=text_color)
            self.style.configure('TMenubutton', background=button_bg, foreground=text_color)
            self.style.configure('TEntry', fieldbackground=bg_color, foreground=text_color)
            self.style.configure('TCombobox', fieldbackground=bg_color, foreground=text_color)
            
            # Override the background color of the main window
            self.configure(background=bg_color)

        #Define styles
        self.style.configure('Recording.TButton', background='red', foreground='white')
        self.style.configure("Green.TButton", background="green", foreground="white")

        # Ensure that the config directory exists
        self.ensure_config_directory()
        load_env_file()

        # Get API key using APIKeyManager
        self.api_key = APIKeyManager.get_api_key(self)
        self.has_api_key = bool(self.api_key)
        
        if self.has_api_key:
            self.client = OpenAI(api_key=self.api_key)
        
        # Initializing device index variables before they are used
        self.device_index = tk.StringVar(self)
        self.device_index_2 = tk.StringVar(self)

        self.available_devices = self.get_audio_devices()  # Load audio devices
        self.available_input_devices = self.get_input_devices() # Load input devices

        # Load tone presets
        self.tone_presets = TonePresetsManager.load_tone_presets(self)
        self.current_tone_name = self.load_current_tone_from_settings()
        
        # Initialize settings before creating menu
        settings = self.load_settings()
        self.banner_var = tk.BooleanVar()
        self.banner_var.set(settings.get("hide_banner", False))
        self.always_on_top_var = tk.BooleanVar(value=settings.get("always_on_top", False))
        self.compact_mode_var = tk.BooleanVar(value=settings.get("compact_mode", False))
        self.window_opacity = tk.DoubleVar(value=float(settings.get("window_opacity", 1.0)))
        self.send_with_ctrl_enter_var = tk.BooleanVar(value=settings.get("send_with_ctrl_enter", False))
        self.speech_model_var = tk.StringVar(
            value=self.get_speech_model_label(settings.get("speech_model", self.default_speech_model))
        )
        self.tone_intensity_var = tk.StringVar(value=(settings.get("tone_intensity", "strong") or "strong").lower())
        
        # Initialize auto_check_version before creating menu
        self.auto_check_version = tk.BooleanVar(value=settings.get("auto_check_version", True))
        
        # Create the presets manager before initializing the GUI
        self.presets_manager = PresetsManager(self)
        
        # Create the AI Editor Manager
        self.ai_editor = AIEditorManager(self)
        
        # Store reference to presets state 
        self.presets_collapsed = self.presets_manager.presets_collapsed

        # Initialize the main frame as a class variable for version notification to work
        self.main_frame = None

        # Create menu and initialize GUI after presets manager is created
        self.create_menu()
        self.initialize_gui()
        
        # Initialize our HotkeyManager
        self.hotkey_manager = HotkeyManager(self)
        
        # Initialize version checker
        self.version_checker = VersionChecker(self, self.version)
        
        # If banner should be hidden based on settings, hide it now
        if self.banner_var.get():
            self.toggle_banner()

        self.apply_always_on_top()
        self.apply_window_opacity()
        self.apply_compact_mode_layout()
             
        # Center the window on the screen
        self.center_window()
            
        # Schedule version check after app is fully loaded
        # Only check automatically if the setting is enabled
        if self.auto_check_version.get():
            # Delay the check to ensure UI is fully loaded
            self.after(2000, self.version_checker.check_version, False)

        # At the end of __init__, after all initialization:
        # Make the window visible again, now properly centered and with all elements loaded
        self.deiconify()

        # Set initial window height based on banner and presets state
        self.update_window_size()

        if self.compact_mode_var.get():
            self.focus_text_input()

    def center_window(self):
        """Center the window on the screen."""
        self.update_idletasks()  # Update window size info
        
        # Get screen width and height
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Get window width and height
        window_width = self.winfo_width()
        window_height = self.winfo_height()
        
        # Calculate position coordinates
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        # Set the position
        self.geometry(f"+{x}+{y}")

    def position_window_bottom_center(self, bottom_margin=72):
        """Place the window centered horizontally near the bottom of the screen."""
        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = self.winfo_width()
        window_height = self.winfo_height()

        x = (screen_width - window_width) // 2
        y = max(0, screen_height - window_height - bottom_margin)

        self.geometry(f"+{x}+{y}")

    def ensure_config_directory(self):
        """Ensure the config directory exists."""
        config_dir = Path("config")
        config_dir.mkdir(parents=True, exist_ok=True)

    def show_version(self):
        instruction_window = tk.Toplevel(self)
        instruction_window.title("App Version")
        instruction_window.geometry("300x150")  # Width x Height

        instructions = f"""Version {self.version}\n\n App by Scorchsoft.com"""
        
        tk.Label(instruction_window, text=instructions, justify=tk.LEFT, wraplength=280).pack(padx=10, pady=10)
        
        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def create_menu(self):
        self.menubar = Menu(self)
        self.config(menu=self.menubar)

        # Get current hotkey settings
        settings = self.load_settings()
        hotkey_manager = self.hotkey_manager if hasattr(self, 'hotkey_manager') else None
        
        # Format hotkeys for display in menus
        if hotkey_manager:
            replay_shortcut = hotkey_manager.format_shortcut(settings["hotkeys"]["play_last_audio"])
            record_shortcut = hotkey_manager.format_shortcut(settings["hotkeys"]["record_start_stop"])
            stop_shortcut = hotkey_manager.format_shortcut(settings["hotkeys"]["stop_recording"])
            cancel_shortcut = hotkey_manager.format_shortcut(settings["hotkeys"]["cancel_operation"])
            focus_writer_shortcut = hotkey_manager.format_shortcut(settings["hotkeys"].get("focus_writer", ["ctrl", "shift", "7"]))
        else:
            # Default values if hotkey_manager isn't available
            replay_shortcut = "Ctrl+Shift+8"
            record_shortcut = "Ctrl+Shift+0"
            stop_shortcut = "Ctrl+Shift+9"
            cancel_shortcut = "Ctrl+Shift+1"
            focus_writer_shortcut = "Ctrl+Shift+7"

        # File or settings menu
        settings_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="API Key", command=self.change_api_key)
        settings_menu.add_command(label="AI Copyediting", command=self.show_ai_editor_settings)
        settings_menu.add_command(label="Keyboard Shortcuts", command=self.show_hotkey_settings)  
        settings_menu.add_command(label="Manage Tones", command=self.show_tone_presets_manager)
        settings_menu.add_command(label="Generate Tone with AI", command=self.generate_tone_preset_with_ai)
        settings_menu.add_command(label="Window Opacity", command=self.show_window_opacity_settings)
        speech_model_menu = Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Speech Model", menu=speech_model_menu)
        for label, _model_id in self.available_speech_models:
            speech_model_menu.add_radiobutton(
                label=label,
                value=label,
                variable=self.speech_model_var,
                command=self.set_speech_model_from_menu
            )
        tone_intensity_menu = Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Tone Intensity", menu=tone_intensity_menu)
        tone_intensity_menu.add_radiobutton(label="Mild", value="mild", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        tone_intensity_menu.add_radiobutton(label="Strong", value="strong", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        tone_intensity_menu.add_radiobutton(label="Extreme", value="extreme", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        settings_menu.add_separator()
        
        # Add presets toggle with checkbox
        self.presets_visible_var = tk.BooleanVar(value=not self.presets_collapsed)
        settings_menu.add_checkbutton(label="Show Presets", variable=self.presets_visible_var, command=self.toggle_presets_from_menu)
        
        settings_menu.add_checkbutton(label="Auto Check for Updates", variable=self.auto_check_version, command=self.toggle_auto_version_check)
        settings_menu.add_checkbutton(label="Always on Top", variable=self.always_on_top_var, command=self.toggle_always_on_top)
        settings_menu.add_checkbutton(label="Compact Writing Mode", variable=self.compact_mode_var, command=self.toggle_compact_mode)
        settings_menu.add_checkbutton(label="Send with Ctrl+Enter", variable=self.send_with_ctrl_enter_var, command=self.toggle_send_with_ctrl_enter)
        settings_menu.add_checkbutton(label="Hide Scorchsoft Banner", variable=self.banner_var, command=self.toggle_banner)

        # Playback menu
        playback_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Actions", menu=playback_menu)
        
        # Add keyboard shortcuts to menu items
        playback_menu.add_command(label=f"Replay [{replay_shortcut}]", command=self.play_last_audio)
        playback_menu.add_command(label="Apply AI Copyedit", command=self.apply_ai_to_input)
        playback_menu.add_command(label=f"Focus Writer [{focus_writer_shortcut}]", command=self.show_writer_overlay)
        playback_menu.add_separator()
        playback_menu.add_command(label=f"Start/Stop Recording [{record_shortcut}]", command=self.handle_record_button_click)
        playback_menu.add_command(label=f"Stop Recording [{stop_shortcut}]", command=lambda: self.stop_recording(auto_play=False))
        playback_menu.add_command(label=f"Cancel Operation [{cancel_shortcut}]", command=self.stop_playback)

        # Help menu
        help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Check Version", command=self.check_version)
        help_menu.add_command(label="How to Use", command=self.show_instructions)
        help_menu.add_command(label="Terms of Use and Licence", command=self.show_terms_of_use)

        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Play", command=self.handle_submit_button_click)
        self.context_menu.add_command(label="Replay", command=self.play_last_audio)
        self.context_menu.add_command(label="Focus Writer", command=self.show_writer_overlay)
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(label="Always on Top", variable=self.always_on_top_var, command=self.toggle_always_on_top)
        self.context_menu.add_checkbutton(label="Compact Writing Mode", variable=self.compact_mode_var, command=self.toggle_compact_mode)
        self.context_menu.add_checkbutton(label="Send with Ctrl+Enter", variable=self.send_with_ctrl_enter_var, command=self.toggle_send_with_ctrl_enter)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Window Opacity", command=self.show_window_opacity_settings)
        context_speech_model_menu = Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label="Speech Model", menu=context_speech_model_menu)
        for label, _model_id in self.available_speech_models:
            context_speech_model_menu.add_radiobutton(
                label=label,
                value=label,
                variable=self.speech_model_var,
                command=self.set_speech_model_from_menu
            )
        context_tone_intensity_menu = Menu(self.context_menu, tearoff=0)
        self.context_menu.add_cascade(label="Tone Intensity", menu=context_tone_intensity_menu)
        context_tone_intensity_menu.add_radiobutton(label="Mild", value="mild", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        context_tone_intensity_menu.add_radiobutton(label="Strong", value="strong", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        context_tone_intensity_menu.add_radiobutton(label="Extreme", value="extreme", variable=self.tone_intensity_var, command=self.set_tone_intensity)
        self.context_menu.add_command(label="Generate Tone with AI", command=self.generate_tone_preset_with_ai)
        self.context_menu.add_command(label="API Key", command=self.change_api_key)
        self.context_menu.add_command(label="AI Copyediting", command=self.show_ai_editor_settings)
        self.context_menu.add_command(label="Keyboard Shortcuts", command=self.show_hotkey_settings)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Center Window", command=self.center_window)
        self.context_menu.add_command(label="Exit", command=self.destroy)

    def show_hotkey_settings(self):
        """Show the hotkey settings dialog."""
        HotkeyManager.hotkey_settings_dialog(self)

    def change_api_key(self):
        """Change the API key using APIKeyManager."""
        new_key = APIKeyManager.change_api_key(self)
        if new_key:
            self.api_key = new_key
            self.has_api_key = True
            self.client = OpenAI(api_key=self.api_key)
            self.on_speech_model_change()
            self.update_buttons_for_playback(False)

    def prompt_string_modal(self, title, prompt, initial_value="", mask_input=False, width=480):
        """Show a small custom input dialog that works in compact borderless mode."""
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(background="#f5f5f7")

        try:
            dialog.attributes("-topmost", True)
        except tk.TclError:
            pass

        result = {"value": None}

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=prompt, justify=tk.LEFT, wraplength=width - 40).pack(anchor=tk.W, pady=(0, 10))

        entry_var = tk.StringVar(value=initial_value)
        entry = tk.Entry(
            frame,
            textvariable=entry_var,
            width=60,
            show="*" if mask_input else ""
        )
        entry.pack(fill=tk.X, expand=True)
        entry.icursor(tk.END)
        entry.selection_range(0, tk.END)

        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(14, 0))

        def submit():
            result["value"] = entry_var.get().strip()
            dialog.destroy()

        def cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="OK", command=submit).pack(side=tk.RIGHT, padx=(0, 8))

        entry.bind("<Return>", lambda event: submit())
        dialog.bind("<Escape>", lambda event: cancel())

        dialog.update_idletasks()
        dialog_width = max(width, dialog.winfo_reqwidth())
        dialog_height = dialog.winfo_reqheight()
        position_x = self.winfo_x() + max(0, (self.winfo_width() - dialog_width) // 2)
        position_y = self.winfo_y() + max(20, (self.winfo_height() - dialog_height) // 2)
        dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

        dialog.deiconify()
        dialog.lift()
        entry.focus_force()
        dialog.wait_window()

        return result["value"]

    def get_audio_file_path(self, filename):
        if platform.system() == 'Darwin':  # Check if the OS is macOS
            mac_path = APIKeyManager.get_app_support_path_mac()
            return f"{mac_path}/{filename}"
        else:
            return Path(filename)  # Default to current directory for non-macOS systems

    def play_sound(self, sound_file):
        """Play a sound file using ResourceUtils."""
        ResourceUtils.play_sound(sound_file)

    def resource_path(self, relative_path):
        """Get the resource path using ResourceUtils."""
        return ResourceUtils.resource_path(relative_path)

    def initialize_gui(self):
        # Get saved settings
        settings = self.load_settings()

        self.input_device_index = tk.StringVar(self)
        self.device_index = tk.StringVar(self)
        self.device_index_2 = tk.StringVar(self)

        # Set default values
        default_input = "Default"
        default_output = "Select Device"
        default_secondary = "None"
        
        # Get saved device names from settings
        saved_input_device = settings.get("input_device", default_input)
        saved_primary_device = settings.get("primary_device", default_output)
        saved_secondary_device = settings.get("secondary_device", default_secondary)
        
        # Validate that saved devices are still available, otherwise use defaults
        if saved_input_device in self.available_input_devices:
            self.input_device_index.set(saved_input_device)
        else:
            self.input_device_index.set(default_input)
        
        if saved_primary_device in self.available_devices:
            self.device_index.set(saved_primary_device)
        else:
            self.device_index.set(default_output)
        
        if saved_secondary_device in self.available_devices or saved_secondary_device == "None":
            self.device_index_2.set(saved_secondary_device)
        else:
            self.device_index_2.set(default_secondary)

        main_frame = ttk.Frame(self, padding="20")
        main_frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Configure columns in main_frame to expand properly
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(2, weight=0)
        main_frame.columnconfigure(3, weight=0)
        
        # Store reference to main_frame for version notification
        self.main_frame = main_frame

        # Use the background color from our style for the text widget
        bg_color = self.style.lookup('TFrame', 'background')
        text_color = self.style.lookup('TLabel', 'foreground')

        # Define custom button styles for pill-shaped buttons
        self.style.configure('Pill.TButton', 
                             font=('Arial', 13, 'bold'),
                             borderwidth=0,
                             relief='flat',
                             padding=(20, 8))
                             
        self.style.configure('RecordPill.TButton', 
                             font=('Arial', 13, 'bold'),
                             background='#d32f2f',
                             foreground='white',
                             borderwidth=0,
                             relief='flat',
                             padding=(20, 8))
                             
        self.style.configure('PlayPill.TButton', 
                             font=('Arial', 13, 'bold'),
                             background='#058705',
                             foreground='white',
                             borderwidth=0,
                             relief='flat',
                             padding=(20, 8))

        # Create frames for better organization
        voice_frame = ttk.Frame(main_frame)
        voice_frame.grid(column=0, row=0, columnspan=2, sticky="ew")
        voice_frame.columnconfigure(0, weight=1)  # Make the first column expandable
        voice_frame.columnconfigure(1, weight=3)  # Make the second column expand more
        self.voice_frame = voice_frame

        device_frame = ttk.Frame(main_frame)
        device_frame.grid(column=0, row=1, columnspan=2, sticky="ew", pady=(10, 0))
        device_frame.columnconfigure(0, weight=1)  # Make the first column expandable
        device_frame.columnconfigure(1, weight=3)  # Make the second column expand more
        self.device_frame = device_frame

        # Set fixed width for dropdown menus
        dropdown_width = 34

        # Create a style for compact dropdowns
        self.style.configure('Compact.TMenubutton', padding=(8, 4))

        # Voice and Tone Settings
        ttk.Label(voice_frame, text="Voice Settings", font=("Arial", 10, "bold")).grid(column=0, row=0, sticky=tk.W, pady=(0, 10), columnspan=2)

        # Make sure voice_frame columns expand properly
        voice_frame.columnconfigure(1, weight=1)
        
        # Set fixed width for all labels
        label_width = 31  # Keep labels aligned while freeing more width for controls
        
        # Initialize voice selection
        selected_speech_model = settings.get("speech_model", self.default_speech_model)
        self.available_voices = self.get_available_voices(selected_speech_model)
        
        # Determine default voice based on whether API key is available
        default_voice = self.get_default_voice_for_model(selected_speech_model) if self.has_api_key else self.available_voices[0] if self.available_voices else "[System] Default"
        
        self.voice_var = tk.StringVar(value=default_voice)
        
        voice_label = ttk.Label(voice_frame, text="Voice:", width=label_width)
        voice_label.grid(column=0, row=1, sticky=tk.W, pady=(0, 5))
        self.voice_menu = ttk.OptionMenu(voice_frame, self.voice_var, self.voice_var.get(), *self.available_voices, command=self.on_voice_change)
        self.voice_menu.grid(column=1, row=1, sticky="ew", pady=(0, 5))
        self.voice_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        speech_model_label = ttk.Label(voice_frame, text="Speech Model:", width=label_width)
        speech_model_label.grid(column=0, row=2, sticky=tk.W, pady=(0, 5))
        self.speech_model_menu = ttk.OptionMenu(
            voice_frame,
            self.speech_model_var,
            self.speech_model_var.get(),
            *self.get_speech_model_labels(),
            command=self.on_speech_model_change
        )
        self.speech_model_menu.grid(column=1, row=2, sticky="ew", pady=(0, 5))
        self.speech_model_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        # Tone selection with warning for basic version
        self.tone_var = tk.StringVar(value=self.current_tone_name)
        tone_options = ["None"] + list(self.tone_presets.keys())
        tone_label = ttk.Label(voice_frame, text="Tone Preset:", width=label_width)
        tone_label.grid(column=0, row=3, sticky=tk.W, pady=(0, 5))
        self.tone_menu = ttk.OptionMenu(voice_frame, self.tone_var, self.tone_var.get(), *tone_options, command=self.on_tone_change)
        self.tone_menu.grid(column=1, row=3, sticky="ew", pady=(0, 5))
        self.tone_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        self.speech_model_hint_label = ttk.Label(
            voice_frame,
            text="",
            foreground="#666666",
            font=("Arial", 8, "italic"),
            wraplength=430
        )
        self.speech_model_hint_label.grid(column=0, row=4, columnspan=2, sticky=tk.W, pady=(4, 0))
        
        # Check if we should disable tone menu based on voice type
        if self.voice_var.get().startswith("[System]"):
            self.tone_menu.state(['disabled'])
            self.tone_var.set("None")
        
        # Add warning label for basic version
        if not self.has_api_key:
            warning_label = ttk.Label(voice_frame, 
                                    text="⚠️ Basic Version - Add API Key in Settings for full features", 
                                    foreground="orange",
                                    font=("Arial", 8, "italic"))
            warning_label.grid(column=0, row=5, columnspan=2, sticky=tk.W, pady=(5, 0))

        # Separator between Voice Settings and Device Settings
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(column=0, row=2, columnspan=2, sticky="ew", pady=10)
        self.main_separator = separator

        # Device Settings
        ttk.Label(device_frame, text="Device Settings", font=("Arial", 10, "bold")).grid(column=0, row=0, sticky=tk.W, pady=(0, 10), columnspan=2)

        input_label = ttk.Label(device_frame, text="Input Device (optional):", width=label_width)
        input_label.grid(column=0, row=1, sticky=tk.W, pady=(0, 5))
        input_device_menu = ttk.OptionMenu(device_frame, self.input_device_index, self.input_device_index.get(), 
                                          *self.available_input_devices.keys(), 
                                          command=self.on_input_device_change)
        input_device_menu.grid(column=1, row=1, sticky="ew", pady=(0, 5))
        input_device_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        primary_label = ttk.Label(device_frame, text="Primary Playback Device:", width=label_width)
        primary_label.grid(column=0, row=2, sticky=tk.W, pady=(0, 5))
        primary_device_menu = ttk.OptionMenu(device_frame, self.device_index, self.device_index.get(), 
                                            *self.available_devices.keys(),
                                            command=self.on_primary_device_change)
        primary_device_menu.grid(column=1, row=2, sticky="ew", pady=(0, 5))
        primary_device_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        secondary_label = ttk.Label(device_frame, text="Secondary Playback Device (optional):", width=label_width)
        secondary_label.grid(column=0, row=3, sticky=tk.W, pady=(0, 5))
        secondary_device_menu = ttk.OptionMenu(device_frame, self.device_index_2, self.device_index_2.get(), 
                                              "None", *self.available_devices.keys(),
                                              command=self.on_secondary_device_change)
        secondary_device_menu.grid(column=1, row=3, sticky="ew", pady=(0, 5))
        secondary_device_menu.config(width=dropdown_width, style='Compact.TMenubutton')

        # Make sure device_frame columns expand properly
        device_frame.columnconfigure(1, weight=1)

        # Text to Read section with proper layout
        text_read_frame = ttk.Frame(main_frame)
        text_read_frame.grid(column=0, row=4, columnspan=2, sticky="ew", pady=(10, 0))
        text_read_frame.columnconfigure(0, weight=1)  # Left side expands
        text_read_frame.columnconfigure(1, weight=0)  # Right side fixed width
        self.text_read_frame = text_read_frame

        # Make sure text_read_frame columns expand properly
        text_read_frame.columnconfigure(0, weight=1)

        # Text to Read label - Updated to match other section titles
        ttk.Label(text_read_frame, text="Text to Read", font=("Arial", 10, "bold")).grid(column=0, row=0, sticky=tk.W, pady=(0, 10))

        # Create a frame to contain the dropdown and save button
        save_frame = ttk.Frame(text_read_frame)
        save_frame.grid(column=1, row=0, sticky=tk.E)
        self.save_frame = save_frame

        # Create a compact style for the button
        self.style.configure('Compact.TButton', padding=(2, 1))
        save_as_preset_button = ttk.Button(save_frame, text="Save As Preset", width=15, style='Compact.TButton', command=self.show_save_preset_dialog)
        save_as_preset_button.grid(column=0, row=0, sticky=tk.E)

        # Text input area with proper spacing
        self.text_input = tk.Text(main_frame, height=6, width=78)
        # Use white background for text input instead of the system background color
        text_color = self.style.lookup('TLabel', 'foreground')
        self.text_input.configure(bg="white", fg=text_color, insertbackground=text_color, wrap=tk.WORD, font=("Arial", 10))
        self.text_input.grid(column=0, row=5, columnspan=6, pady=(0, 20), sticky="nsew")  # Proper spacing
        self.text_input.bind("<Return>", self.handle_text_input_return)
        self.text_input.bind("<KP_Enter>", self.handle_text_input_return)

        # Add a status frame at the bottom of the text input with white background
        status_frame = ttk.Frame(main_frame, style='White.TFrame')
        status_frame.grid(column=0, row=5, columnspan=2, sticky=(tk.S, tk.E), pady=(0, 25), padx=(0, 5))  # Add right padding to shift the frame inward
        self.status_frame = status_frame
        
        # Create a custom style for the white frame
        self.style.configure('White.TFrame', background='white')
        
        # Status indicator showing if editing is enabled
        status_text = "AI Copyediting Disabled"
        if settings.get("chat_gpt_completion", False):
            if settings.get("auto_apply_ai_to_recording", False):
                status_text = f"AI Copyediting Enabled (Auto) - {settings.get('model', self.default_model)}"
            else:
                status_text = f"AI Copyediting Enabled (Manual) - {settings.get('model', self.default_model)}"
        
        self.editing_status = ttk.Label(status_frame, text=status_text, foreground="#888888", font=("Arial", 8, "italic"), background="white")
        self.editing_status.pack(side=tk.RIGHT, padx=5)

        # Create a frame for the buttons to allow for better styling
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(column=0, row=6, columnspan=2, sticky="ew", pady=(0, 20))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=0)
        self.button_frame = button_frame

        # Get keyboard shortcuts from settings
        settings = self.load_settings()
        record_shortcut = "+".join(filter(None, settings["hotkeys"]["record_start_stop"]))
        play_shortcut = "+".join(filter(None, settings["hotkeys"]["play_last_audio"]))

        # Button configuration
        self.recording = False  # State to check if currently recording
        self.is_playing = False  # State to check if audio is playing
        self.idle_record_button_color = "#d9dee7"
        self.idle_record_text_color = "#111111"
        
        # Create CTk buttons with proper rounded corners
        button_height = 38
        button_width = 260
        
        # Record button with CTkButton
        self.record_button = ctk.CTkButton(
            button_frame,
            text=f"Record Mic ({record_shortcut})",
            corner_radius=20,
            height=button_height,
            width=button_width,
            fg_color=self.idle_record_button_color,
            text_color=self.idle_record_text_color,
            hover_color="#cfd6e1",
            font=("Arial", 13, "bold"),
            command=self.handle_record_button_click
        )
        self.record_button.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.play_controls_frame = ttk.Frame(button_frame)
        self.play_controls_frame.grid(row=0, column=1, sticky="ew")
        self.play_controls_frame.columnconfigure(2, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.quick_tone_menu = ttk.OptionMenu(
            self.play_controls_frame,
            self.tone_var,
            self.tone_var.get(),
            *tone_options,
            command=self.on_tone_change
        )
        self.quick_tone_menu.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.quick_tone_menu.config(width=16, style='Compact.TMenubutton')

        # Play button with CTkButton
        self.submit_button = ctk.CTkButton(
            self.play_controls_frame,
            text=f"Play Audio ({play_shortcut})",
            corner_radius=20,
            height=button_height,
            width=button_width,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=self.handle_submit_button_click
        )
        self.submit_button.grid(row=0, column=2, sticky="ew")

        self.compact_speech_model_menu = ttk.OptionMenu(
            main_frame,
            self.speech_model_var,
            self.speech_model_var.get(),
            *self.get_speech_model_labels(),
            command=self.on_speech_model_change
        )
        self.compact_speech_model_menu.grid(row=5, column=1, sticky="e", padx=(0, 8), pady=(0, 0))
        self.compact_speech_model_menu.config(width=10, style='Compact.TMenubutton')
        self.compact_speech_model_menu.grid_remove()

        self.compact_tone_menu = ttk.OptionMenu(
            main_frame,
            self.tone_var,
            self.tone_var.get(),
            *tone_options,
            command=self.on_tone_change
        )
        self.compact_tone_menu.grid(row=5, column=2, sticky="e", padx=(0, 8), pady=(0, 0))
        self.compact_tone_menu.config(width=12, style='Compact.TMenubutton')
        self.compact_tone_menu.grid_remove()

        self.compact_submit_button = ctk.CTkButton(
            main_frame,
            text="Play",
            corner_radius=16,
            height=38,
            width=110,
            bg_color=self.compact_bg_color,
            fg_color="#058705",
            font=("Arial", 13, "bold"),
            command=self.handle_submit_button_click
        )
        self.compact_submit_button.grid(row=5, column=3, sticky="e", padx=(8, 0), pady=(0, 0))
        self.compact_submit_button.grid_remove()
        self.update_speech_model_selection()
        self.update_voice_selection()
        self.update_speech_model_hint()
        self.on_voice_change()

        #Credits
        # Banner image that links to Scorchsoft
        self.banner_frame = ttk.Frame(main_frame)
        self.banner_frame.grid(column=0, row=7, columnspan=2, pady=(10, 0))
        
        banner_path = self.resource_path("assets/ss-banner-550.png")
        try:
            banner_img = tk.PhotoImage(file=banner_path)
            banner_label = tk.Label(self.banner_frame, image=banner_img, cursor="hand2")
            banner_label.image = banner_img  # Keep a reference to prevent garbage collection
            banner_label.pack()
            banner_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        except Exception as e:
            print(f"Error loading banner image: {e}")
            # Fallback to text if image fails to load
            info_label = tk.Label(self.banner_frame, text="Visit Scorchsoft.com for custom app development", 
                               fg="blue", cursor="hand2")
            info_label.pack()
            info_label.bind("<Button-1>", lambda e: self.open_scorchsoft())
        
        # If the banner should be hidden based on settings, hide it now
        if self.banner_var.get():
            self.toggle_banner()

        self.bind_context_menu_targets()
        self.bind_compact_window_controls()

    def open_scorchsoft(self, event=None):
        webbrowser.open('https://www.scorchsoft.com')

    def bind_context_menu_targets(self):
        """Bind right-click context menu to the main compact-mode surfaces."""
        targets = [self, self.main_frame]
        for optional_widget in [
            getattr(self, 'text_input', None),
            getattr(self, 'compact_speech_model_menu', None),
            getattr(self, 'compact_submit_button', None),
            getattr(self, 'submit_button', None)
        ]:
            if optional_widget is not None:
                targets.append(optional_widget)

        for target in targets:
            if target is not None:
                target.bind("<Button-3>", self.show_context_menu)

    def bind_compact_window_controls(self):
        """Allow moving the borderless compact window and restoring with Escape."""
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self.bind("<Escape>", self.handle_escape_key)
        self.main_frame.bind("<ButtonPress-1>", self.start_window_drag)
        self.main_frame.bind("<B1-Motion>", self.perform_window_drag)

    def show_context_menu(self, event):
        """Show the compact-mode context menu."""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def start_window_drag(self, event):
        """Store the current mouse offset for dragging the borderless compact window."""
        if not self.compact_mode_var.get():
            return
        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def perform_window_drag(self, event):
        """Move the borderless compact window while dragging."""
        if not self.compact_mode_var.get():
            return
        new_x = event.x_root - self._drag_offset_x
        new_y = event.y_root - self._drag_offset_y
        self.geometry(f"+{new_x}+{new_y}")

    def handle_escape_key(self, event=None):
        """Exit compact mode quickly when using the borderless overlay."""
        if self.compact_mode_var.get():
            self.compact_mode_var.set(False)
            self.toggle_compact_mode()
            return "break"
        return None

    def handle_text_input_return(self, event=None):
        """Use Enter or Ctrl+Enter to speak, depending on settings."""
        shift_pressed = bool(event and (event.state & 0x0001))
        ctrl_pressed = bool(event and (event.state & 0x0004))
        send_with_ctrl_enter = self.send_with_ctrl_enter_var.get()

        if shift_pressed:
            return None

        if send_with_ctrl_enter:
            if ctrl_pressed:
                self.play_submit_feedback_sound()
                self.handle_submit_button_click()
                return "break"
            return None

        if ctrl_pressed:
            return None

        self.play_submit_feedback_sound()
        self.handle_submit_button_click()
        return "break"

    def focus_text_input(self):
        """Focus the text input for fast typing in compact mode."""
        if hasattr(self, 'text_input') and self.text_input.winfo_exists():
            try:
                self.text_input.focus_force()
                self.text_input.focus_set()
                self.text_input.mark_set(tk.INSERT, tk.END)
                self.text_input.see(tk.INSERT)
            except tk.TclError as e:
                print(f"Error focusing text input: {e}")

    def play_submit_feedback_sound(self):
        """Play a short confirmation sound when sending from the keyboard."""
        threading.Thread(
            target=lambda: self.play_sound('assets/pop.wav'),
            daemon=True
        ).start()

    def get_speech_model_labels(self):
        """Return user-facing labels for supported speech models."""
        return [label for label, _model_id in self.available_speech_models]

    def get_speech_model_label(self, model_id):
        """Map a stored model id to the current UI label."""
        normalized = (model_id or self.default_speech_model).strip().lower()
        alias_map = {
            "realtime-1.5": "gpt-audio-1.5",
            "gpt-realtime": "gpt-audio-1.5",
            "gpt-realtime-1.5": "gpt-audio-1.5",
            "gpt-audio": "gpt-audio-1.5"
        }
        normalized = alias_map.get(normalized, normalized)

        for label, candidate_id in self.available_speech_models:
            if candidate_id == normalized:
                return label

        return self.available_speech_models[0][0]

    def get_selected_speech_model(self):
        """Return the API model id for the current speech-model selection."""
        selected_label = self.speech_model_var.get()
        for label, model_id in self.available_speech_models:
            if label == selected_label:
                return model_id
        return self.default_speech_model

    def speech_model_supports_tone_instructions(self, model_id=None):
        """Return whether a speech model accepts instruction-based voice steering."""
        active_model = model_id or self.get_selected_speech_model()
        return active_model not in {"tts-1", "tts-1-hd"}

    def get_openai_voices_for_model(self, model_id=None):
        """Return supported built-in voices for the selected speech model."""
        active_model = model_id or self.get_selected_speech_model()
        if active_model == "gpt-audio-1.5":
            return ['alloy', 'ash', 'ballad', 'coral', 'echo', 'sage', 'shimmer', 'verse', 'marin', 'cedar']
        return ['alloy', 'ash', 'ballad', 'coral', 'echo', 'fable', 'nova', 'onyx', 'sage', 'shimmer', 'verse']

    def get_default_voice_for_model(self, model_id=None):
        """Pick a sensible default voice for the active OpenAI speech model."""
        available = self.get_openai_voices_for_model(model_id)
        if 'alloy' in available:
            return self.get_voice_display_label('alloy')
        return self.get_voice_display_label(available[0]) if available else "[System] Default"

    def get_voice_display_label(self, voice_id):
        """Return a human-friendly label for a built-in voice."""
        if not voice_id or voice_id.startswith("[System]"):
            return voice_id

        descriptor = self.voice_descriptors.get(voice_id)
        if descriptor:
            return f"{voice_id} - {descriptor}"
        return voice_id

    def get_voice_id_from_label(self, voice_label):
        """Extract the raw voice id from a display label."""
        if not voice_label or voice_label.startswith("[System]"):
            return voice_label

        return voice_label.split(" - ", 1)[0].strip()

    def update_option_menu_choices(self, option_menu, options, command, variable=None):
        """Replace the choices in a Tk OptionMenu."""
        if option_menu is None:
            return

        menu = option_menu["menu"]
        menu.delete(0, "end")

        for option in options:
            menu.add_command(
                label=option,
                command=lambda value=option, var=variable: (
                    var.set(value) if var is not None else None,
                    command(value)
                )
            )

    def update_speech_model_selection(self):
        """Synchronize all speech-model dropdowns."""
        selected_label = self.get_speech_model_label(self.get_selected_speech_model())
        self.speech_model_var.set(selected_label)

        labels = self.get_speech_model_labels()
        for dropdown_name in ("speech_model_menu", "quick_speech_model_menu", "compact_speech_model_menu"):
            dropdown = getattr(self, dropdown_name, None)
            if dropdown is None:
                continue
            self.update_option_menu_choices(dropdown, labels, self.on_speech_model_change, self.speech_model_var)

    def update_voice_selection(self):
        """Refresh voice selectors for the active speech model."""
        selected_voice = self.voice_var.get() if hasattr(self, 'voice_var') else ""
        model_id = self.get_selected_speech_model()
        self.available_voices = self.get_available_voices(model_id)

        if selected_voice not in self.available_voices:
            if self.has_api_key:
                next_voice = self.get_default_voice_for_model(model_id)
            else:
                next_voice = self.available_voices[0] if self.available_voices else "[System] Default"
            self.voice_var.set(next_voice)

        if hasattr(self, 'voice_menu'):
            self.update_option_menu_choices(self.voice_menu, self.available_voices, self.on_voice_change, self.voice_var)

    def update_speech_model_hint(self):
        """Explain the behavior of the selected speech model."""
        if not hasattr(self, 'speech_model_hint_label'):
            return

        selected_model = self.get_selected_speech_model()
        if not self.has_api_key:
            hint = "OpenAI speech models require an API key. System voices still work without one."
        elif selected_model == "tts-1-hd":
            hint = "TTS-1 HD prioritizes cleaner output, but it ignores tone instructions and tone presets."
        elif selected_model == "gpt-audio-1.5":
            hint = "Audio 1.5 gives more natural speech through Chat Completions. For a true live session, you'd need a separate Realtime API flow."
        else:
            hint = "4o Mini TTS supports tone instructions, so presets and intensity boosting stay active."

        self.speech_model_hint_label.config(text=hint)

    def build_chat_audio_messages(self, text, tone_instructions):
        """Build messages for chat-based audio generation while preserving the user's text."""
        system_parts = [
            "You are a text-to-speech narrator.",
            "Your job is to repeat the provided phrase exactly as written.",
            "Treat the user's message as a script to perform, not as a question or chat message.",
            "Do not answer it, translate it, summarize it, or react to it.",
            "Do not add commentary, explanations, greetings, or extra words.",
            "Keep the spoken output natural and expressive."
        ]

        if tone_instructions:
            system_parts.append(f"Voice style guidance: {tone_instructions}")

        return [
            {"role": "system", "content": " ".join(system_parts)},
            {
                "role": "user",
                "content": (
                    "REPEAT THIS PHRASE WITH THE REQUESTED TONE. "
                    "DO NOT RESPOND TO IT. DO NOT CHANGE THE WORDS.\n\n"
                    f"{text}"
                )
            }
        ]

    def generate_audio_via_chat_completions(self, model_id, voice, text, tone_instructions, output_file):
        """Generate audio using chat completions models that return audio directly."""
        response = self.client.chat.completions.create(
            model=model_id,
            modalities=["text", "audio"],
            audio={
                "voice": voice,
                "format": "wav"
            },
            messages=self.build_chat_audio_messages(text, tone_instructions),
            temperature=0.6
        )

        message = response.choices[0].message if response.choices else None
        if message is None or getattr(message, "audio", None) is None or not getattr(message.audio, "data", None):
            raise ValueError("The model returned no audio data.")

        audio_bytes = base64.b64decode(message.audio.data)
        with open(output_file, "wb") as audio_file:
            audio_file.write(audio_bytes)

    def get_tone_intensity_profile(self):
        """Return guidance for how assertively the TTS should perform the tone."""
        profiles = {
            "mild": {
                "label": "Mild",
                "directive": "Make the style noticeable, but keep it controlled and natural.",
                "accent": "Use light character, light rhythm shaping, and subtle color."
            },
            "strong": {
                "label": "Strong",
                "directive": "Make the style clearly obvious from the first words and sustain it throughout.",
                "accent": "Lean into the character, cadence, attitude, and emphasis without drifting back to neutral."
            },
            "extreme": {
                "label": "Extreme",
                "directive": "Make the style dramatic, unmistakable, and highly stylized for the entire utterance.",
                "accent": "Push character, accent, rhythm, and emotional color hard while staying intelligible."
            }
        }
        selected = (self.tone_intensity_var.get() or "strong").lower()
        return profiles.get(selected, profiles["strong"])

    def shorten_tone_fragment(self, text, max_words=16):
        """Trim verbose tone prose down to the strongest descriptive fragment."""
        cleaned = " ".join((text or "").replace("\n", " ").split()).strip(" .;,:-")
        if not cleaned:
            return ""

        for separator in ("; ", ". ", " - ", " -- "):
            if separator in cleaned:
                candidate = cleaned.split(separator, 1)[0].strip(" .;,:-")
                if candidate:
                    cleaned = candidate
                    break

        words = cleaned.split()
        if len(words) > max_words:
            cleaned = " ".join(words[:max_words]).rstrip(" ,;:-")
        return cleaned

    def condense_tone_preset_text(self, tone_text):
        """Convert long preset notes into a short, forceful TTS style direction."""
        raw_text = (tone_text or "").strip()
        if not raw_text:
            return ""

        blocks = [block.strip() for block in re.split(r"\n\s*\n+", raw_text) if block.strip()]
        labeled_values = {}
        free_blocks = []

        for block in blocks:
            single_line = " ".join(block.split())
            if ":" in single_line:
                label, value = single_line.split(":", 1)
                normalized_label = label.strip().lower()
                if normalized_label in {
                    "voice affect",
                    "tone",
                    "pacing",
                    "emotion",
                    "pronunciation",
                    "pauses"
                }:
                    labeled_values[normalized_label] = value.strip()
                    continue
            free_blocks.append(single_line)

        directives = []
        labeled_templates = (
            ("voice affect", "Sound {}."),
            ("tone", "Stay {}."),
            ("pacing", "Keep the pacing {}."),
            ("emotion", "Let the emotion feel {}."),
            ("pronunciation", "Stress words with {}."),
            ("pauses", "Use pauses that feel {}.")
        )

        for label, template in labeled_templates:
            value = self.shorten_tone_fragment(labeled_values.get(label, ""))
            if value:
                directives.append(template.format(value.lower()))

        if free_blocks:
            free_text = self.shorten_tone_fragment(" ".join(free_blocks), max_words=28)
            if free_text:
                if not directives:
                    return free_text
                directives.append(f"Core vibe: {free_text}.")

        if directives:
            return " ".join(directives)

        return self.shorten_tone_fragment(raw_text, max_words=28)

    def build_tone_instructions(self, tone_name, tone_text):
        """Build a stronger instruction payload for OpenAI TTS."""
        compact_tone = self.condense_tone_preset_text(tone_text)
        if not compact_tone:
            return ""

        intensity = self.get_tone_intensity_profile()
        return (
            "Perform the text in the requested style instead of reading it neutrally. "
            f"{intensity['directive']} {intensity['accent']} "
            "Do not describe the tone. Act it out while keeping the words clear and natural. "
            "If the preset implies an accent or regional flavor, make it audible.\n\n"
            f"Tone preset: {tone_name}\n"
            f"Tone summary: {compact_tone}\n"
            f"Intensity: {intensity['label']}"
        )

    def make_unique_tone_name(self, base_name):
        """Create a unique tone preset name."""
        cleaned_name = " ".join((base_name or "").strip().split()) or "Custom Tone"
        if cleaned_name not in self.tone_presets:
            return cleaned_name

        suffix = 2
        while f"{cleaned_name} {suffix}" in self.tone_presets:
            suffix += 1
        return f"{cleaned_name} {suffix}"

    def set_current_tone(self, tone_name, save=True):
        """Set the current tone preset and synchronize all selectors."""
        tone_name = tone_name if tone_name in self.tone_presets or tone_name == "None" else "None"
        self.current_tone_name = tone_name
        self.tone_var.set(tone_name)

        if save:
            self.save_current_tone_to_settings()

    def normalize_ai_json_response(self, response_text):
        """Extract JSON from responses that may include code fences."""
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        return cleaned.strip()

    def coerce_tone_preset_data(self, response_text, fallback_request):
        """Best-effort extraction of a tone preset from imperfect model output."""
        cleaned = self.normalize_ai_json_response(response_text)

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return {
                    "name": parsed.get("name") or fallback_request,
                    "instructions": (parsed.get("instructions") or "").strip()
                }
        except json.JSONDecodeError:
            pass

        name_match = re.search(r'"name"\s*:\s*"([^"]+)"', cleaned, re.IGNORECASE)
        instructions_match = re.search(r'"instructions"\s*:\s*"([^"]+)"', cleaned, re.IGNORECASE | re.DOTALL)
        if name_match or instructions_match:
            return {
                "name": name_match.group(1).strip() if name_match else fallback_request,
                "instructions": instructions_match.group(1).strip() if instructions_match else cleaned
            }

        lines = [line.strip(" -*\t") for line in cleaned.splitlines() if line.strip()]
        if len(lines) >= 2:
            return {
                "name": lines[0][:40],
                "instructions": "\n".join(lines[1:]).strip()
            }

        return {
            "name": fallback_request,
            "instructions": cleaned.strip()
        }

    def generate_tone_preset_with_ai(self):
        """Create and auto-select a new tone preset from a natural-language request."""
        if not self.has_api_key:
            messagebox.showinfo(
                "API Key Required",
                "Generating a tone preset with AI requires an OpenAI API key."
            )
            return

        tone_request = self.prompt_string_modal(
            "Generate Tone with AI",
            "Describe the voice type you want.\n\nExample: voz de heroe vaquero mexicano"
        )

        if not tone_request:
            return

        settings = self.load_settings()
        model = settings.get("model", self.default_model) or self.default_model

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You create short, high-impact TTS tone presets. Return valid JSON only with keys "
                            "\"name\" and \"instructions\". The name should be short, memorable, and suitable "
                            "for a preset dropdown. The instructions must be 1 to 3 punchy sentences, written "
                            "as direct performance guidance for a text-to-speech model. Avoid section headers, "
                            "rubrics, bullet points, or long explanations. Make the voice style easy to hear."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            "Create a spoken tone preset for this request: "
                            f"{tone_request}\n\n"
                            "Make the result vivid, performable, and noticeably stylized."
                        )
                    }
                ],
                max_tokens=220,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content or ""
            preset_data = self.coerce_tone_preset_data(content, tone_request)
            preset_name = self.make_unique_tone_name(preset_data.get("name", tone_request))
            preset_instructions = self.condense_tone_preset_text((preset_data.get("instructions") or "").strip())

            if not preset_instructions:
                raise ValueError("AI response did not include preset instructions.")

            self.tone_presets[preset_name] = preset_instructions
            self.save_tone_presets(self.tone_presets)
            self.set_current_tone(preset_name)
            self.update_tone_selection()

            messagebox.showinfo(
                "Tone Created",
                f"Created and selected tone preset: {preset_name}"
            )
        except Exception as e:
            messagebox.showerror(
                "Tone Generation Failed",
                f"Couldn't generate the tone preset automatically:\n\n{e}"
            )

    def bring_window_to_foreground(self):
        """Use the native window manager to bring the app to the foreground."""
        try:
            self.update_idletasks()

            if platform.system() == "Windows":
                user32 = ctypes.windll.user32
                hwnd = self.winfo_id()
                SW_RESTORE = 9
                SWP_NOSIZE = 0x0001
                SWP_NOMOVE = 0x0002
                HWND_TOPMOST = -1
                HWND_NOTOPMOST = -2

                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
                user32.BringWindowToTop(hwnd)
                user32.SetForegroundWindow(hwnd)
                user32.SetActiveWindow(hwnd)
                user32.SetFocus(hwnd)

                if not self.always_on_top_var.get():
                    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            else:
                self.lift()
                self.focus_force()
        except Exception as e:
            print(f"Error bringing window to foreground: {e}")

    def apply_always_on_top(self):
        """Apply the always-on-top preference to the main window."""
        try:
            is_topmost = self.always_on_top_var.get()
            self.attributes("-topmost", is_topmost)
            if is_topmost:
                self.lift()
        except tk.TclError as e:
            print(f"Error applying always-on-top setting: {e}")

    def apply_window_opacity(self):
        """Apply the configured window opacity."""
        try:
            opacity = max(0.35, min(1.0, float(self.window_opacity.get())))
            self.attributes("-alpha", opacity)
        except (tk.TclError, ValueError) as e:
            print(f"Error applying window opacity: {e}")

    def toggle_always_on_top(self):
        """Toggle whether the main window stays above other windows."""
        settings = self.load_settings()
        settings["always_on_top"] = self.always_on_top_var.get()
        self.save_settings_to_JSON(settings)
        self.apply_always_on_top()

    def toggle_send_with_ctrl_enter(self):
        """Toggle whether sending uses Ctrl+Enter instead of Enter."""
        settings = self.load_settings()
        settings["send_with_ctrl_enter"] = self.send_with_ctrl_enter_var.get()
        self.save_settings_to_JSON(settings)

    def set_tone_intensity(self):
        """Save how strongly tone presets should shape the TTS performance."""
        selected = (self.tone_intensity_var.get() or "strong").lower()
        if selected not in {"mild", "strong", "extreme"}:
            selected = "strong"
        self.tone_intensity_var.set(selected)

        settings = self.load_settings()
        settings["tone_intensity"] = selected
        self.save_settings_to_JSON(settings)

    def set_speech_model_from_menu(self):
        """Apply the speech model selected from a menu radio item."""
        self.on_speech_model_change(self.speech_model_var.get())

    def on_speech_model_change(self, selected_label=None):
        """Persist speech model changes and refresh voice-related controls."""
        if selected_label:
            self.speech_model_var.set(selected_label)

        selected_model = self.get_selected_speech_model()
        settings = self.load_settings()
        settings["speech_model"] = selected_model
        self.save_settings_to_JSON(settings)

        self.update_speech_model_selection()
        self.update_voice_selection()
        self.update_speech_model_hint()
        self.on_voice_change()

    def update_window_opacity(self, value):
        """Update opacity in real time from the slider."""
        try:
            opacity = round(float(value), 2)
        except ValueError:
            return

        self.window_opacity.set(opacity)
        self.apply_window_opacity()

    def save_window_opacity(self):
        """Persist the current window opacity setting."""
        settings = self.load_settings()
        settings["window_opacity"] = round(float(self.window_opacity.get()), 2)
        self.save_settings_to_JSON(settings)

    def show_window_opacity_settings(self):
        """Show a slider to control the main window opacity."""
        dialog = tk.Toplevel(self)
        dialog.title("Window Opacity")
        dialog.geometry("320x140")
        dialog.transient(self)
        dialog.grab_set()

        ttk.Label(dialog, text="Window opacity").pack(pady=(15, 5))

        value_label = ttk.Label(dialog, text=f"{int(self.window_opacity.get() * 100)}%")
        value_label.pack()

        slider = ttk.Scale(
            dialog,
            from_=0.35,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.window_opacity,
            command=lambda value: (
                value_label.config(text=f"{int(float(value) * 100)}%"),
                self.update_window_opacity(value)
            )
        )
        slider.pack(fill=tk.X, padx=20, pady=10)

        ttk.Button(
            dialog,
            text="Save",
            command=lambda: (self.save_window_opacity(), dialog.destroy())
        ).pack(pady=(0, 10))

    def apply_compact_mode_layout(self):
        """Show only the writing essentials when compact mode is enabled."""
        compact_mode = self.compact_mode_var.get()

        try:
            self.overrideredirect(compact_mode)
        except tk.TclError as e:
            print(f"Error updating window chrome: {e}")

        self.config(menu="" if compact_mode else self.menubar)

        for widget_name in ("voice_frame", "device_frame", "main_separator", "text_read_frame", "save_frame", "status_frame", "button_frame"):
            widget = getattr(self, widget_name, None)
            if widget and widget.winfo_exists():
                if compact_mode:
                    widget.grid_remove()
                else:
                    widget.grid()

        if hasattr(self, 'banner_frame') and self.banner_frame.winfo_exists():
            if compact_mode or self.banner_var.get():
                self.banner_frame.grid_remove()
            else:
                self.banner_frame.grid()

        if hasattr(self, 'presets_manager'):
            if hasattr(self.presets_manager, 'toggle_frame') and self.presets_manager.toggle_frame.winfo_exists():
                if compact_mode:
                    self.presets_manager.toggle_frame.grid_remove()
                else:
                    self.presets_manager.toggle_frame.grid()

            if hasattr(self.presets_manager, 'presets_frame') and self.presets_manager.presets_frame.winfo_exists():
                if compact_mode or self.presets_collapsed:
                    self.presets_manager.presets_frame.grid_remove()
                else:
                    self.presets_manager.presets_frame.grid()
                    self.presets_manager.refresh_presets_display()

        if hasattr(self, 'text_input') and self.text_input.winfo_exists():
            self.text_input.configure(height=1 if compact_mode else 5)
            if compact_mode:
                self.text_input.grid_configure(column=0, row=5, columnspan=1, padx=(0, 14), pady=(2, 2), sticky="ew")
            else:
                self.text_input.configure(height=6)
                self.text_input.grid_configure(column=0, row=5, columnspan=2, padx=0, pady=(0, 20), sticky="nsew")

        if hasattr(self, 'main_frame') and self.main_frame is not None:
            if compact_mode:
                self.main_frame.columnconfigure(0, weight=9)
                self.main_frame.columnconfigure(1, weight=0, minsize=120)
                self.main_frame.columnconfigure(2, weight=0, minsize=140)
                self.main_frame.columnconfigure(3, weight=0, minsize=120)
                self.main_frame.configure(style='CompactDark.TFrame')
                self.configure(background=self.compact_bg_color)
            else:
                self.main_frame.columnconfigure(0, weight=1, minsize=0)
                self.main_frame.columnconfigure(1, weight=1, minsize=0)
                self.main_frame.columnconfigure(2, weight=0, minsize=0)
                self.main_frame.columnconfigure(3, weight=0, minsize=0)
                self.main_frame.configure(style='TFrame')
                self.configure(background=self.normal_bg_color)

        if hasattr(self, 'compact_tone_menu') and self.compact_tone_menu.winfo_exists():
            if compact_mode:
                self.compact_tone_menu.grid()
                self.compact_tone_menu.grid_configure(padx=(0, 10), pady=(2, 2))
            else:
                self.compact_tone_menu.grid_remove()

        if hasattr(self, 'quick_tone_menu') and self.quick_tone_menu.winfo_exists():
            self.quick_tone_menu.grid_remove()

        if hasattr(self, 'compact_speech_model_menu') and self.compact_speech_model_menu.winfo_exists():
            if compact_mode:
                self.compact_speech_model_menu.grid()
                self.compact_speech_model_menu.grid_configure(padx=(0, 10), pady=(2, 2))
            else:
                self.compact_speech_model_menu.grid_remove()

        if hasattr(self, 'compact_submit_button') and self.compact_submit_button.winfo_exists():
            if compact_mode:
                self.compact_submit_button.grid()
                self.compact_submit_button.grid_configure(padx=(8, 0), pady=(2, 2))
            else:
                self.compact_submit_button.grid_remove()

        compact_button_width = 220 if compact_mode else 260
        if hasattr(self, 'record_button') and self.record_button.winfo_exists():
            self.record_button.configure(width=compact_button_width)

        if hasattr(self, 'submit_button') and self.submit_button.winfo_exists():
            self.submit_button.configure(width=compact_button_width)
            self.submit_button.grid_configure(column=1)

        if hasattr(self, 'main_frame') and self.main_frame is not None:
            self.main_frame.configure(padding=12 if compact_mode else 20)

        if compact_mode:
            self.apply_always_on_top()
            self.apply_window_opacity()
            self.after(50, self.focus_text_input)

    def toggle_compact_mode(self):
        """Toggle a smaller writing-focused layout."""
        settings = self.load_settings()
        settings["compact_mode"] = self.compact_mode_var.get()
        self.save_settings_to_JSON(settings)

        self.apply_compact_mode_layout()
        self.update_window_size()
        self._maintain_consistent_width()
        self.update_idletasks()

        # A second idle pass helps Tk settle the grid after switching window chrome/layout live.
        self.after_idle(self.apply_compact_mode_layout)
        self.after_idle(self._maintain_consistent_width)

        if hasattr(self, 'version_checker') and self.version_checker.notification_visible:
            self.after(100, self._reposition_version_notification)

    def show_writer_overlay(self):
        """Bring the writing UI to the foreground and focus the text box."""
        self.deiconify()
        self.update_window_size()
        self.apply_window_opacity()

        original_topmost = self.always_on_top_var.get()
        try:
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.after(300, lambda: self.attributes("-topmost", original_topmost))
        except tk.TclError as e:
            print(f"Error showing writer overlay: {e}")

        self.after(0, self.bring_window_to_foreground)
        self.after(50, self.focus_text_input)
        self.after(150, self.focus_text_input)
        self.after(300, self.focus_text_input)

    def save_current_text_as_preset(self):
        """Forward the save request to the presets manager."""
        self.show_save_preset_dialog()

    def show_instructions(self):
        instruction_window = tk.Toplevel(self)
        instruction_window.title("How to Use")
        instruction_window.geometry("600x720")  # Width x Height

        instructions = AppText.INSTRUCTIONS
        
        tk.Label(instruction_window, text=instructions, justify=tk.LEFT, wraplength=580).pack(padx=10, pady=10)
        
        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def show_terms_of_use(self):
        # Try multiple approaches to find the LICENSE.md file
        license_content = None
        possible_paths = [
            "LICENSE.md",                            # Direct path when running as script
            self.resource_path("LICENSE.md"),        # Using resource_path helper
            self.resource_path("assets/LICENSE.md"), # Check in assets folder
            Path("assets") / "LICENSE.md"            # Alternative assets path
        ]
        
        # Try each path until we find the file
        for path in possible_paths:
            try:
                with open(path, "r", encoding="utf-8") as file:
                    license_content = file.read()
                    break
            except (FileNotFoundError, PermissionError, UnicodeDecodeError):
                continue
        
        # If we couldn't find the file in the filesystem, provide a fallback
        if license_content is None:
            license_content = AppText.DEFAULT_LICENSE
        
        # Create a new window to display the terms of use
        instruction_window = tk.Toplevel(self)
        instruction_window.title("Terms of Use")
        instruction_window.geometry("800x700")  # Width x Height

        # Create a frame to contain the text widget and scrollbar
        frame = ttk.Frame(instruction_window)
        frame.pack(fill=tk.BOTH, expand=True)

        # Add a scrolling text widget to display the license content
        text_widget = tk.Text(frame, wrap=tk.WORD)
        text_widget.insert(tk.END, license_content)
        text_widget.config(state=tk.DISABLED)  # Make the text read-only
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure the scrollbar to work with the text widget
        text_widget.config(yscrollcommand=scrollbar.set)

        # Add a button to close the window
        ttk.Button(instruction_window, text="Close", command=instruction_window.destroy).pack(pady=(10, 0))

    def get_app_support_path_mac(self):
        home = Path.home()
        app_support_path = home / 'Library' / 'Application Support' / 'scorchsoft-text-to-mic'
        app_support_path.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        return app_support_path
    
    def save_api_key_mac(self, api_key):
        return APIKeyManager.save_api_key(api_key)

    def save_api_key(self, api_key):
        """Compatibility wrapper for the shared API key manager."""
        return APIKeyManager.save_api_key(api_key)

    def load_api_key_mac(self):
        env_path = APIKeyManager.get_env_file_path()
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('OPENAI_API_KEY'):
                        return line.strip().split('=')[1]
        return None

 
    def get_api_key(self):
        """Compatibility wrapper for the shared API key manager."""
        return APIKeyManager.get_api_key(self)





    def get_audio_devices(self):
        p = pyaudio.PyAudio()
        devices = {}
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxOutputChannels'] > 0:  # Filter for output-capable devices
                devices[info['name']] = i
        p.terminate()
        return devices
    
    def get_input_devices(self):
        p = pyaudio.PyAudio()
        devices = {}
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:  # Filter for input-capable devices
                devices[info['name']] = i
        p.terminate()
        return devices

    
    def get_audio_file_path(self, filename):
        if platform.system() == 'Darwin':  # Check if the OS is macOS
            mac_path = APIKeyManager.get_app_support_path_mac()
            return f"{mac_path}/{filename}"
        else:
            return Path(filename)  # Default to current directory for non-macOS systems


    def submit_text(self, play_text = None):
        print(f"submit text self recording: {self.recording}")
        if self.recording:
            print("Stopping recording")
            self.stop_recording(auto_play = True)
        else:
            print("Submitting text")
            self.submit_text_helper(play_text = play_text)
    
    def submit_text_helper(self, play_text = None):
        if play_text is None:
            #Load from GUI if play text not set
            text = self.text_input.get("1.0", tk.END).strip()
        else:
            text = play_text

        if not text:
            messagebox.showinfo("Error", "Please enter some text to synthesize.")
            return
        
        selected_voice = self.voice_var.get()
        selected_voice_id = self.get_voice_id_from_label(selected_voice)
        is_system_voice = selected_voice.startswith("[System]")
        
        if is_system_voice:
            # Use system TTS
            system_voice_name = selected_voice.replace("[System] ", "")
            for voice in self.system_voices:
                if voice.name == system_voice_name:
                    self.engine.setProperty('voice', voice.id)
                    break
            
            # Convert device names to indices
            primary_index = self.available_devices.get(self.device_index.get(), None)
            secondary_index = self.available_devices.get(self.device_index_2.get(), None) if self.device_index_2.get() != "None" else None

            if primary_index is None:
                messagebox.showerror("Error", "Primary device not selected or unavailable.")
                return
            
            try:
                # Create a proper temporary file with a simple name in current directory
                temp_filename = "temp_speech_output.wav"
                
                # Generate audio using system TTS
                self.engine.save_to_file(text, temp_filename)
                self.engine.runAndWait()
                
                # Store as last audio file for replay
                self.last_audio_file = temp_filename
                
                # Play the generated audio
                if primary_index and secondary_index != "None" and secondary_index is not None:
                    self.play_audio_multiplexed([temp_filename, temp_filename],
                                              [primary_index, secondary_index])
                else:
                    self.play_audio_multiplexed([temp_filename],
                                              [primary_index])
                
                # We'll leave the file for potential replay rather than deleting it immediately
            except Exception as e:
                messagebox.showerror("TTS Error", f"Failed to generate or play system voice: {str(e)}")
                
        else:
            # Use OpenAI TTS
            if not self.has_api_key:
                messagebox.showerror("API Key Required", 
                                   "An OpenAI API Key is required for speech to text or to use OpenAI voices.\n\n"
                                   "Please add your API key in Settings.\n\n"
                                   "Note: You can still use text to speech with the system voices only.")
                return
                
            # Check if a tone preset is selected and add it to the text
            selected_tone_name = self.tone_var.get()
            
            # Get the actual tone instructions from the tone_presets dictionary
            tone_instructions = None
            if selected_tone_name != "None" and selected_tone_name in self.tone_presets:
                tone_instructions = self.build_tone_instructions(
                    selected_tone_name,
                    self.tone_presets[selected_tone_name]
                )
            else:
                tone_instructions = ""  # Empty string if "None" or not found
            
            # Convert device names to indices
            primary_index = self.available_devices.get(self.device_index.get(), None)
            secondary_index = self.available_devices.get(self.device_index_2.get(), None) if self.device_index_2.get() != "None" else None

            if primary_index is None:
                messagebox.showerror("Error", "Primary device not selected or unavailable.")
                return
            
            try:
                speech_model = self.get_selected_speech_model()
                self.last_audio_file = self.get_audio_file_path("last_output.wav")

                if speech_model == "gpt-audio-1.5":
                    self.generate_audio_via_chat_completions(
                        speech_model,
                        selected_voice_id,
                        text,
                        tone_instructions,
                        str(self.last_audio_file)
                    )
                else:
                    request_kwargs = dict(
                    model=speech_model,
                    voice=selected_voice_id,
                    input=text,
                    response_format='wav'
                )

                    if tone_instructions and self.speech_model_supports_tone_instructions(speech_model):
                        request_kwargs["instructions"] = tone_instructions

                    response = self.client.audio.speech.create(
                        **request_kwargs
                    )
                    response.stream_to_file(str(self.last_audio_file))

                #Play to either two or a single stream
                if primary_index and secondary_index != "None" and secondary_index is not None:
                    self.play_audio_multiplexed([self.last_audio_file, self.last_audio_file],
                                                [primary_index, secondary_index])
                else:
                    self.play_audio_multiplexed([self.last_audio_file],
                                                [primary_index])

            except Exception as e:
                messagebox.showerror("API Error", f"Failed to generate audio: {str(e)}")


    def resample_audio(self, file_path, target_sample_rate):
        sound = AudioSegment.from_file(file_path)
        resampled_sound = sound.set_frame_rate(target_sample_rate)
        resampled_file_path = "resampled_" + file_path
        resampled_sound.export(resampled_file_path, format="wav")
        return resampled_file_path

    def play_audio_multiplexed(self, file_paths, device_indices):
        """Play audio files to multiple devices with better cancellation handling."""
        # Stop any existing playback first
        if hasattr(self, 'is_playing') and self.is_playing:
            self.stop_playback()
            # Add a small delay to ensure previous resources are cleaned up
            time.sleep(0.2)
        
        # Make p and streams accessible for stop_playback
        try:
            self.current_playback_p = pyaudio.PyAudio()
            self.current_playback_streams = []
            self.is_playing = True
            
            # Update button text to show Stop with cancel operation shortcut
            self.update_buttons_for_playback(True)
            
        except Exception as e:
            print(f"Error initializing PyAudio: {e}")
            messagebox.showerror("Audio Error", f"Failed to initialize audio system: {e}")
            return
        
        try:
            # Open all files and start all streams
            for file_path, device_index in zip(file_paths, device_indices):
                if not self.is_playing:
                    print("Playback canceled during initialization")
                    break
                    
                try:
                    # Ensure the file_path is a string when opening the file
                    file_path_str = str(file_path)
                    print(f"Opening audio file: {file_path_str}")
                    
                    # Make sure file exists
                    if not os.path.exists(file_path_str):
                        messagebox.showerror("File Not Found", f"Could not find audio file: {file_path_str}")
                        continue
                        
                    wf = wave.open(file_path_str, 'rb')
                except FileNotFoundError:
                    messagebox.showerror("File Not Found", f"Could not find audio file: {file_path_str}")
                    continue  # Skip this iteration and proceed with other files if any
                except wave.Error as e:
                    messagebox.showerror("Wave Error", f"Error reading audio file: {file_path_str}. Error: {str(e)}")
                    continue
                except Exception as e:
                    messagebox.showerror("File Error", f"Unexpected error with audio file: {str(e)}")
                    continue

                try:
                    # Get device info including default sample rate
                    device_info = self.get_device_info(device_index)
                    sample_rate = int(device_info['defaultSampleRate']) if device_info else 44100
                    wf_frame_rate = wf.getframerate()

                    print(f"Device Sample Rate: {sample_rate}")
                    print(f"Audio Sample Rate: {wf_frame_rate}")

                    # Create a stream from our file with current frame rate (we'll handle resampling for mismatch later)
                    stream = self.current_playback_p.open(
                        format=self.current_playback_p.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf_frame_rate,  # Use audio file's rate for now
                        output=True,
                        output_device_index=int(device_index)
                    )
                    
                except Exception as e:
                    print(f"Stream creation error: {e}")
                    messagebox.showerror("Stream Creation Error", f"Failed to create audio stream for device index {device_index}: {str(e)}")
                    wf.close()
                    continue

                self.current_playback_streams.append((stream, wf))

            # Play interleaved using a more robust approach
            self._play_audio_streams()
            
        except Exception as e:
            print(f"Playback setup error: {e}")
            messagebox.showerror("Playback Error", f"Error setting up playback: {e}")
            self.stop_playback()
    
    def _play_audio_streams(self):
        """Handle the actual audio playback in chunks, with better error handling."""
        if not hasattr(self, 'current_playback_streams') or not self.current_playback_streams:
            print("No streams to play")
            self.stop_playback()
            return
            
        try:
            finished_streams = []
            
            # Process one chunk from each stream
            for stream, wf in self.current_playback_streams:
                if not self.is_playing:
                    print("Playback canceled during streaming")
                    break
                    
                try:
                    data = wf.readframes(1024)
                    if data:
                        stream.write(data)
                    else:
                        # Mark this stream as finished
                        finished_streams.append((stream, wf))
                except Exception as e:
                    print(f"Error during stream playback: {e}")
                    # Add to finished streams if there's an error
                    finished_streams.append((stream, wf))
            
            # Remove finished streams
            for stream_pair in finished_streams:
                try:
                    stream, wf = stream_pair
                    stream.stop_stream()
                    stream.close()
                    wf.close()
                    self.current_playback_streams.remove(stream_pair)
                except Exception as e:
                    print(f"Error cleaning up finished stream: {e}")
            
            # If we still have streams and playback is active, schedule the next chunk
            if self.current_playback_streams and self.is_playing:
                self.after(1, self._play_audio_streams)  # Schedule next chunk processing
            else:
                # All done or canceled, clean up
                self.stop_playback()
                
        except Exception as e:
            print(f"Error in _play_audio_streams: {e}")
            self.stop_playback()
    
    def stop_playback(self):
        """Stop any active audio playback."""
        print("Attempting to stop playback")
        
        # Set flag first to exit any playback loops
        self.is_playing = False
        
        # Revert buttons to normal state
        self.update_buttons_for_playback(False)
        
        try:
            # Close any active streams
            if hasattr(self, 'current_playback_streams'):
                # Make a copy of the list to safely iterate while potentially modifying
                streams_to_close = list(self.current_playback_streams)
                
                for stream, wf in streams_to_close:
                    try:
                        # Check if stream exists and is active before attempting to stop it
                        if stream and stream.is_active():
                            stream.stop_stream()
                        if stream:
                            stream.close()
                        if wf:
                            wf.close()
                    except Exception as e:
                        print(f"Error closing stream: {e}")
                
                # Clear the list after processing all streams
                self.current_playback_streams = []
            
            # Terminate PyAudio instance - do this last and carefully
            if hasattr(self, 'current_playback_p') and self.current_playback_p:
                try:
                    # Add a small delay to ensure streams are properly closed before terminating
                    self.after(100, self._complete_playback_termination)
                except Exception as e:
                    print(f"Error scheduling PyAudio termination: {e}")
        
        except Exception as e:
            print(f"Error in stop_playback: {e}")
            # Don't reraise - we want to prevent crashes
    
    def _complete_playback_termination(self):
        """Complete the termination of PyAudio in a separate step to avoid crashes."""
        try:
            if hasattr(self, 'current_playback_p') and self.current_playback_p:
                self.current_playback_p.terminate()
                self.current_playback_p = None
                print("PyAudio terminated successfully")
        except Exception as e:
            print(f"Error terminating PyAudio: {e}")
            # Still clear the reference even if termination fails
            self.current_playback_p = None

    def play_last_audio(self):

        if hasattr(self, 'last_audio_file'):
            primary_index = self.available_devices.get(self.device_index.get(), None)
            secondary_index = self.available_devices.get(self.device_index_2.get(), None) if self.device_index_2.get() != "None" else None

            # Check if a secondary device is selected
            if primary_index and secondary_index != "None" and secondary_index is not None:
                self.play_audio_multiplexed([self.last_audio_file, self.last_audio_file],
                                            [primary_index, secondary_index])
            else:
                self.play_audio_multiplexed([self.last_audio_file],
                                            [primary_index])

        else:
            messagebox.showinfo("No Audio", "No audio has been generated yet.")

    def play_saved_audio(self, file_path, device_name):
        device_index = self.available_devices.get(device_name, None)
        if device_index is None:
            messagebox.showerror("Error", "Selected audio device is not available.")
            return
        
        wf = wave.open(file_path, 'rb')
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True,
                            output_device_index=device_index)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
        finally:
            stream.stop_stream()
            stream.close()
            wf.close()
            p.terminate()

            
    def show_ai_editor_settings(self):
        """Show the AI copy editing settings dialog"""
        self.ai_editor.show_settings()

    def apply_ai_to_input(self):
        """Apply AI to the current input text"""
        # First check if we have an API key
        if not self.has_api_key:
            messagebox.showinfo(
                "API Key Required",
                "AI copyediting requires an OpenAI API key.\n\n"
                "Please add your API key in Settings to use this feature."
            )
            return
        
        # Check if AI copy editing is enabled in settings
        settings = self.load_settings()
        if not settings.get("chat_gpt_completion", False):
            messagebox.showinfo(
                "AI Copy Editing Disabled",
                "AI copy editing is currently disabled in settings.\n\n"
                "Please enable it in Settings → AI Copyediting before using this feature."
            )
            return
        
        # If we have an API key and AI is enabled, proceed with the AI editing
        self.ai_editor.apply_ai()

    def chat_gpt_settings(self):
        """Delegate to AIEditorManager"""
        self.show_ai_editor_settings()

    def save_chat_gpt_settings(self, settings):
        """Delegate to AIEditorManager"""
        self.ai_editor.save_settings(settings)

    def apply_ai(self, input_text=None):
        """Delegate to AIEditorManager"""
        return self.ai_editor.apply_ai(input_text)

    def get_device_info(self, device_index):
        p = pyaudio.PyAudio()
        try:
            device_info = p.get_device_info_by_index(device_index)
            return device_info
        finally:
            p.terminate()
    
    def toggle_recording(self, auto_play=False):
        if not self.recording:
            self.start_recording()
        else:
            self.stop_recording(auto_play)

    def stop_recording_btn_change(self, btn_text):
        self.record_button.config(text=btn_text)

    def start_recording(self, play_confirm_sound=False):
        if not self.has_api_key:
            messagebox.showerror("API Key Required", 
                    "An OpenAI API Key is required for speech to text or to use OpenAI voices.\n\n"
                    "Please add your API key in Settings.\n\n"
                    "Note: You can still use text to speech with the system voices only.")
            return
            
        input_device_index = self.input_device_index.get()
        input_device_id = self.available_input_devices.get(input_device_index)

        if input_device_id is None:
            if play_confirm_sound:
                self.play_sound('assets/please-select-input.wav')
            else:
                messagebox.showerror("Error", "Selected audio device is not available.")
            return

        device_info = self.get_device_info(input_device_id)
        sample_rate = int(device_info['defaultSampleRate'])

        print(f"Device info: {device_info}")

        if sample_rate is None:
            sample_rate = 44100

        if input_device_id is None:
            messagebox.showerror("Error", "Selected audio device is not available.")
            return
        
        try:
            self.recording = True
            
            # Get keyboard shortcuts from settings
            settings = self.load_settings()
            record_shortcut = "+".join(filter(None, settings["hotkeys"]["record_start_stop"]))
            play_shortcut = "+".join(filter(None, settings["hotkeys"]["play_last_audio"]))
            stop_shortcut = "+".join(filter(None, settings["hotkeys"]["stop_recording"]))
            cancel_shortcut = "+".join(filter(None, settings["hotkeys"]["cancel_operation"]))
            
            # Update CTkButton for recording state, keeping shortcuts visible
            self.record_button.configure(text=f"Stop and Insert", fg_color="#d32f2f", text_color="white")
            self.submit_button.configure(text=f"Stop and Play ({record_shortcut})", fg_color="#d32f2f")

            self.frames = []

            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=1024, input_device_index=input_device_id)

            if play_confirm_sound:
                self.play_sound('assets/pop.wav')

            def record():
                while self.recording:
                    data = self.stream.read(1024, exception_on_overflow=False)
                    self.frames.append(data)

            self.record_thread = threading.Thread(target=record)
            self.record_thread.start()

        except Exception as e:
            messagebox.showerror("Recording Error", f"Failed to record audio: {str(e)}")
            self.stop_recording(True)

    def stop_recording(self, cancel_save=False, auto_play=False):
        self.recording = False
        if hasattr(self, 'record_thread') and self.record_thread:
            self.record_thread.join()

        if hasattr(self, 'stream') and self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if hasattr(self, 'p') and self.p:
            self.p.terminate()

        if cancel_save==False:
            self.save_recording(auto_play=auto_play)
        
        # Get keyboard shortcuts from settings
        settings = self.load_settings()
        record_shortcut = "+".join(filter(None, settings["hotkeys"]["record_start_stop"]))
        play_shortcut = "+".join(filter(None, settings["hotkeys"]["play_last_audio"]))
        
        # Reset button appearance
        self.record_button.configure(
            text=f"Record Mic ({record_shortcut})",
            fg_color=self.idle_record_button_color,
            text_color=self.idle_record_text_color
        )
        self.submit_button.configure(text=f"Play Audio ({play_shortcut})", fg_color="#058705")

    def save_recording(self, auto_play = False):
        file_path = "output.wav"
        wf = wave.open(file_path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(self.frames))
        wf.close()
        print("Recording saved.")

        # If auto_play is requested, we'll handle it through the transcribe_audio callback
        # This ensures proper button state updates regardless of how playback is triggered
        self.after(0, self.transcribe_audio, file_path, auto_play)
        
    def transcribe_audio(self, file_path, auto_play=False):
        try:
            with open(str(file_path), "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model="gpt-4o-transcribe",
                    response_format="json"
                )

            settings = self.load_settings()
            
            # Always update the text with the raw transcription first
            self.text_input.delete("1.0", tk.END)
            self.text_input.insert("1.0", transcription.text)

            # Check if AI processing is enabled AND we have an API key
            if settings["chat_gpt_completion"] and settings["auto_apply_ai_to_recording"] and self.has_api_key:
                auto_apply_ai = True
            else:
                auto_apply_ai = False

            print(f"auto_apply_ai: {auto_apply_ai}")

            # If AI processing is enabled, apply it and update the text input again
            if auto_apply_ai:
                print("applying ai")
                # Set the update_ui parameter to True to ensure the text gets updated
                play_text = self.ai_editor.apply_ai(transcription.text, update_ui=True)
            else:
                print("outputting without ai")
                play_text = transcription.text

            if auto_play:
                print(f"Triggering auto play with: {play_text} ")
                # Use a slight delay to allow UI to update before playback starts
                self.after(100, lambda: self.submit_text_helper(play_text=play_text))
            
            print("Transcription Complete: The audio has been transcribed and the text has been placed in the input area.")
        
        except Exception as e:
            print(f"Transcription error: An error occurred during transcription: {str(e)}")

    def load_settings(self):
        """Load settings using the SettingsManager."""
        return SettingsManager.load_settings()

    def save_settings_to_JSON(self, settings):
        """Save complete settings using the SettingsManager."""
        SettingsManager.save_settings(settings)

    def update_settings(self, partial_settings):
        """Update specific settings without overwriting others."""
        return SettingsManager.update_settings(partial_settings)

    def get_settings_file_path(self, filename):
        """Get the settings file path using SettingsManager."""
        return SettingsManager.get_settings_file_path(filename)

    # Methods for tone preset management
    def show_tone_presets_manager(self):
        """Show the tone presets manager dialog."""
        TonePresetsManager(self)
    
    def load_current_tone_from_settings(self):
        """Load the current tone preset from settings."""
        settings = self.load_settings()
        return settings.get("current_tone", "None")
    
    def save_current_tone_to_settings(self):
        """Save the current tone preset to settings."""
        settings = self.load_settings()
        settings["current_tone"] = self.current_tone_name
        self.save_settings_to_JSON(settings)
    
    def on_tone_change(self, event):
        """Handle tone selection change in the dropdown."""
        selected_tone = event if isinstance(event, str) else self.tone_var.get()
        self.set_current_tone(selected_tone)
    
    def update_tone_selection(self):
        """Update the tone selection dropdown with current presets."""
        # Update the variable
        self.tone_var.set(self.current_tone_name)

        tone_options = ["None"] + list(self.tone_presets.keys())

        for dropdown_name in ("tone_menu", "quick_tone_menu", "compact_tone_menu"):
            dropdown = getattr(self, dropdown_name, None)
            if dropdown is None:
                continue

            self.update_option_menu_choices(dropdown, tone_options, self.on_tone_change, self.tone_var)
    
    def save_tone_presets(self, tone_presets):
        """Save tone presets using the TonePresetsManager."""
        return TonePresetsManager.save_tone_presets(self, tone_presets)

    # Add a new method to toggle banner visibility
    def toggle_banner(self):
        """Toggle the visibility of the banner image."""
        # Store notification state before changes
        had_notification = False
        if hasattr(self, 'version_checker') and self.version_checker.notification_visible:
            had_notification = True
        
        # Toggle banner state
        settings = self.load_settings()
        hide_banner = self.banner_var.get()
        
        if hide_banner:
            # Hide the banner
            self.banner_frame.grid_remove()
        else:
            # Show the banner
            self.banner_frame.grid()
        
        # Update the settings
        settings["hide_banner"] = hide_banner
        self.save_settings_to_JSON(settings)
        
        # Update window size based on new banner state
        self.update_window_size()
        self.apply_compact_mode_layout()
        
        # Ensure input elements maintain consistent width
        self._maintain_consistent_width()
        
        # Make sure presets are laid out correctly if visible
        if not self.presets_collapsed and hasattr(self, 'presets_manager'):
            self.presets_manager.refresh_presets_display()
        
        
        # Ensure the presets button is correctly positioned using grid
        if hasattr(self, 'presets_manager') and hasattr(self.presets_manager, 'presets_button'):
            if self.presets_manager.presets_button.winfo_exists():
                # Use grid (not pack) to ensure proper positioning
                self.presets_manager.presets_button.grid_configure(column=0, row=0, sticky=tk.W, padx=0, pady=2)

        # If we had a notification, make sure it's correctly positioned after layout changes
        if had_notification:
            # Need to schedule this after all geometry changes are complete
            self.after(100, self._reposition_version_notification)

    def toggle_presets(self):
        """Toggle the visibility of the presets panel."""
        # Store notification state before changes
        had_notification = False
        if hasattr(self, 'version_checker') and self.version_checker.notification_visible:
            had_notification = True
        
        if hasattr(self, 'presets_manager'):
            # Toggle presets via presets manager
            self.presets_manager.toggle_presets()
            
            # Update our local tracking of presets state
            self.presets_collapsed = self.presets_manager.presets_collapsed
            
            # Update the menu checkbox state to match
            if hasattr(self, 'presets_visible_var'):
                self.presets_visible_var.set(not self.presets_collapsed)
            
            # Update window size based on new presets state
            self.update_window_size()
            self.apply_compact_mode_layout()
            
            # Refresh presets display if they're visible
            if not self.presets_collapsed:
                self.presets_manager.refresh_presets_display()

            # If we had a notification, make sure it's correctly positioned after layout changes
            if had_notification:
                # Need to schedule this after all geometry changes are complete
                self.after(100, self._reposition_version_notification)
        
        # Ensure input elements maintain consistent width
        self._maintain_consistent_width()

    def update_buttons_for_playback(self, is_playing):
        """Update button text based on playback state."""
        try:
            # Get keyboard shortcuts from settings
            settings = self.load_settings()
            record_shortcut = "+".join(filter(None, settings["hotkeys"]["record_start_stop"]))
            play_shortcut = "+".join(filter(None, settings["hotkeys"]["play_last_audio"]))
            cancel_shortcut = "+".join(filter(None, settings["hotkeys"]["cancel_operation"]))
            
            if is_playing:
                # Set both buttons to show stop with cancel shortcut
                self.record_button.configure(text=f"Stop Audio ({cancel_shortcut})", fg_color="#d32f2f", text_color="white")
                self.submit_button.configure(text=f"Stop Audio ({cancel_shortcut})", fg_color="#d32f2f")
                if hasattr(self, 'compact_submit_button') and self.compact_submit_button.winfo_exists():
                    self.compact_submit_button.configure(text="Stop", fg_color="#d32f2f")
            else:
                # Reset buttons to normal state
                self.record_button.configure(
                    text=f"Record Mic ({record_shortcut})",
                    fg_color=self.idle_record_button_color,
                    text_color=self.idle_record_text_color
                )
                self.submit_button.configure(text=f"Play Audio ({play_shortcut})", fg_color="#058705")
                if hasattr(self, 'compact_submit_button') and self.compact_submit_button.winfo_exists():
                    self.compact_submit_button.configure(text="Play", fg_color="#058705")
        except Exception as e:
            print(f"Error updating buttons: {e}")
            # Don't raise the exception further to prevent crashes

    def handle_record_button_click(self):
        """Handle clicks on the record button based on current state."""
        if self.is_playing:
            # If audio is playing, stop it
            self.stop_playback()
        else:
            # Otherwise, toggle recording as before
            self.toggle_recording()
    
    def handle_submit_button_click(self, via_hotkey=False):
        """Handle clicks on the submit/play button based on current state."""
        if self.is_playing:
            # If audio is playing, stop it
            self.stop_playback()
        elif self.recording and via_hotkey:
            # If recording and triggered via hotkey, stop recording and play
            self.recording = False
            self.stop_recording(auto_play=True)
        else:
            # Otherwise, submit text as before
            self.submit_text()

    def on_input_device_change(self, device_name):
        """Save the selected input device in settings."""
        settings = self.load_settings()
        settings["input_device"] = device_name
        self.save_settings_to_JSON(settings)
        
    def on_primary_device_change(self, device_name):
        """Save the selected primary output device in settings."""
        settings = self.load_settings()
        settings["primary_device"] = device_name
        self.save_settings_to_JSON(settings)
        
    def on_secondary_device_change(self, device_name):
        """Save the selected secondary output device in settings."""
        settings = self.load_settings()
        settings["secondary_device"] = device_name
        self.save_settings_to_JSON(settings)

    def show_save_preset_dialog(self):
        """Show the save preset dialog."""
        self.presets_manager.show_save_preset_dialog()

    def check_version(self):
        """Run the version checker and show the result"""
        self.version_checker.check_version(True)  # True means show result even if no update available
        
    def toggle_auto_version_check(self):
        """Toggle automatic version checking and save the setting"""
        settings = self.load_settings()
        settings["auto_check_version"] = self.auto_check_version.get()
        self.save_settings_to_JSON(settings)

    def _reposition_version_notification(self):
        """Helper method to reposition version notification after layout changes"""
        if hasattr(self, 'version_checker') and self.version_checker.notification_visible:
            if hasattr(self.version_checker, 'notification_window') and self.version_checker.notification_window:
                # First ensure the notification window is visible
                self.version_checker.notification_window.deiconify()
                # Then reposition it
                self.version_checker._reposition_notification()

    def _maintain_consistent_width(self):
        """Ensure all input elements maintain consistent width after banner toggle."""
        # Force update to ensure we have current dimensions
        self.update_idletasks()
        
        # Respect the active layout instead of forcing every column to equal width.
        if hasattr(self, 'main_frame') and self.main_frame is not None:
            if self.compact_mode_var.get():
                self.main_frame.columnconfigure(0, weight=9, minsize=0)
                self.main_frame.columnconfigure(1, weight=0, minsize=120)
                self.main_frame.columnconfigure(2, weight=0, minsize=140)
                self.main_frame.columnconfigure(3, weight=0, minsize=120)
            else:
                self.main_frame.columnconfigure(0, weight=1, minsize=0)
                self.main_frame.columnconfigure(1, weight=1, minsize=0)
                self.main_frame.columnconfigure(2, weight=0, minsize=0)
                self.main_frame.columnconfigure(3, weight=0, minsize=0)
        
        # Ensure text input maintains its width
        if hasattr(self, 'text_input'):
            self.text_input.config(width=0)  # Let it be sized by the grid
        
        # Update and refresh all frames to apply the new layout
        self.update_idletasks()

    def get_available_voices(self, speech_model=None):
        """Get list of available voices, including system voices if no API key."""
        voices = []
        if self.has_api_key:
            # Add OpenAI voices
            voices.extend(
                self.get_voice_display_label(voice_id)
                for voice_id in self.get_openai_voices_for_model(speech_model)
            )
        
        # Add system voices with [System] prefix
        try:
            if hasattr(self, 'system_voices') and self.system_voices:
                for voice in self.system_voices:
                    voices.append(f"[System] {voice.name}")
            
            # If no system voices were found, add a default system voice
            if not voices:
                voices.append("[System] Default")
        except Exception as e:
            print(f"Error loading system voices: {e}")
            # Ensure we have at least one voice option
            if not voices:
                voices.append("[System] Default")
        
        return voices

    def on_voice_change(self, *args):
        """Handle voice selection change."""
        selected_voice = self.voice_var.get()
        is_system_voice = selected_voice.startswith("[System]")
        tone_supported = not is_system_voice and self.speech_model_supports_tone_instructions()
        
        # Update tone menu state based on voice type
        tone_selectors = [self.tone_menu]
        if hasattr(self, 'quick_tone_menu'):
            tone_selectors.append(self.quick_tone_menu)
        if hasattr(self, 'compact_tone_menu'):
            tone_selectors.append(self.compact_tone_menu)

        if is_system_voice:
            for tone_selector in tone_selectors:
                tone_selector.state(['disabled'])
            self.set_current_tone("None")
        elif not tone_supported:
            for tone_selector in tone_selectors:
                tone_selector.state(['disabled'])
        else:
            for tone_selector in tone_selectors:
                tone_selector.state(['!disabled'])

    def update_window_size(self):
        """Update window size based on current banner and presets state."""
        if self.compact_mode_var.get():
            current_x = self.winfo_x()
            current_y = self.winfo_y()
            if self.winfo_viewable():
                self.geometry(f"{self.COMPACT_WIDTH}x{self.COMPACT_HEIGHT}+{current_x}+{current_y}")
            else:
                self.geometry(f"{self.COMPACT_WIDTH}x{self.COMPACT_HEIGHT}")
                self.position_window_bottom_center()
            return

        # Calculate a width that preserves the current width if it's larger than default
        current_width = self.winfo_width()
        width_to_use = max(current_width, self.BASE_WIDTH)
        
        # Determine appropriate height based on current states
        banner_hidden = self.banner_var.get()
        
        if self.presets_collapsed:
            # Presets collapsed
            if banner_hidden:
                # Banner hidden, presets collapsed
                height = self.COLLAPSED_HEIGHT_NO_BANNER
            else:
                # Banner visible, presets collapsed
                height = self.COLLAPSED_HEIGHT_WITH_BANNER
        else:
            # Presets expanded
            if banner_hidden:
                # Banner hidden, presets expanded
                height = self.BASE_HEIGHT_NO_BANNER
            else:
                # Banner visible, presets expanded
                height = self.BASE_HEIGHT_WITH_BANNER
            
        # Update geometry and re-center
        self.geometry(f"{width_to_use}x{height}")
        self.center_window()

    def toggle_presets_from_menu(self):
        """Toggle presets visibility from menu, ensuring button state is updated."""
        # Toggle presets
        self.toggle_presets()
        
        # Make sure the checkbox state matches the actual state
        # (in case toggling failed for some reason)
        self.presets_visible_var.set(not self.presets_collapsed)
