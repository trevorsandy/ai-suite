#!/usr/bin/env python3
"""
Trevor SANDY
Last Update January 02, 2026
Copyright (c) 2025-Present by Trevor SANDY

AI-Suite uses this script for the installation command that handles the AI-Suite
functional module selection, Ollama CPU/GPU configuration, and starting Supabase and
Open WebUI Filesystem when specified.

If specified, the Supabase stack is started first. The script waits for it to initialize,
then starts open-webui filesystem tool - if specified, and then starts the AI-Suite stack.
All stacks use the same Docker Compose services project name ("ai-suite") so they appear
grouped together in Docker Desktop.

This script is also used for operation commands that start, stop, stop-ollama,
pause, unpause, update and install the AI-Suite services using the optional
--operation argument. An Ollama check is performed when it is assumed Ollama is
running from the Docker Host. If Ollama is determined to be installed but not running,
an attempt to launch the Ollama service is executed on install, start and unpause.
The check will also attempt to stop the Ollama service (in addition to stopping the
AI-Suite services) when the stop-ollama operational command is specified.

Both installation and operation commands utilize the optional --profile
arguments to specify which AI-Suite functional modules and which Ollama CPU/GPU
configuration to use. When no functional profile argument is specified, the
default functional module open-webui is used, Likewise, if no CPU/GPU configuration
profile is specified, it is assumed Ollama is being run from the Docker Host.
Multiple profile arguments (functional modules) are supported.

The --environment command allows the installation to be defined as private (default)
or public. A public install restricts the communication ports exposed to the network.

For full installation and operation details, see the AI-Suite repository README.md

This script has been adapted from start_services.py by Cole Medin

This program is free software; you can redistribute it and/or modify it under
the terms of the Apache License, Version 2.0.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import os
import sys
import datetime
import subprocess
import pathlib
import shutil
import time
import argparse
import platform
import dotenv
import tempfile
import textwrap
import re

info = {
    "name": "AI-Suite",
    "version": (0, 1, 0),
    "title": "AI-Suite installation and operation",
    "file": os.path.basename(__file__),
    "description": "A dockerized suite of AI agents in a no-code, workflow, LLM environment",
    "author": "Trevor SANDY <trevor.sandy@gmail.com>",
    "author_url": "https://github.com/trevorsandy/",
    "repository": "https://github.com/trevorsandy/ai-suite",
    "issues": "https://github.com/trevorsandy/ai-suite/issues",
    "license": "Apache License 2.0",
    "copyright": "Copyright (c) 2025-present by Trevor SANDY"
    }

def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    print("Running command:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

def launch_ollama_process():
    """Launch Ollama inference server on host"""
    cmd = " ".join([ollama_exe, "serve"])
    print("Running command:", cmd)
    if system == "Windows":
        path = tempfile.gettempdir()
        ollama_launch = os.path.join(path, "ollama_launch.vbs")
        print("Command script:", ollama_launch)
        with open(ollama_launch, 'w') as f:
            f.write(textwrap.dedent(f"""\
                ' Generated from {info.get("file")} on: {datetime.datetime.now().ctime()}
                Set WshShell = CreateObject("WScript.Shell")
                WshShell.Run "{cmd}", 0, False
                Set WshShell = Nothing
                """))
        os.startfile(ollama_launch)
    else:  # Unix-based systems (Linux, macOS)
        os.system(cmd)
    global attempted_launch
    attempted_launch = True
    print("Waiting for Ollama on host to initialize...")
    time.sleep(4)
    check_ollama_process(None)

def check_ollama_process(operation=None):
    """Check for Ollama (on host) and attempt to launch if not running."""
    if not attempted_launch:
        print("Checking for Ollama process on host...")
    ollama_running = False
    ollama_proc = ollama_app.lower()
    try:
        if system == "Windows":
            cmd = ["tasklist"]
        else:  # Unix-based systems (Linux, macOS)
            cmd = ["pgrep", "-f", ollama_proc]
        print("Running command:", " ".join(cmd))
        check_proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if system == "Windows":
            ollama_running = True if ollama_proc in check_proc.stdout.lower() else False
        else:  # Unix-based systems (Linux, macOS)
            ollama_running = check_proc.returncode == 0 if check_proc else False
    except Exception as e:
        print(f"Exception: Ollama process: {e} - assuming Ollama is not running.")

    stop_ollama = operation and operation == 'stop-ollama'

    if ollama_running:
        if stop_ollama:
            print("Stopping Ollama process on host...")
            if system == "Windows":
                cmd = ["taskkill", "/f", "/im", ollama_proc]
            else:  # Unix-based systems (Linux, macOS)
                cmd = ["ps", "-C", ollama_proc, "-o", "pid=|xargs", "kill", "-9"]
            print("Running command:", " ".join(cmd))
            os.system(" ".join(cmd))
        else:
            insert = "is now" if attempted_launch else "is"
            print(f"Ollama on host {insert} running...")
    else:
        if attempted_launch:
            print("Failed to launch Ollama on host - exiting...")
            sys.exit(1)
        print("Ollama is not running...")
        if not stop_ollama:
            print("Attempting to launch Ollama on host...")
            launch_ollama_process()

def clone_supabase_repo():
    """Clone the Supabase repository using sparse checkout if not already present."""
    if not os.path.exists("supabase"):
        print("Cloning the Supabase repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/supabase/supabase.git"
        ])
        os.chdir("supabase")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "docker"])
        run_command(["git", "checkout", "master"])
        os.chdir("..")
    else:
        print("Supabase repository already exists, updating...")
        os.chdir("supabase")
        run_command(["git", "pull"])
        os.chdir("..")

def clone_open_webui_tools_filesystem_repo():
    """Clone the Open WebUI Tools Filesystem repository using sparse checkout if
       not already present.
    """
    repo_path = os.path.join("open-webui", "tools", "servers")
    if not os.path.exists(repo_path):
        os.chdir("open-webui")
        print("Cloning the Open WebUI Tools Filesystem repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/open-webui/openapi-servers.git", "tools"
        ])
        os.chdir("tools")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "servers/filesystem"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../")
    else:
        repo_path = os.path.join("open-webui", "tools")
        print("Open WebUI Tools Filesystem repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../")

def clone_open_webui_functions_repos():
    """Clone the Open WebUI Functions repository using sparse checkout if not
       already present.
    """
    repo_path = os.path.join("open-webui", "functions", "open-webui")
    if not os.path.exists(repo_path):
        os.mkdir("open-webui/functions")
        os.chdir("open-webui/functions")
        print("Cloning the Open WebUI Functions repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/open-webui/functions.git", "open-webui"
        ])
        os.chdir("open-webui")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "functions/filters", "functions/pipes/openai"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../../")
    else:
        print("Open WebUI Functions repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../../")

    repo_path = os.path.join("open-webui", "functions", "owndev")
    if not os.path.exists(repo_path):
        os.chdir("open-webui/functions")
        print("Cloning the Open WebUI Owndev Functions repository...")
        run_command([
            "git", "clone", "--filter=blob:none", "--no-checkout",
            "https://github.com/owndev/Open-WebUI-Functions.git", "owndev"
        ])
        os.chdir("owndev")
        run_command(["git", "sparse-checkout", "init", "--cone"])
        run_command(["git", "sparse-checkout", "set", "pipelines/n8n", "filters", "docs"])
        run_command(["git", "checkout", "main"])
        os.chdir("../../../")
    else:
        print("Open WebUI Functions repository already exists, updating...")
        os.chdir(repo_path)
        run_command(["git", "pull"])
        os.chdir("../../../")

    os.chdir(repo_path)
    docs_dir = os.path.join("docs")
    retain = ["n8n-integration.md", "n8n-tool-usage-display.md"]
    os.chdir(docs_dir)
    for item in os.listdir(os.getcwd()):
        if item not in retain:
            if pathlib.Path(item).is_file():
                os.remove(item)
            elif pathlib.Path(item).is_dir():
                shutil.rmtree(item)
    os.chdir("../../../../")

def copy_dot_env_file(env_file=None):
    """Copy .env to .env in target compose file destination."""
    if env_file is not None:
        env_source_file = os.path.join(".env")
        print(f"Copying .env in {name} root to {env_file}...")
        shutil.copyfile(env_source_file, env_file)

def prepare_supabase_env():
    """Copy .env to .env in supabase/docker."""
    env_file = os.path.join("supabase", "docker", ".env")
    copy_dot_env_file(env_file)
    header = " ".join(["\n############", "\n# Docker Compose", "\n############\n\n"])
    set_variable_in_env_file(env_file, 'COMPOSE_IGNORE_ORPHANS', 'true', header)

def prepare_open_webui_tools_filesystem_env():
    """Copy .env and write compose.yaml to open-webui/tools/servers/filesystem."""
    env_file = os.path.join("open-webui", "tools", "servers", "filesystem", ".env")
    copy_dot_env_file(env_file)
    header = " ".join(["\n############", "\n# Docker Compose", "\n############\n\n"])
    set_variable_in_env_file(env_file, 'COMPOSE_IGNORE_ORPHANS', 'true', header)

    docker_compose_path = os.path.join("open-webui", "tools", "servers", "filesystem", "compose.yaml")
    print(f"Writing {docker_compose_path}...")
    with open(docker_compose_path, 'w') as f:
        f.write(textwrap.dedent("""\
                services:
                  open-webui-filesystem:
                    container_name: open-webui-filesystem
                    restart: unless-stopped
                    build:
                      context: .
                    ports:
                      - 8091:8091
                    extra_hosts:
                      - host.docker.internal:host-gateway
                    volumes:
                      - ${PROJECTS_PATH:-../shared}:/nonexistent/tmp
                    environment:
                      - PROJECTS_PATH
                """))

def destroy_ai_suite(profile=None, build=False, install=False):
    """Stop and remove AI-Suite containers and volumes (using its compose file)
       for the specified profile arguments.
    """
    insert = "and volumes for" if install else "for"
    print(f"Destroying {name} containers {insert} profile arguments: {profile}...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for argument in profile:
            cmd.extend(["--profile", argument])
    cmd.extend(["-f", "docker-compose.yml", "down"])
    if build:
        cmd.extend(["--remove-orphans"])
        if install:
            cmd.extend(["--volumes"])
    run_command(cmd)
    if build and install:
        cmd = ["docker", "volume", "prune", "--force"]
        run_command(cmd)

def operate_ai_suite(operation=None, profile=None, environment=None):
    """Start, stop, pause or pull the AI-Suite containers (using its compose file)
       for the specified profile arguments and environment argument.
    """
    if not operation:
        operation = "stop"

    with open('.operation', 'w') as f:
        f.write(operation)

    supabase =False
    open_webui = False
    if profile and operation != 'pull':
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])
        open_webui = any(p for p in profile if p in open_webui_all_profiles)    
    
    if operation == 'start':
        if supabase:
            start_supabase(environment, False)
            print("""Waiting for Supabase to initialize...""")
            time.sleep(10)
        if open_webui:
            start_open_webui_tools_filesystem(environment, False)
            time.sleep(1)
        start_ai_suite(profile, environment, False)
        return

    if operation == 'stop':
        insert = "Stopping"
    elif operation == 'pull':
        insert = "Pulling"
    else:
        insert = "Pausing" if operation == 'pause' else None
    container = "images" if operation == 'pull' else "containers"
    print(f"{insert} '{name}' {container} for profile arguments: {profile}...")
    base = ["docker", "compose", "-p", "ai-suite"]
    if supabase:
        cmd = base + ["-f", "supabase/docker/docker-compose.yml", operation]
        run_command(cmd)
    if open_webui:
        cmd = base + ["-f", "open-webui/tools/servers/filesystem/compose.yaml", operation]
        run_command(cmd)
    cmd = base
    if profile:
        for argument in profile:
            cmd.extend(["--profile", argument])
    cmd.extend(["-f", "docker-compose.yml", operation])
    run_command(cmd)
    if operation == 'pull':
        cmd = ["docker", "image", "prune", "--force"]
        run_command(cmd)

def start_built_container(compose_file=None, environment=None, build=False):
    """Start the built container services (using its compose file)."""
    cmd = ["docker", "compose", "-p", "ai-suite", "-f", compose_file]
    if environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
    if build:
        cmd.extend(["--build"])
    run_command(cmd)

def start_supabase(environment=None, build=False):
    """Start the Supabase services (using its compose file)."""
    print("Starting Supabase services...")
    compose_file = "supabase/docker/docker-compose.yml"
    start_built_container(compose_file, environment, build)

def start_open_webui_tools_filesystem(environment=None, build=False):
    """Start the Open WebUI Tools Filesystem services (using its compose file)."""
    print("Starting Open WebUI Tools Filesystem services...")
    compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    start_built_container(compose_file, environment, build)

def start_ai_suite(profile=None, environment=None, build=False):
    """Start the AI-Suite services (using its compose file) for the specified
       profile arguments and environment argument.
    """
    print(f"Starting {name} services for profile arguments: {profile}...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile:
        for argument in profile:
            cmd.extend(["--profile", argument])
    else:
        cmd.extend(["--profile", 'open-webui'])
    cmd.extend(["-f", "docker-compose.yml"])
    if environment == "private":
        cmd.extend(["-f", "docker-compose.override.private.yml"])
    if environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
    if build:
        cmd.extend(["--remove-orphans"])
    run_command(cmd)

def generate_searxng_secret_key():
    """Generate a secret key for SearXNG based on the current platform."""
    print("Checking SearXNG settings...")

    # Define paths for SearXNG settings files
    settings_path = os.path.join("searxng", "settings.yml")
    settings_base_path = os.path.join("searxng", "settings-base.yml")

    # Check if settings-base.yml exists
    if not os.path.exists(settings_base_path):
        print(f"Warning: SearXNG base settings file not found at {settings_base_path}")
        return

    # Check if settings.yml exists, if not create it from settings-base.yml
    if not os.path.exists(settings_path):
        print(f"SearXNG settings.yml not found. Creating from {settings_base_path}...")
        try:
            shutil.copyfile(settings_base_path, settings_path)
            print(f"Created {settings_path} from {settings_base_path}")
        except Exception as e:
            print(f"Exception: Create SearXNG settings.yml: {e}")
            return
    else:
        print(f"SearXNG settings.yml already exists at {settings_path}")

    print("Generating SearXNG secret key...")

    # Run the appropriate platform command
    try:
        if system == "Windows":
            print("Using Windows PowerShell to generate secret key...")
            # PowerShell command to generate a random key and replace in the settings file
            ps_command = [
                "powershell", "-Command",
                "$randomBytes = New-Object byte[] 32; " +
                "(New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes); " +
                "$secretKey = -join ($randomBytes | ForEach-Object { \"{0:x2}\" -f $_ }); " +
                "(Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml"
            ]
            subprocess.run(ps_command, check=True)

        elif system == "Darwin":  # macOS
            print("Using macOS sed command with empty string parameter...")
            # macOS sed command requires an empty string for the -i parameter
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", "", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        else:  # Linux and other Unix-like systems
            print("Using standard Linux/Unix sed command...")
            # Standard sed command for Linux
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        print("SearXNG secret key generated successfully.")

    except Exception as e:
        print(f"Exception: Generate SearXNG secret key: {e}")
        print("You may need to manually generate the secret key using the commands:")
        print("  - Linux: sed -i \"s|ultrasecretkey|$(openssl rand -hex 32)|g\" searxng/settings.yml")
        print("  - macOS: sed -i '' \"s|ultrasecretkey|$(openssl rand -hex 32)|g\" searxng/settings.yml")
        print("  - Windows (PowerShell):")
        print("    $randomBytes = New-Object byte[] 32")
        print("    (New-Object Security.Cryptography.RNGCryptoServiceProvider).GetBytes($randomBytes)")
        print("    $secretKey = -join ($randomBytes | ForEach-Object { \"{0:x2}\" -f $_ })")
        print("    (Get-Content searxng/settings.yml) -replace 'ultrasecretkey', $secretKey | Set-Content searxng/settings.yml")

def check_and_fix_docker_compose_for_searxng():
    """Check and modify docker-compose.yml for SearXNG first run."""
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        print(f"Warning: Docker Compose file not found at {docker_compose_path}")
        return

    try:
        # Default to first run
        is_first_run = True

        # Check if Docker is running and if the SearXNG container exists
        try:
            # Check if the SearXNG container is running
            container_check = subprocess.run(
                ["docker", "ps", "--filter", "name=searxng", "--format", "{{.Names}}"],
                capture_output=True, text=True, check=True
            )
            searxng_containers = container_check.stdout.strip().split('\n')

            # If SearXNG container is running, check inside for uwsgi.ini
            if any(container for container in searxng_containers if container):
                container_name = next(container for container in searxng_containers if container)
                print(f"Found running SearXNG container: {container_name}")

                # Check if uwsgi.ini exists inside the container
                container_check = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c", "[ -f /etc/searxng/uwsgi.ini ] && echo 'found' || echo 'not_found'"],
                    capture_output=True, text=True, check=False
                )

                if "found" in container_check.stdout:
                    print("Found uwsgi.ini inside the SearXNG container - not first run")
                    is_first_run = False
                else:
                    print("uwsgi.ini not found inside the SearXNG container - first run")
                    is_first_run = True
            else:
                print("No running SearXNG container found - assuming first run")
                is_first_run = True
        except Exception as e:
            print(f"Exception: Check Docker container running: {e} - assuming first run")

        # Temporarily comment out the cap_drop line on first run
        if is_first_run:
            print("First run detected for SearXNG. Temporarily commenting 'cap_drop:' directive...")
            with open(docker_compose_path, 'r+') as f:
                commented = False
                searxng_found = False
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    if not commented:
                        compare = line.strip()
                        if compare == 'searxng:':
                            searxng_found = True
                        if searxng_found:
                            if compare == 'cap_drop:':
                                line = "   #cap_drop:\n"
                            if compare == '- ALL':
                                line = "   #  - ALL  # Temporarily commented out for first run\n"
                                commented = True
                                searxng_found = False
                                print("SearXNG 'cap_drop:' directive temporarily commented...")
                    f.write(line)
            print("Note: After the first run completes successfully, uncomment 'cap_drop:' in docker-compose.yml for security.")
        else:
            # Read the docker-compose.yml file
            with open(docker_compose_path, 'r') as f:
                content = f.read()

            # Uncomment the cap_drop line
            cap_drop_comment = "   #cap_drop:\n   #  - ALL  # Temporarily commented out for first run\n"
            if cap_drop_comment in content:
                print(f"SearXNG has been initialized. Uncommenting 'cap_drop:' directive for security...")
                cap_drop = "cap_drop:\n      - ALL\n"
                modified_content = content.replace(cap_drop_comment, cap_drop)

                # Write the modified content back
                with open(docker_compose_path, 'w') as f:
                    f.write(modified_content)

    except Exception as e:
        print(f"Exception: Check/modify docker-compose.yml for SearXNG: {e}")

# Treat Selfhosted Supavisor Pooler Keeps Restarting.
# See: https://github.com/supabase/supabase/issues/30210
def convert_supabase_pooler_line_endings():
    """converting Windows line endings to Linux/Unix/MacOS line endings."""
    if system == "Windows":
        print("Converting supavisor pooler line endings...")
        WINDOWS_LINE_ENDING = b'\r\n'
        UNIX_LINE_ENDING = b'\n'
        file_path = r"supabase/docker/volumes/pooler/pooler.exs"
        with open(file_path, 'rb') as f:
            content = f.read()
        # Windows ➡ Unix
        content = content.replace(WINDOWS_LINE_ENDING, UNIX_LINE_ENDING)
        with open(file_path, 'wb') as f:
            f.write(content)

def docker_compose_include(supabase=False, filesystem=False):
    """Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml"""
    compose_file = "docker-compose.yml"
    supabase_compose_file = "supabase/docker/docker-compose.yml"
    filesystem_compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    if not os.path.exists(compose_file):
        print(f"Error: Docker Compose file '{compose_file}' not found - include skipped...")
        return
    if supabase and not os.path.exists(supabase_compose_file):
        print(f"Warning: Include file '{supabase_compose_file}' not found.")
        supabase = False
    if filesystem and not os.path.exists(filesystem_compose_file):
        print(f"Warning: Include file '{filesystem_compose_file}' not found.")
        filesystem = False
    supabase_ins = "add" if supabase else "remove"
    filesystem_ins = "add" if filesystem else "remove"
    print(f"Perform {supabase_ins} Supabase and {filesystem_ins} Filesystem 'include:' in {compose_file}...")
    include = supabase or filesystem
    compose_include = "include:\n"
    supabase_include = f"  - ./{supabase_compose_file}\n"
    filesystem_include = f"  - ./{filesystem_compose_file}\n"

    try:
        with open(compose_file, 'r') as f:
            content = f.read()

        if include:
            if compose_include in content:
                content = content.replace(compose_include, "")
            else:
                print(f"Adding 'include:' element to {compose_file}...")
                content = "\n" + content
        elif compose_include in content:
            print(f"Removing 'include:' element from {compose_file}...")

        if supabase and supabase_include not in content:
            print(f"Adding include file ./{supabase_compose_file}...")
            content = supabase_include + content
        elif not supabase and supabase_include in content:
            print(f"Removing include file ./{supabase_compose_file}...")
            content = content.replace(supabase_include, "")

        if filesystem and filesystem_include not in content:
            print(f"Adding include file ./{filesystem_compose_file}...")
            content = filesystem_include + content
        elif not filesystem and filesystem_include in content:
            print(f"Removing include file ./{filesystem_compose_file}...")
            content = content.replace(filesystem_include, "")

        if include and not compose_include in content:
            content = compose_include + content
        elif not include and compose_include in content:
            content = content.replace(compose_include + "\n", "")

        with open(compose_file, 'w') as f:
            f.write(content)
    except Exception as e:
        print(f"Exception: Set 'include:' in {compose_file}: {e}")

def set_variable_in_env_file(env_file=None, key=None , value=None, header=None):
    """Set an environment variable and add optional header in .env file"""
    if not key or not value:
        print("Error: A valid .env key or value was not specified.")
        return
    if env_file is None:
        env_file = os.path.join(".env")
    try:
        with open(env_file, 'r') as f:
            lines = f.readlines()
        for line in lines:
            line = line.strip().split('=')
            if len(line) > 1 and key == line[0].strip():
                return
    except FileNotFoundError:
        print(f"Exception: File '{env_file}' not found.")

    if dotenv.load_dotenv(env_file):
        variable = key
        if header is not None:
            with open(env_file, 'r') as f:
                content = f.read()
            if not header in content:
                variable = "".join([header, key])
        print(f"Set '{key}' to '{value}' in {env_file}...")
        dotenv.set_key(env_file, variable, value)

def update_n8n_database_settings(env_file=None, supabase=False):
    """Set POSTGRES_HOST in .env file and n8n database depends_on and
       postgres volume in Docker Compose file.
    """
    key = "POSTGRES_HOST"
    value = "db" if supabase else "postgres"
    set_variable_in_env_file(env_file, key, value, None)

    old_vol = "postgres_data" if supabase else "langfuse_postgres_data"
    compose_file = os.path.join("docker-compose.yml")
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        regex = r"\b{}\b\:".format(old_vol)
        if re.search(regex, content):
            new_vol = "langfuse_postgres_data:" if supabase else "postgres_data:"
            print(f"Set Postgres volume: from '{old_vol}' to '{new_vol}' in {compose_file}...")
            modified_content = re.sub(r"\b{}\b\:".format(old_vol), new_vol, content)
            with open(compose_file, 'w') as f:
                f.write(modified_content)

        with open(compose_file, 'r+') as f:
            updated = False
            n8n_found = False
            old_db = "postgres:" if supabase else "db:"
            new_db = f"{value}:"
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            for line in lines:
                if not updated:
                    if line == '  n8n:\n':
                        n8n_found = True
                    if line == '  n8n-runner:\n':
                        updated = True
                        n8n_found = False
                    if n8n_found:
                        if line == f'      {old_db}\n':
                            line = f"      {new_db}\n"
                            updated = True
                            n8n_found = False
                            print(f"Set n8n database depends_on: from '{old_db}' " \
                                  f"to '{new_db}' in {compose_file}...")
                f.write(line)
    except Exception as e:
        print(f"Exception: Update n8n database settings in {compose_file}: {e}")

def main():
    # Name and version information
    global name
    name = info.get("name", "placeholder")
    file = info.get("file", "placeholder.py")
    version = info.get("version", (-1, -1, -1))
    print(f"""{name} version: {".".join(map(str, version))}""")

    # Profile, environment and operation arguments
    global open_webui_all_profiles
    ollama_profiles = ['cpu', 'gpu-nvidia', 'gpu-amd']
    n8n_profiles = ["n8n", "n8n-all"]
    n8n_all_profiles = n8n_profiles + ['ai-all']
    open_webui_utils_profiles = ['open-webui-mcpo', 'open-webui-pipe']
    open_webui_profiles = ['open-webui', 'open-webui-all']
    open_webui_all_profiles = open_webui_profiles + n8n_all_profiles
    agent_all_profiles = open_webui_all_profiles + ['opencode']
    server_profiles = ['supabase', 'flowise', 'searxng', 'langfuse', 'neo4j', 'caddy']
    profiles = agent_all_profiles + open_webui_utils_profiles + server_profiles + ollama_profiles
    operations = ['stop', 'stop-ollama', 'start', 'pause', 'unpause', 'update', 'install']
    environments = ['private', 'public']
    parser = argparse.ArgumentParser(
        prog=f'{file}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(f'''\
            {info.get("description")}

            With {file}, you can install, start, stop, pause or update {name}
            with specified profile arguments (functional modules) and environment.
            ___________________________

            Syntax:

            python {file} [--profiles <arguments...>] [--environment <argument>] [--operation <argument>]

            Example commands:

            - Install profile arguments n8n and opencode...
              ...with Ollama running in the Host:
              >python {file} --profile n8n opencode

              ...with Ollama runing in Docker using CPU:
              >python {file} --profile n8n opencode cpu

              ...using GPU and in public (production) environment:
              >python {file} --profile n8n opencode --environment public

            - Perform stop (start, pause, unpause) suite operation:
              >python {file} --profile n8n opencode cpu --operation stop

            - Perform suite operation to update all modules and restart:
              >python {file} --operation update
            '''),
        epilog=textwrap.dedent(f'''\
            - Title: {info.get("title")}
            - File: {info.get("file")}
            - Author: {info.get("author")}
            - Author URL: {info.get("author_url")}
            - Repository: {info.get("repository")}
            - Report Issues: {info.get("issues")}
            - License: {info.get("license")}
            - Copyright: {info.get("copyright")}
            '''))
    parser.add_argument('-p', '--profile', type=str, nargs='+', choices=profiles,
                        help='Docker Compose Profile arguments for functional modules and Ollama'
                             'CPU/GPU options (default: open-webui - with Ollama running on Host)')
    parser.add_argument('-e', '--environment', type=str, choices=environments, default='private',
                        help='Environment arguments used by Docker Compose to expose '
                             'or restrict network communication ports (default: private)')
    parser.add_argument('-o', '--operation', type=str, choices=operations,
                        help='Docker container, volumes and image management arguments '
                              'along with argument to stop Ollama running on Host.')

    args = parser.parse_args()

    # Detect platform
    global system
    system = platform.system()
    if system == "Windows":
        print("""Detected Windows platform...""")
    elif system == "Darwin":  # macOS
        print("""Detected macOS platform...""")
    else:  # Linux and other Unix-like systems
        print("""Detected Linux/Unix platform...""")

    # Detect default profile - no arguments specified
    default_profile = False if args.profile else True

    # Check Ollama status when running Ollama in the Host
    ollama_in_host = default_profile or not \
        any(profile for profile in args.profile if profile in ollama_profiles)
    if ollama_in_host:
        global ollama_app, ollama_exe, attempted_launch
        ollama_found = False
        attempted_launch = False
        if system == "Windows":
            ollama_app = 'ollama.exe'
            ollama_exe = os.path.join(os.path.expanduser('~'), 'AppData\\Local\\Programs\\Ollama', ollama_app)
            ollama_found = os.path.exists(ollama_exe)
        else: # Unix-based systems (Linux, macOS)
            ollama_app = 'ollama'
            for ollama_path in ['/bin', '/usr/local/bin', '/usr/bin']:
                ollama_exe = os.path.join(ollama_path, ollama_app)
                if os.path.exists(ollama_exe):
                    ollama_found = True
                    break
        if not ollama_found:
            print(f"""The {ollama_app} file was not found at {ollama_exe} - exiting...""")
            sys.exit(1)
        check_ollama_process(args.operation)

    # Process operation argument
    build = False
    if args.operation:
        status = None
        if os.path.exists('.operation'):
            with open('.operation', 'r') as f:
                status = f.readline()
        if args.operation == 'stop-ollama':
            args.operation = "stop"
        if args.operation == status:
            if status == 'stop':
                insert = "Stopped"
            else:
                insert = "Paused" if status == 'pause' else "Started"
            print(f"""{name} is already {insert} - exiting...""")
            sys.exit(0)
        elif args.operation == 'unpause' and not status == 'pause':
            print(f"""{name} cannot unpause as it is not paused - exiting...""")
            sys.exit(0)
        if default_profile:
            args.profile = ['ai-all']
        if args.operation == 'update' or args.operation == 'install':
            build = True            
            install = args.operation == 'install'
            if args.operation == 'update':
                user_confirm = input(textwrap.dedent(f"""\
                    Performing an {name} update can impact its integrity.
                    Named and anonymous data volumes will be deleted.
                    [Type 'Got-It' to continue]: 
                    """))
                if len(user_confirm) == 0 or user_confirm.lower() != 'got-it':
                    print(f"""Received [{user_confirm}].""") if user_confirm else None
                    print(f"""{name} update was not confirmed - exiting...""")
                    sys.exit(0)
            args.operation = 'pull'
            insert = "Installing" if install == 'install' else "Updating"
            if default_profile:
                print(f"""{insert} all container images including Ollama...""")
                args.profile.extend(["cpu"])
            else:
                print(f"""{insert} container images for {args.profile}...""")
            docker_compose_include(True, True)
            destroy_ai_suite(args.profile, build, install)
        operate_ai_suite(args.operation, args.profile, args.environment)
        if not build:
            sys.exit(0)
    os.remove('.operation') if os.path.exists('.operation') else None

    # Manually set default profile argument
    if default_profile:
        if build:
            args.profile.remove('cpu') if 'cpu' in args.profile else None
        else:
            args.profile = ['open-webui']

    env_file = os.path.join(".env")

    # Set default projects path in .env file
    if any(profile for profile in args.profile if profile in agent_all_profiles):
        key = "PROJECTS_PATH"
        value = os.path.join(os.path.expanduser('~'), "projects")
        header = " ".join(["\n############", "\n# Projects", "\n############\n\n"])
        set_variable_in_env_file(env_file, key, value, header)

    # Setup Supabase
    if any(profile for profile in args.profile if profile == 'supabase'):
        if not any(profile for profile in args.profile if profile in n8n_all_profiles):
            print(f"""Profile argument 'supabase' requires argument in {n8n_all_profiles}
                      - removing 'supabase'...""")
            args.profile.remove('supabase')
    supabase = \
        any(profile for profile in args.profile if profile in ['supabase', 'ai-all'])
    if supabase:
        args.profile.remove('supabase') if 'supabase' in args.profile else None
        clone_supabase_repo()
        convert_supabase_pooler_line_endings()

    if any(profile for profile in args.profile if profile in n8n_all_profiles):
        update_n8n_database_settings(env_file, supabase)

    if supabase:
        prepare_supabase_env()
    elif 'langfuse' in args.profile:
        print("""Profile argument 'langfuse' requires Supabase - removing 'langfuse'...'""")
        args.profile.remove('langfuse')

    # Generate SearXNG secret key and check docker-compose.yml
    if any(profile for profile in args.profile if profile in ['searxng', 'ai-all']):
        generate_searxng_secret_key()
        check_and_fix_docker_compose_for_searxng()

    # Setup Open WebUI Functions and Tools Filesystem repos
    open_webui = \
        any(profile for profile in args.profile if profile in open_webui_all_profiles)
    if open_webui:
        clone_open_webui_functions_repos()
        clone_open_webui_tools_filesystem_repo()
        prepare_open_webui_tools_filesystem_env()

    # Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml
    docker_compose_include(supabase, open_webui)

    # Stop and remove AI-Suite containers
    if not build:
        destroy_ai_suite(args.profile, False, False)

    # Start Supabase first
    if supabase:
        start_supabase(args.environment, build)
        # Give Supabase some time to initialize
        print("""Waiting for Supabase to initialize...""")
        time.sleep(10)

    # Start Open WebUI Tools Filesystem
    if open_webui:
        start_open_webui_tools_filesystem(args.environment, build)
        time.sleep(1)

    # Check if open-webui-mcpo specified with required profile arguments, else remove open-webui-mcpo
    if any(profile for profile in args.profile if profile == 'open-webui-mcpo'):
        if not any(profile for profile in args.profile if profile in open_webui_all_profiles):
            print(f"""Profile argument 'open-webui-mcpo' requires argument in
                      {open_webui_all_profiles} - removing 'open-webui-mcpo'...""")
            args.profile.remove('open-webui-mcpo')

    # Check if open-webui-pipe specified with required profile arguments, else remove open-webui-pipe
    if any(profile for profile in args.profile if profile == 'open-webui-pipe'):
        if not any(profile for profile in args.profile if profile in open_webui_all_profiles):
            print(f"""Profile argument 'open-webui-pipe' requires argument in
                      {open_webui_all_profiles} - removing 'open-webui-pipe'...""")
            args.profile.remove('open-webui-pipe')

    # Check if profile arguments n8n and open-webui specified, remove redundant open-webui
    if any(profile for profile in args.profile if profile == 'n8n'):
        if any(profile for profile in args.profile if profile == 'open-webui'):
            print("""Profiles arguments 'n8n' and 'open-webui' detected - removing 'open-webui'...""")
            args.profile.remove('open-webui')

    # Check if more than one Ollama CPU/GPU argument specified, use first argument
    if any(profile for profile in args.profile if profile in ollama_profiles):
        first_argument = False
        for ollama_profile in ollama_profiles:
            if not first_argument:
                if any(profile for profile in args.profile if profile == ollama_profile):
                    print(f"""{name} will use Ollama CPU/GPU profile argument '{ollama_profile}'...""")
                    first_argument = True
            else:
                args.profile.remove(ollama_profile)

    # Then start the AI-Suite services
    start_ai_suite(args.profile, args.environment, build)

    with open('.operation', 'w') as f:
        f.write('start')

if __name__ == "__main__":
    main()
