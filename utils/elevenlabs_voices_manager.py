import base64
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
import wave

import customtkinter as ctk
import requests


class ElevenLabsVoicesManager:
    """Dialog for listing ElevenLabs voices and creating new voices with Voice Design."""

    DESIGN_MODELS = [
        ("Multilingual TTV v2", "eleven_multilingual_ttv_v2"),
        ("TTV v3", "eleven_ttv_v3"),
    ]

    DEFAULT_PREVIEW_TEXT = (
        "Hola, esta es una prueba de voz creada con Voice Design. "
        "Debe sonar natural, clara y expresiva, con suficiente personalidad para usarse en una conversacion real."
    )

    def __init__(self, parent):
        self.parent = parent
        self.previews = []
        self.played_preview_ids = []
        self.preview_files = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("ElevenLabs Voices Manager")
        self.dialog.geometry("920x720")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.configure(background="#f5f5f7")

        self.center_dialog()
        self.create_dialog()
        self.refresh_voices()

    def center_dialog(self):
        dialog_width = 920
        dialog_height = 720
        position_x = self.parent.winfo_x() + (self.parent.winfo_width() - dialog_width) // 2
        position_y = self.parent.winfo_y() + (self.parent.winfo_height() - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{position_x}+{position_y}")

    def create_dialog(self):
        main_frame = ttk.Frame(self.dialog, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(main_frame, width=310)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        left_panel.pack_propagate(False)

        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.create_voice_list_panel(left_panel)
        self.create_voice_design_panel(right_panel)

    def create_voice_list_panel(self, parent_frame):
        ttk.Label(parent_frame, text="Your ElevenLabs Voices", font=("Arial", 11, "bold")).pack(anchor=tk.W)
        ttk.Label(
            parent_frame,
            text="Voices in your ElevenLabs account. Select an item to copy its ID.",
            foreground="#666666",
            wraplength=280
        ).pack(anchor=tk.W, pady=(2, 8))

        list_frame = ttk.Frame(parent_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.voice_list = tk.Listbox(
            list_frame,
            height=18,
            bg="#ffffff",
            fg="#222222",
            selectbackground="#0078d7",
            selectforeground="#ffffff",
            font=("Arial", 9)
        )
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.voice_list.yview)
        self.voice_list.config(yscrollcommand=scrollbar.set)
        self.voice_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.voice_list.bind("<<ListboxSelect>>", self.on_voice_select)

        self.selected_voice_info = ttk.Label(parent_frame, text="", foreground="#555555", wraplength=280)
        self.selected_voice_info.pack(fill=tk.X, pady=(8, 0))

        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(button_frame, text="Refresh", command=self.refresh_voices).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="Use Selected", command=self.use_selected_voice).pack(side=tk.LEFT, padx=(8, 0))

    def create_voice_design_panel(self, parent_frame):
        ttk.Label(parent_frame, text="Voice Design", font=("Arial", 12, "bold")).pack(anchor=tk.W)
        ttk.Label(
            parent_frame,
            text="Design a new ElevenLabs voice from a text prompt, preview options, then save the best one.",
            foreground="#666666",
            wraplength=550
        ).pack(anchor=tk.W, pady=(2, 10))

        form = ttk.Frame(parent_frame)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Voice name:").grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        self.voice_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.voice_name_var).grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(form, text="Model:").grid(row=1, column=0, sticky=tk.W, pady=(0, 8))
        self.model_label_var = tk.StringVar(value=self.DESIGN_MODELS[0][0])
        ttk.OptionMenu(
            form,
            self.model_label_var,
            self.model_label_var.get(),
            *[label for label, _model_id in self.DESIGN_MODELS]
        ).grid(row=1, column=1, sticky="ew", pady=(0, 8))

        self.enhance_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form,
            text="Enhance prompt with ElevenLabs",
            variable=self.enhance_var
        ).grid(row=2, column=1, sticky=tk.W, pady=(0, 8))

        ttk.Label(form, text="Guidance:").grid(row=3, column=0, sticky=tk.W, pady=(0, 8))
        self.guidance_var = tk.DoubleVar(value=5.0)
        ttk.Scale(form, from_=0, to=20, variable=self.guidance_var, orient=tk.HORIZONTAL).grid(
            row=3,
            column=1,
            sticky="ew",
            pady=(0, 8)
        )

        ttk.Label(parent_frame, text="Voice prompt:").pack(anchor=tk.W, pady=(6, 2))
        self.prompt_text = tk.Text(parent_frame, height=7, wrap=tk.WORD, font=("Arial", 10))
        self.prompt_text.pack(fill=tk.X)
        self.prompt_text.insert(
            "1.0",
            "Una voz masculina mexicana, joven adulta, natural y cercana. "
            "Debe sonar clara, confiada y expresiva, como narrador conversacional para directos y videos."
        )

        ttk.Label(parent_frame, text="Preview text:").pack(anchor=tk.W, pady=(10, 2))
        self.preview_text = tk.Text(parent_frame, height=4, wrap=tk.WORD, font=("Arial", 10))
        self.preview_text.pack(fill=tk.X)
        self.preview_text.insert("1.0", self.DEFAULT_PREVIEW_TEXT)

        action_frame = ttk.Frame(parent_frame)
        action_frame.pack(fill=tk.X, pady=(12, 8))

        self.generate_button = ctk.CTkButton(
            action_frame,
            text="Generate Voice Previews",
            corner_radius=18,
            height=36,
            fg_color="#058705",
            hover_color="#046a38",
            command=self.generate_previews
        )
        self.generate_button.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(action_frame, mode="indeterminate", length=180)
        self.progress.pack(side=tk.LEFT, padx=(12, 0))

        self.status_label = ttk.Label(parent_frame, text="", foreground="#555555")
        self.status_label.pack(anchor=tk.W)

        self.previews_frame = ttk.LabelFrame(parent_frame, text="Generated Previews", padding=8)
        self.previews_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.render_previews()

    def selected_design_model_id(self):
        selected_label = self.model_label_var.get()
        for label, model_id in self.DESIGN_MODELS:
            if label == selected_label:
                return model_id
        return self.DESIGN_MODELS[0][1]

    def set_busy(self, busy, message=""):
        self.status_label.config(text=message)
        if busy:
            self.progress.start(10)
            self.generate_button.configure(state="disabled")
        else:
            self.progress.stop()
            self.generate_button.configure(state="normal")

    def refresh_voices(self):
        self.voice_list.delete(0, tk.END)
        self.selected_voice_info.config(text="")

        if not self.parent.has_elevenlabs_api_key:
            self.voice_list.insert(tk.END, "Add ElevenLabs API Key first")
            return

        def worker():
            try:
                voices = self.parent.fetch_elevenlabs_voice_details()
                self.dialog.after(0, lambda: self.populate_voices(voices))
            except Exception as e:
                self.dialog.after(0, lambda: messagebox.showerror("ElevenLabs Error", str(e), parent=self.dialog))

        threading.Thread(target=worker, daemon=True).start()

    def populate_voices(self, voices):
        self.voice_details = voices
        self.voice_list.delete(0, tk.END)
        for voice in voices:
            self.voice_list.insert(tk.END, voice.get("name", "Unnamed"))

        if not voices:
            self.voice_list.insert(tk.END, "No voices found")

    def on_voice_select(self, _event=None):
        selected = self.voice_list.curselection()
        if not selected or not hasattr(self, "voice_details"):
            return

        index = selected[0]
        if index >= len(self.voice_details):
            return

        voice = self.voice_details[index]
        labels = voice.get("labels") or {}
        label_text = ", ".join(f"{key}: {value}" for key, value in labels.items())
        self.selected_voice_info.config(
            text=f"ID: {voice.get('voice_id', '')}\nCategory: {voice.get('category', '')}\n{label_text}"
        )

    def use_selected_voice(self):
        selected = self.voice_list.curselection()
        if not selected or not hasattr(self, "voice_details"):
            return

        index = selected[0]
        if index >= len(self.voice_details):
            return

        voice = self.voice_details[index]
        label = f"[ElevenLabs] {voice.get('name', 'Unnamed')}"
        self.parent.elevenlabs_voice_label_to_id[label] = voice.get("voice_id", "")
        self.parent.speech_model_var.set(self.parent.get_speech_model_label("elevenlabs:eleven_flash_v2_5"))
        self.parent.update_speech_model_selection()
        self.parent.update_voice_selection()
        self.parent.voice_var.set(label)
        self.parent.on_voice_change()
        messagebox.showinfo("Voice Selected", f"Selected {voice.get('name', 'Unnamed')}.", parent=self.dialog)

    def validate_design_inputs(self):
        voice_name = self.voice_name_var.get().strip()
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        preview_text = self.preview_text.get("1.0", tk.END).strip()

        if not self.parent.has_elevenlabs_api_key:
            raise ValueError("Add your ElevenLabs API key first.")
        if not voice_name:
            raise ValueError("Voice name is required.")
        if len(prompt) < 20 or len(prompt) > 1000:
            raise ValueError("Voice prompt must be between 20 and 1000 characters.")
        if len(preview_text) < 100 or len(preview_text) > 1000:
            raise ValueError("Preview text must be between 100 and 1000 characters.")

        return voice_name, prompt, preview_text

    def generate_previews(self):
        try:
            voice_name, prompt, preview_text = self.validate_design_inputs()
        except ValueError as e:
            messagebox.showerror("Voice Design", str(e), parent=self.dialog)
            return

        self.previews = []
        self.played_preview_ids = []
        self.preview_files = {}
        self.render_previews()
        self.set_busy(True, "Generating previews with ElevenLabs...")

        def worker():
            try:
                previews = self.parent.design_elevenlabs_voice(
                    voice_description=prompt,
                    preview_text=preview_text,
                    model_id=self.selected_design_model_id(),
                    guidance_scale=round(float(self.guidance_var.get()), 2),
                    should_enhance=self.enhance_var.get()
                )
                self.dialog.after(0, lambda: self.on_previews_generated(voice_name, prompt, previews))
            except Exception as e:
                self.dialog.after(0, lambda: self.on_generation_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_previews_generated(self, voice_name, prompt, previews):
        self.set_busy(False, f"Generated {len(previews)} previews.")
        self.generated_voice_name = voice_name
        self.generated_voice_prompt = prompt
        self.previews = previews
        self.render_previews()

    def on_generation_failed(self, error):
        self.set_busy(False, "")
        messagebox.showerror("Voice Design Error", str(error), parent=self.dialog)

    def render_previews(self):
        for child in self.previews_frame.winfo_children():
            child.destroy()

        if not self.previews:
            ttk.Label(self.previews_frame, text="No previews yet. Generate previews to choose a voice.").pack(anchor=tk.W)
            return

        for index, preview in enumerate(self.previews, start=1):
            row = ttk.Frame(self.previews_frame)
            row.pack(fill=tk.X, pady=4)

            preview_id = preview.get("generated_voice_id", "")
            duration = preview.get("duration_secs", "")
            ttk.Label(row, text=f"Preview {index}  {duration}s", width=18).pack(side=tk.LEFT)
            ttk.Button(row, text="Play", command=lambda p=preview, i=index: self.play_preview(p, i)).pack(side=tk.LEFT)
            ttk.Button(row, text="Save as Voice", command=lambda p=preview: self.save_preview_as_voice(p)).pack(
                side=tk.LEFT,
                padx=(8, 0)
            )
            ttk.Label(row, text=preview_id, foreground="#777777").pack(side=tk.LEFT, padx=(10, 0))

    def play_preview(self, preview, index):
        try:
            audio_file = self.write_preview_audio_file(preview, index)
            preview_id = preview.get("generated_voice_id")
            if preview_id and preview_id not in self.played_preview_ids:
                self.played_preview_ids.append(preview_id)

            primary_index = self.parent.available_devices.get(self.parent.device_index.get(), None)
            secondary_index = (
                self.parent.available_devices.get(self.parent.device_index_2.get(), None)
                if self.parent.device_index_2.get() != "None"
                else None
            )

            if primary_index is None:
                messagebox.showerror("Audio Device", "Primary device not selected or unavailable.", parent=self.dialog)
                return

            if primary_index is not None and secondary_index is not None:
                self.parent.play_audio_multiplexed([audio_file, audio_file], [primary_index, secondary_index])
            else:
                self.parent.play_audio_multiplexed([audio_file], [primary_index])
        except Exception as e:
            messagebox.showerror("Preview Error", str(e), parent=self.dialog)

    def write_preview_audio_file(self, preview, index):
        if index in self.preview_files:
            return self.preview_files[index]

        audio_data = base64.b64decode(preview.get("audio_base_64", ""))
        output_file = Path(f"elevenlabs_voice_preview_{index}.wav")

        with wave.open(str(output_file), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(24000)
            audio_file.writeframes(audio_data)

        self.preview_files[index] = output_file
        return output_file

    def save_preview_as_voice(self, preview):
        preview_id = preview.get("generated_voice_id")
        if not preview_id:
            messagebox.showerror("Voice Design", "This preview is missing a generated voice ID.", parent=self.dialog)
            return

        self.set_busy(True, "Saving voice to your ElevenLabs account...")

        def worker():
            try:
                created_voice = self.parent.create_elevenlabs_voice_from_preview(
                    voice_name=self.generated_voice_name,
                    voice_description=self.generated_voice_prompt,
                    generated_voice_id=preview_id,
                    played_not_selected_voice_ids=[
                        voice_id for voice_id in self.played_preview_ids if voice_id != preview_id
                    ]
                )
                self.dialog.after(0, lambda: self.on_voice_created(created_voice))
            except Exception as e:
                self.dialog.after(0, lambda: self.on_generation_failed(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_voice_created(self, created_voice):
        self.set_busy(False, "Voice saved.")
        self.parent.elevenlabs_voices_cache = None
        self.parent.update_voice_selection()
        self.refresh_voices()
        messagebox.showinfo(
            "Voice Created",
            f"Saved voice: {created_voice.get('name', self.generated_voice_name)}",
            parent=self.dialog
        )
