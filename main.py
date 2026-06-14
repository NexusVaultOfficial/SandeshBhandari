#!/usr/bin/env python3
"""
Sandesh Launcher – Final Edition
Offline only. Profiles, version isolation, auto Java, auto Fabric.
Modern UI, no Microsoft login.
"""

import os
import json
import threading
import subprocess
import shutil
import re
import uuid
from datetime import datetime

import customtkinter as ctk
from tkinter import messagebox
import minecraft_launcher_lib
from minecraft_launcher_lib.utils import get_installed_versions
from minecraft_launcher_lib import fabric
import jdk

# ==================== CONFIG ====================
DEFAULT_BASE_DIR = os.path.expanduser("~/sandeshlauncher")
LAUNCHER_FILES_DIR = os.path.join(DEFAULT_BASE_DIR, "launcher_files")
VERSIONS_DIR = os.path.join(DEFAULT_BASE_DIR, "versions")
CONFIG_FILE = os.path.join(DEFAULT_BASE_DIR, "launcher_config.json")
JAVA_DIR = os.path.join(LAUNCHER_FILES_DIR, "java")

os.makedirs(LAUNCHER_FILES_DIR, exist_ok=True)
os.makedirs(VERSIONS_DIR, exist_ok=True)
os.makedirs(JAVA_DIR, exist_ok=True)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ==================== GLOBALS ====================
config = {}
profiles = {}
java_path = None
app = None
log_textbox = None
status_label = None
profile_combobox = None

# ==================== HELPERS ====================
def update_log(message):
    if log_textbox:
        log_textbox.configure(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_textbox.insert("end", f"[{timestamp}] {message}\n")
        log_textbox.see("end")
        log_textbox.configure(state="disabled")
        app.update_idletasks()

def set_status(text, color="#4CAF50"):
    if status_label:
        status_label.configure(text=text, text_color=color)

# ---------- Java ----------
def get_java_executable():
    global java_path
    if java_path and os.path.exists(java_path):
        return java_path
    java_cmd = shutil.which("java")
    if java_cmd:
        try:
            output = subprocess.check_output([java_cmd, "-version"], stderr=subprocess.STDOUT, text=True)
            if "21" in output or "openjdk version \"21" in output:
                update_log(f"Found Java 21 at: {java_cmd}")
                java_path = java_cmd
                return java_path
        except:
            pass
    update_log("Java 21 not found. Installing OpenJDK 21...")
    set_status("Installing Java...", "#FF9800")
    try:
        installed_path = jdk.install('21', path=JAVA_DIR, jre=False)
        java_path = os.path.join(installed_path, "bin", "java")
        if os.name == 'nt':
            java_path += ".exe"
        if os.path.exists(java_path):
            update_log(f"Java 21 installed at: {java_path}")
            return java_path
        raise Exception("Installation path not found")
    except Exception as e:
        update_log(f"Failed to auto-install Java: {e}")
        messagebox.showerror("Java Error", "Install Java 21 manually.")
        return None

# ---------- Minecraft / Fabric ----------
def is_valid_minecraft_version(version):
    return bool(re.match(r'^\d+(\.\d+){1,2}$', version))

def get_installed_version_ids(version_dir):
    try:
        return [v["id"] for v in get_installed_versions(version_dir)]
    except:
        return []

def is_version_installed(version_id, version_dir):
    return version_id in get_installed_version_ids(version_dir)

def get_installed_fabric_version(mc_version, version_dir):
    for vid in get_installed_version_ids(version_dir):
        if vid.startswith("fabric-loader") and mc_version in vid:
            return vid
    return None

def delete_corrupted_library(lib_path):
    if os.path.exists(lib_path):
        try:
            os.remove(lib_path)
            update_log(f"Deleted {lib_path}")
        except Exception as e:
            update_log(f"Delete failed: {e}")

def repair_libraries(version_dir):
    libs_dir = os.path.join(version_dir, "libraries")
    bad = os.path.join(libs_dir, "org/lwjgl/lwjgl-jemalloc/3.3.3/lwjgl-jemalloc-3.3.3-natives-linux.jar")
    if os.path.exists(bad):
        delete_corrupted_library(bad)
        update_log("Removed corrupted lwjgl-jemalloc")

def ensure_minecraft_installed(version, version_dir, retry=True):
    if not is_valid_minecraft_version(version):
        return False
    try:
        if is_version_installed(version, version_dir):
            return True
        update_log(f"Installing Vanilla {version}...")
        set_status(f"Installing {version}...", "#FF9800")
        minecraft_launcher_lib.install.install_minecraft_version(version, version_dir)
        update_log(f"✓ Vanilla {version} installed")
        return True
    except Exception as e:
        error_msg = str(e)
        if "wrong Checksum" in error_msg and retry:
            update_log("Checksum error, cleaning...")
            match = re.search(r"'(/[^']+\.jar)'", error_msg)
            if match:
                delete_corrupted_library(match.group(1))
            else:
                repair_libraries(version_dir)
            return ensure_minecraft_installed(version, version_dir, retry=False)
        set_status("✗ Vanilla install failed", "#F44336")
        return False

def ensure_fabric_installed(mc_version, version_dir):
    if not ensure_minecraft_installed(mc_version, version_dir):
        return None
    existing = get_installed_fabric_version(mc_version, version_dir)
    if existing:
        update_log(f"✓ Fabric already: {existing}")
        return existing
    update_log(f"Installing Fabric for {mc_version}...")
    set_status("Installing Fabric...", "#FF9800")
    try:
        latest = fabric.get_latest_loader_version()
        fabric_id = fabric.install_fabric(mc_version, version_dir, loader_version=latest)
        if not fabric_id:
            raise Exception("install_fabric returned None")
        if not is_version_installed(fabric_id, version_dir):
            found = get_installed_fabric_version(mc_version, version_dir)
            if found:
                fabric_id = found
            else:
                raise Exception("Fabric not found after install")
        update_log(f"✓ Fabric {fabric_id} installed")
        return fabric_id
    except Exception as e:
        set_status("✗ Fabric install failed", "#F44336")
        update_log(f"Fabric error: {e}")
        return None

# ---------- Profile & Config ----------
def load_configs():
    global config, profiles
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
        except:
            config = get_default_config()
    else:
        config = get_default_config()
    profiles = config.get("profiles", {})
    if not profiles:
        profiles["Default"] = get_default_profile()
        config["profiles"] = profiles
        save_configs()

def get_default_config():
    return {"base_dir": DEFAULT_BASE_DIR, "profiles": {}}

def get_default_profile():
    return {
        "username": "Player",
        "version": "1.21.1",
        "loader": "vanilla",
        "ram": "2048",
        "width": "854",
        "height": "480",
        "fullscreen": False
    }

def save_configs():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    update_log("Settings saved")

def refresh_profile_list():
    if profile_combobox:
        profile_combobox.configure(values=list(profiles.keys()))
        if profiles:
            profile_combobox.set(list(profiles.keys())[0])

# ---------- Profile dialogs ----------
def add_profile():
    def save_new():
        name = profile_name_entry.get().strip()
        if not name or name in profiles:
            messagebox.showerror("Error", "Invalid or duplicate name")
            return
        profiles[name] = {
            "username": username_entry.get().strip() or "Player",
            "version": version_entry.get().strip() or "1.21.1",
            "loader": loader_var.get(),
            "ram": ram_entry.get().strip() or "2048",
            "width": width_entry.get().strip() or "854",
            "height": height_entry.get().strip() or "480",
            "fullscreen": fullscreen_var.get()
        }
        save_configs()
        refresh_profile_list()
        new_window.destroy()
        update_log(f"Profile '{name}' added")
    new_window = ctk.CTkToplevel(app)
    new_window.title("Add Profile")
    new_window.geometry("450x550")
    new_window.update_idletasks()
    new_window.grab_set()
    main = ctk.CTkFrame(new_window, fg_color="transparent")
    main.pack(fill="both", expand=True, padx=20, pady=20)
    ctk.CTkLabel(main, text="Create Profile", font=("Arial", 18, "bold")).pack(pady=(0,15))
    ctk.CTkLabel(main, text="Profile Name").pack(anchor="w")
    profile_name_entry = ctk.CTkEntry(main, width=350)
    profile_name_entry.pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="Username").pack(anchor="w")
    username_entry = ctk.CTkEntry(main, width=350)
    username_entry.pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="Minecraft Version").pack(anchor="w")
    version_entry = ctk.CTkEntry(main, width=350, placeholder_text="1.21.1")
    version_entry.pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="Mod Loader").pack(anchor="w")
    loader_var = ctk.StringVar(value="vanilla")
    ctk.CTkOptionMenu(main, values=["vanilla", "fabric"], variable=loader_var).pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="RAM (MB)").pack(anchor="w")
    ram_entry = ctk.CTkEntry(main, width=350, placeholder_text="2048")
    ram_entry.pack(pady=(0,10), fill="x")
    size_frame = ctk.CTkFrame(main, fg_color="transparent")
    size_frame.pack(fill="x", pady=(0,10))
    ctk.CTkLabel(size_frame, text="Width:").pack(side="left", padx=(0,5))
    width_entry = ctk.CTkEntry(size_frame, width=80, placeholder_text="854")
    width_entry.pack(side="left", padx=(0,15))
    ctk.CTkLabel(size_frame, text="Height:").pack(side="left", padx=(0,5))
    height_entry = ctk.CTkEntry(size_frame, width=80, placeholder_text="480")
    height_entry.pack(side="left")
    fullscreen_var = ctk.BooleanVar(value=False)
    ctk.CTkCheckBox(main, text="Fullscreen", variable=fullscreen_var).pack(anchor="w", pady=(0,15))
    btn_frame = ctk.CTkFrame(main, fg_color="transparent")
    btn_frame.pack(fill="x")
    ctk.CTkButton(btn_frame, text="Cancel", command=new_window.destroy, fg_color="#555").pack(side="right", padx=5)
    ctk.CTkButton(btn_frame, text="Create", command=save_new, fg_color="#4CAF50").pack(side="right", padx=5)

def edit_profile():
    selected = profile_combobox.get()
    if not selected:
        return
    p = profiles[selected]
    def save_edits():
        profiles[selected] = {
            "username": username_entry.get().strip() or "Player",
            "version": version_entry.get().strip() or "1.21.1",
            "loader": loader_var.get(),
            "ram": ram_entry.get().strip() or "2048",
            "width": width_entry.get().strip() or "854",
            "height": height_entry.get().strip() or "480",
            "fullscreen": fullscreen_var.get()
        }
        save_configs()
        edit_window.destroy()
        update_log(f"Profile '{selected}' updated")
    edit_window = ctk.CTkToplevel(app)
    edit_window.title(f"Edit {selected}")
    edit_window.geometry("450x550")
    edit_window.update_idletasks()
    edit_window.grab_set()
    main = ctk.CTkFrame(edit_window, fg_color="transparent")
    main.pack(fill="both", expand=True, padx=20, pady=20)
    ctk.CTkLabel(main, text=f"Editing {selected}", font=("Arial", 18, "bold")).pack(pady=(0,15))
    ctk.CTkLabel(main, text="Username").pack(anchor="w")
    username_entry = ctk.CTkEntry(main, width=350)
    username_entry.insert(0, p.get("username", "Player"))
    username_entry.pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="Minecraft Version").pack(anchor="w")
    version_entry = ctk.CTkEntry(main, width=350)
    version_entry.insert(0, p.get("version", "1.21.1"))
    version_entry.pack(pady=(0,10), fill="x")
    loader_var = ctk.StringVar(value=p.get("loader", "vanilla"))
    ctk.CTkOptionMenu(main, values=["vanilla", "fabric"], variable=loader_var).pack(pady=(0,10), fill="x")
    ctk.CTkLabel(main, text="RAM (MB)").pack(anchor="w")
    ram_entry = ctk.CTkEntry(main, width=350)
    ram_entry.insert(0, p.get("ram", "2048"))
    ram_entry.pack(pady=(0,10), fill="x")
    size_frame = ctk.CTkFrame(main, fg_color="transparent")
    size_frame.pack(fill="x", pady=(0,10))
    ctk.CTkLabel(size_frame, text="Width:").pack(side="left", padx=(0,5))
    width_entry = ctk.CTkEntry(size_frame, width=80)
    width_entry.insert(0, p.get("width", "854"))
    width_entry.pack(side="left", padx=(0,15))
    ctk.CTkLabel(size_frame, text="Height:").pack(side="left", padx=(0,5))
    height_entry = ctk.CTkEntry(size_frame, width=80)
    height_entry.insert(0, p.get("height", "480"))
    height_entry.pack(side="left")
    fullscreen_var = ctk.BooleanVar(value=p.get("fullscreen", False))
    ctk.CTkCheckBox(main, text="Fullscreen", variable=fullscreen_var).pack(anchor="w", pady=(0,15))
    btn_frame = ctk.CTkFrame(main, fg_color="transparent")
    btn_frame.pack(fill="x")
    ctk.CTkButton(btn_frame, text="Cancel", command=edit_window.destroy, fg_color="#555").pack(side="right", padx=5)
    ctk.CTkButton(btn_frame, text="Save", command=save_edits, fg_color="#2196F3").pack(side="right", padx=5)

def delete_profile():
    sel = profile_combobox.get()
    if sel and messagebox.askyesno("Confirm", f"Delete '{sel}'?"):
        del profiles[sel]
        save_configs()
        refresh_profile_list()
        update_log(f"Profile '{sel}' deleted")

# ---------- Launch ----------
def launch_game():
    profile_name = profile_combobox.get()
    if not profile_name:
        messagebox.showerror("Error", "No profile")
        return
    profile = profiles.get(profile_name)
    if not profile:
        return

    username = profile.get("username", "Player")
    mc_version = profile.get("version", "1.21.1")
    loader = profile.get("loader", "vanilla")
    ram = profile.get("ram", "2048")
    width = profile.get("width", "854")
    height = profile.get("height", "480")
    fullscreen = profile.get("fullscreen", False)

    # Instance folder
    loader_str = "Fabric" if loader == "fabric" else "Vanilla"
    inst_name = f"{profile_name}-{mc_version}-{loader_str}".replace(" ", "_")
    game_dir = os.path.join(VERSIONS_DIR, inst_name)
    os.makedirs(game_dir, exist_ok=True)
    for folder in ["mods", "config", "saves", "resourcepacks", "shaderpacks", "tmp"]:
        os.makedirs(os.path.join(game_dir, folder), exist_ok=True)

    java_exe = get_java_executable()
    if not java_exe:
        return

    try:
        ram_mb = int(ram)
        if ram_mb < 512:
            ram_mb = 512
    except:
        ram_mb = 2048

    # Offline auth
    auth_data = {
        "username": username,
        "uuid": str(uuid.uuid4()),
        "token": "0"
    }
    update_log(f"Offline mode: {username}")

    # Install required version
    actual_version = mc_version
    if loader == "fabric":
        fabric_ver = ensure_fabric_installed(mc_version, game_dir)
        if not fabric_ver:
            set_status("✗ Fabric setup failed", "#F44336")
            return
        actual_version = fabric_ver
    else:
        if not ensure_minecraft_installed(mc_version, game_dir):
            return

    # Launch
    try:
        set_status("🚀 Launching...", "#FF9800")
        update_log(f"Launching {actual_version} as {username}")
        jvm_args = [f"-Xmx{ram_mb}M", f"-Xms{max(512, ram_mb // 2)}M",
                    f"-Djava.io.tmpdir={os.path.join(game_dir, 'tmp')}"]
        game_args = []
        if width and height:
            game_args.extend(["--width", str(width), "--height", str(height)])
        if fullscreen:
            game_args.append("--fullscreen")
        options = {
            "username": auth_data["username"],
            "uuid": auth_data["uuid"],
            "token": auth_data["token"],
            "jvmArguments": jvm_args,
            "gameArguments": game_args,
            "executable": java_exe
        }
        command = minecraft_launcher_lib.command.get_minecraft_command(actual_version, game_dir, options)
        process = subprocess.Popen(command)
        set_status(f"✓ Game started (PID: {process.pid})", "#4CAF50")
        update_log("✓ Minecraft launched")
    except Exception as e:
        set_status("✗ Launch failed", "#F44336")
        update_log(f"Error: {e}")

# ---------- UI ----------
def build_ui():
    global app, log_textbox, status_label, profile_combobox
    app = ctk.CTk()
    app.title("Sandesh Launcher")
    app.geometry("1000x700")
    app.minsize(800, 600)

    app.grid_rowconfigure(0, weight=1)
    app.grid_columnconfigure(0, weight=0)
    app.grid_columnconfigure(1, weight=1)

    # Sidebar
    sidebar = ctk.CTkFrame(app, width=260, corner_radius=0, fg_color="#1e1e1e")
    sidebar.grid(row=0, column=0, sticky="nsew")
    sidebar.grid_propagate(False)

    ctk.CTkLabel(sidebar, text="⛏️", font=("Arial", 48)).pack(pady=(30,0))
    ctk.CTkLabel(sidebar, text="SANDESH LAUNCHER", font=("Arial", 18, "bold")).pack()
    ctk.CTkFrame(sidebar, height=2, fg_color="#333").pack(fill="x", padx=20, pady=10)

    # Profiles
    profile_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
    profile_frame.pack(fill="x", padx=20, pady=10)
    ctk.CTkLabel(profile_frame, text="PROFILES", font=("Arial", 12, "bold"), text_color="#aaa").pack(anchor="w")
    profile_combobox = ctk.CTkComboBox(profile_frame, values=list(profiles.keys()), state="readonly", height=35)
    profile_combobox.pack(fill="x", pady=(5,10))
    if profiles:
        profile_combobox.set(list(profiles.keys())[0])

    btn_frame = ctk.CTkFrame(profile_frame, fg_color="transparent")
    btn_frame.pack(fill="x")
    ctk.CTkButton(btn_frame, text="➕ Add", command=add_profile, fg_color="#4CAF50", height=32).pack(side="left", padx=(0,5), fill="x", expand=True)
    ctk.CTkButton(btn_frame, text="✏️ Edit", command=edit_profile, fg_color="#2196F3", height=32).pack(side="left", padx=5, fill="x", expand=True)
    ctk.CTkButton(btn_frame, text="🗑️ Delete", command=delete_profile, fg_color="#F44336", height=32).pack(side="left", padx=(5,0), fill="x", expand=True)

    ctk.CTkFrame(sidebar, height=2, fg_color="#333").pack(fill="x", padx=20, pady=20)

    info_text = """📁 Each profile's game data is isolated.

~/sandeshlauncher/versions/ProfileName-X.X.X-Vanilla/
   ├── mods/
   ├── saves/
   ├── config/
   └── ...

⚙️ Java auto-installed.
🔧 Fabric auto-installed."""
    ctk.CTkLabel(sidebar, text=info_text, font=("Arial", 11), text_color="#888", justify="left", wraplength=220).pack(padx=20, pady=10)

    # Main content
    main = ctk.CTkFrame(app, fg_color="transparent")
    main.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
    main.grid_rowconfigure(1, weight=1)
    main.grid_columnconfigure(0, weight=1)

    status_card = ctk.CTkFrame(main, fg_color="#1e1e1e", corner_radius=12)
    status_card.grid(row=0, column=0, sticky="ew", pady=(0,15))
    status_label = ctk.CTkLabel(status_card, text="✓ Ready", font=("Arial", 14, "bold"), text_color="#4CAF50")
    status_label.pack(pady=15)

    log_frame = ctk.CTkFrame(main, fg_color="#1e1e1e", corner_radius=12)
    log_frame.grid(row=1, column=0, sticky="nsew")
    log_frame.grid_rowconfigure(1, weight=1)
    log_frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(log_frame, text="CONSOLE", font=("Arial", 12, "bold"), text_color="#aaa").pack(anchor="w", padx=15, pady=(10,0))
    log_textbox = ctk.CTkTextbox(log_frame, font=("Consolas", 11), fg_color="#0d0d0d", corner_radius=8)
    log_textbox.pack(fill="both", expand=True, padx=15, pady=(5,15))

    action_frame = ctk.CTkFrame(main, fg_color="transparent")
    action_frame.grid(row=2, column=0, sticky="ew", pady=(15,0))
    action_frame.grid_columnconfigure((0,1,2,3), weight=1)

    ctk.CTkButton(action_frame, text="▶ PLAY NOW", command=lambda: threading.Thread(target=launch_game, daemon=True).start(),
                  fg_color="#2196F3", font=("Arial", 16, "bold"), height=50, corner_radius=12).grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=5)

    def open_mods():
        sel = profile_combobox.get()
        if sel and sel in profiles:
            p = profiles[sel]
            loader_str = "Fabric" if p.get("loader") == "fabric" else "Vanilla"
            inst = f"{sel}-{p.get('version', '1.21.1')}-{loader_str}".replace(" ", "_")
            mods_path = os.path.join(VERSIONS_DIR, inst, "mods")
        else:
            mods_path = os.path.join(VERSIONS_DIR, "default", "mods")
        os.makedirs(mods_path, exist_ok=True)
        if os.name == 'nt':
            os.startfile(mods_path)
        else:
            subprocess.Popen(['xdg-open', mods_path])

    ctk.CTkButton(action_frame, text="📁 Mods", command=open_mods, fg_color="#4CAF50", height=40).grid(row=1, column=0, sticky="ew", padx=5, pady=5)
    ctk.CTkButton(action_frame, text="📂 Files", command=lambda: subprocess.Popen(['xdg-open', VERSIONS_DIR] if os.name != 'nt' else ['start', VERSIONS_DIR], shell=True),
                  fg_color="#FF9800", height=40).grid(row=1, column=1, sticky="ew", padx=5, pady=5)
    ctk.CTkButton(action_frame, text="🔧 Repair", command=lambda: repair_libraries(VERSIONS_DIR), fg_color="#F44336", height=40).grid(row=1, column=2, sticky="ew", padx=5, pady=5)
    ctk.CTkButton(action_frame, text="🗑️ Clear", command=lambda: log_textbox.delete("1.0", "end"), fg_color="#555", height=40).grid(row=1, column=3, sticky="ew", padx=5, pady=5)

    app.after(500, lambda: update_log(f"✓ Ready – {len(profiles)} profile(s)"))
    app.mainloop()

if __name__ == "__main__":
    load_configs()
    build_ui()
