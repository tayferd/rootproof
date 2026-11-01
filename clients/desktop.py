"""Rootproof local document desk. Launch with python -m clients.desktop."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk
from uuid import UUID

from clients.document_workflow import LocalAPI, fingerprint, verify_document

BG = "#f2f5f4"
INK = "#19322d"
MUTED = "#566a64"
ACCENT = "#17624e"


class DocumentDesk:
    def __init__(self, root: tk.Tk, api: LocalAPI | None = None):
        self.root, self.api = root, api or LocalAPI()
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.busy = False
        self.selected = None
        self.current_registration = None
        self.verification_file = None
        self.verification_receipt = None
        self.actions = []
        root.title("Rootproof — Document Desk")
        root.geometry("1040x780")
        root.minsize(940, 720)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._styles()
        self._build()
        self._buttons()

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 27, "bold"))
        style.configure("Heading.TLabel", font=("Segoe UI", 15, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("TButton", font=("Segoe UI", 10), padding=(14, 9))
        style.configure("Accent.TButton", background=ACCENT, foreground="white")
        style.map("Accent.TButton", background=[("active", "#114b3b"), ("disabled", "#d1dad6")])
        style.configure("TCheckbutton", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=(20, 10))

    def _button(self, parent, text, command, accent=False):
        button = ttk.Button(parent, text=text, command=command, style="Accent.TButton" if accent else "TButton")
        self.actions.append(button)
        return button

    def _build(self):
        shell = ttk.Frame(self.root, padding=28)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Rootproof", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Document Desk  /  Local preview", style="Muted.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Label(shell, text="Choose a document. Keep its contents private. Save evidence you can check later.", wraplength=920).pack(anchor="w", pady=(0, 18))
        self.tabs = ttk.Notebook(shell)
        self.tabs.pack(fill="both", expand=True)
        registration = ttk.Frame(self.tabs, padding=20)
        verification = ttk.Frame(self.tabs, padding=20)
        self.tabs.add(registration, text="Register a document")
        self.tabs.add(verification, text="Check a receipt offline")
        registration.columnconfigure(0, weight=1)
        registration.columnconfigure(1, weight=1)
        left = ttk.Frame(registration, padding=(0, 0, 22, 0))
        right = ttk.Frame(registration, padding=(22, 0, 0, 0))
        left.grid(row=0, column=0, sticky="nsew")
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(left, text="1  Select and hash", style="Heading.TLabel").pack(anchor="w", pady=(0, 14))
        self._button(left, "Choose document…", self.choose_document).pack(anchor="w")
        self.file_name = tk.StringVar(value="No document selected")
        ttk.Label(left, textvariable=self.file_name, wraplength=390).pack(anchor="w", pady=(12, 16))
        ttk.Label(left, text="SHA-256 fingerprint", style="Muted.TLabel").pack(anchor="w")
        self.digest_text = tk.Text(left, height=3, width=38, font=("Consolas", 10), wrap="char", relief="flat", bg="white", fg=INK, padx=10, pady=10)
        self.digest_text.pack(fill="x", pady=(6, 14))
        self.digest_text.configure(state="disabled")
        self.include_name = tk.BooleanVar(value=True)
        self.name_checkbox = ttk.Checkbutton(left, text="Include the file name in metadata", variable=self.include_name)
        self.name_checkbox.pack(anchor="w", pady=(0, 12))
        ttk.Label(left, text="Only the hash and chosen metadata go to your local API. Document contents stay on this computer.", style="Muted.TLabel", wraplength=380).pack(anchor="w", pady=(0, 14))
        self.register_button = self._button(left, "Register fingerprint", self.register, accent=True)
        self.register_button.pack(anchor="w")
        ttk.Label(left, text="Repeated registration creates a new record. This tool does not back up or restore files.", style="Muted.TLabel", wraplength=380).pack(anchor="w", pady=(14, 0))

        ttk.Label(right, text="2  Save your evidence", style="Heading.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Label(right, text="Registration ID", style="Muted.TLabel").pack(anchor="w")
        self.identifier = tk.StringVar()
        self.id_entry = ttk.Entry(right, textvariable=self.identifier, font=("Consolas", 10), width=38)
        self.id_entry.pack(fill="x", pady=(6, 10))
        row = ttk.Frame(right)
        row.pack(anchor="w", pady=(0, 14))
        self._button(row, "Refresh registration", self.refresh).pack(side="left")
        self._button(row, "Copy ID", self.copy_id).pack(side="left", padx=(8, 0))
        self.registration_state = tk.StringVar(value="Register a document or paste an existing ID.")
        ttk.Label(right, textvariable=self.registration_state, wraplength=385, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 12))
        self.registration_info = tk.StringVar(value="A saved registration starts pending. An inclusion receipt becomes available after batch processing.")
        ttk.Label(right, textvariable=self.registration_info, style="Muted.TLabel", wraplength=385).pack(anchor="w", pady=(0, 16))
        self._button(right, "Save registration details…", self.save_registration).pack(anchor="w", pady=(0, 8))
        self._button(right, "Save inclusion receipt…", self.save_receipt, accent=True).pack(anchor="w")
        ttk.Label(right, text="Receipts currently contain an inclusion proof without independent timestamp confirmations. Separate timestamp experiments are not included.", style="Muted.TLabel", wraplength=385).pack(anchor="w", pady=(14, 0))

        ttk.Label(verification, text="Check a file against its saved receipt", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(verification, text="This check runs locally. The API and PostgreSQL do not need to be running.", style="Muted.TLabel", wraplength=860).pack(anchor="w", pady=(0, 20))
        self._button(verification, "Choose file to check…", self.choose_verification_file).pack(anchor="w")
        self.verify_file_label = tk.StringVar(value="No file selected")
        ttk.Label(verification, textvariable=self.verify_file_label, wraplength=850).pack(anchor="w", pady=(8, 16))
        self._button(verification, "Choose receipt JSON…", self.choose_verification_receipt).pack(anchor="w")
        self.verify_receipt_label = tk.StringVar(value="No receipt selected")
        ttk.Label(verification, textvariable=self.verify_receipt_label, wraplength=850).pack(anchor="w", pady=(8, 18))
        self.verify_button = self._button(verification, "Check file and inclusion proof", self.verify, accent=True)
        self.verify_button.pack(anchor="w", pady=(0, 20))
        self.verify_heading = tk.StringVar(value="Ready when you are")
        ttk.Label(verification, textvariable=self.verify_heading, font=("Segoe UI", 17, "bold")).pack(anchor="w", pady=(0, 8))
        self.verify_details = tk.StringVar(value="A matching proof establishes consistency with the root in the receipt. It does not establish a trustworthy timestamp.")
        ttk.Label(verification, textvariable=self.verify_details, wraplength=850).pack(anchor="w")

        self.status = tk.StringVar(value="Ready  ·  Local API: http://127.0.0.1:8000")
        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(18, 0))

    def _buttons(self):
        for button in self.actions:
            button.configure(state="disabled" if self.busy else "normal")
        self.name_checkbox.configure(state="disabled" if self.busy else "normal")
        self.id_entry.configure(state="disabled" if self.busy else "normal")
        if self.selected is None:
            self.register_button.configure(state="disabled")
        if self.verification_file is None or self.verification_receipt is None:
            self.verify_button.configure(state="disabled")

    def _run(self, message, work, success, failure=None):
        if self.busy:
            return
        self.busy = True
        self.status.set(message)
        self._buttons()
        future = self.pool.submit(work)

        def poll():
            if not future.done():
                self.root.after(80, poll)
                return
            self.busy = False
            self._buttons()
            try:
                result = future.result()
                success(result)
            except (OSError, ValueError) as error:
                self.status.set(str(error))
                if failure is not None:
                    failure(str(error))
            except Exception:
                message = "The operation could not finish. Check your local setup and try again."
                self.status.set(message)
                if failure is not None:
                    failure(message)

        self.root.after(80, poll)

    def choose_document(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose a document to hash locally")
        if not chosen:
            return
        self.selected = None
        self.current_registration = None
        self.identifier.set("")
        self.registration_state.set("New document · not registered")
        self.registration_info.set("Hash the document, then register its fingerprint.")
        self.file_name.set(Path(chosen).name)
        self.digest_text.configure(state="normal")
        self.digest_text.delete("1.0", "end")
        self.digest_text.configure(state="disabled")
        self._run("Hashing document locally…", lambda: fingerprint(Path(chosen)), self._hashed)

    def _hashed(self, selected):
        self.selected = selected
        self.digest_text.configure(state="normal")
        self.digest_text.insert("1.0", selected.digest)
        self.digest_text.configure(state="disabled")
        self.status.set("Fingerprint ready. Nothing has been registered yet.")
        self._buttons()

    def register(self):
        if self.selected is not None:
            selected, include = self.selected, self.include_name.get()
            self._run("Registering fingerprint with the local API…", lambda: self.api.register(selected, include), self._registered)

    def _registered(self, record):
        self.current_registration = record
        self.identifier.set(record["id"])
        sealed = record["status"] == "sealed_pending_witnesses"
        self.registration_state.set("Included in a batch · timestamp pending" if sealed else "Saved · awaiting batch processing")
        details = f"Recorded by server: {record.get('received_at', 'Unavailable')}"
        if sealed:
            details += f"\nBatch: {record.get('batch_id')}\nPosition: {record.get('batch_position')}"
        else:
            details += "\nSave the registration details now. Refresh after the operator seals a batch."
        self.registration_info.set(details)
        self.status.set("Registration loaded. Document contents have stayed local.")

    def _id(self):
        try:
            return UUID(self.identifier.get().strip())
        except ValueError:
            self.status.set("Enter a valid registration ID first.")
            return None

    def refresh(self):
        identifier = self._id()
        if identifier is not None:
            self._run("Fetching registration…", lambda: self.api.lookup(identifier), self._registered)

    def copy_id(self):
        identifier = self._id()
        if identifier is not None:
            self.root.clipboard_clear()
            self.root.clipboard_append(str(identifier))
            self.status.set("Registration ID copied.")

    def save_registration(self):
        identifier = self._id()
        if identifier is None:
            return
        destination = filedialog.asksaveasfilename(parent=self.root, title="Save registration details (not an inclusion proof)", initialfile=f"registration-{identifier}.json", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not destination:
            return

        def save():
            record = self.api.lookup(identifier)
            import json
            Path(destination).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            return record

        self._run("Saving registration details…", save, lambda _: self.status.set("Registration details saved. This file is not an inclusion receipt."))

    def save_receipt(self):
        identifier = self._id()
        if identifier is None:
            return
        destination = filedialog.asksaveasfilename(parent=self.root, title="Save inclusion receipt", initialfile=f"rootproof-{identifier}.json", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not destination:
            return

        def save():
            content = self.api.receipt(identifier)
            Path(destination).write_bytes(content)

        self._run("Downloading inclusion receipt…", save, lambda _: self.status.set("Inclusion receipt saved. Independent timestamp evidence is not included."))

    def choose_verification_file(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose the file to check")
        if chosen:
            self.verification_file = Path(chosen)
            self.verify_file_label.set(chosen)
            self._reset_verification()

    def choose_verification_receipt(self):
        chosen = filedialog.askopenfilename(parent=self.root, title="Choose a Rootproof inclusion receipt", filetypes=[("JSON receipts", "*.json"), ("All files", "*.*")])
        if chosen:
            self.verification_receipt = Path(chosen)
            self.verify_receipt_label.set(chosen)
            self._reset_verification()

    def _reset_verification(self):
        self.verify_heading.set("Ready to check")
        self.verify_details.set("Select both the original file and its inclusion receipt.")
        self._buttons()

    def verify(self):
        path, receipt = self.verification_file, self.verification_receipt
        if path is not None and receipt is not None:
            self.verify_heading.set("Checking…")
            self.verify_details.set("")
            self._run("Checking file and receipt locally…", lambda: verify_document(path, receipt), self._verified, self._verification_failed)

    def _verification_failed(self, message):
        self.verify_heading.set("Check could not finish")
        self.verify_details.set(message)

    def _verified(self, result):
        self.verify_heading.set("File and proof match · unwitnessed" if result.status == "valid_unwitnessed" else "Verification failed")
        self.verify_details.set(
            f"File matches registered digest: {'Yes' if result.file_matches else 'No'}\n"
            f"Inclusion proof matches receipt root: {'Yes' if result.inclusion_valid else 'No'}\n"
            "Independent timestamp: not verified\n\n"
            "This checks consistency with the supplied receipt root. It does not authenticate the root's history."
        )
        self.status.set("Offline check complete. No API or database connection was used.")

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    DocumentDesk(root)
    root.mainloop()


if __name__ == "__main__":
    main()
