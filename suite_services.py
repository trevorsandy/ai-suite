#!/usr/bin/env python3
"""
Trevor SANDY
Last Update January 11, 2026
Copyright (c) 2025-Present by Trevor SANDY

AI-Suite uses this script for the installation command that handles the AI-Suite
functional module selection, llama CPU/GPU configuration, and starting Supabase
and Open WebUI Filesystem when specified.

If specified, the Supabase stack is started first. The script waits for it to initialize,
then starts open-webui filesystem tool - if specified, and then starts the AI-Suite
stack. All stacks use the same Docker Compose services project name ("ai-suite")
so they appear grouped together in Docker Desktop.

This script is also used for operation commands that start, stop, stop-llama,
pause, unpause, update and install the AI-Suite services using the optional
--operation argument. A llama (Ollama/Llama.cpp) check is performed when it is
assumed llama is running from the Docker Host. If llama is determined to be installed
but not running, an attempt to launch the Ollama/Llama.cpp service is executed
on install, start and unpause. The check will also attempt to stop the llama service
(in addition to stopping the AI-Suite services) when the stop-llama operational
command is specified.

Both installation and operation commands utilize the optional --profile
arguments to specify which AI-Suite functional modules and which llama CPU/GPU
configuration to use. When no functional profile argument is specified, the
default functional module open-webui is used, Likewise, if no CPU/GPU configuration
profile is specified, it is assumed llama is being run from the Docker Host.
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
import argparse
import datetime
import dotenv
import pathlib
import platform
import re
import shutil
import subprocess
import textwrap
import time

# Info attributes
INFO = {
    "name"       : "AI-Suite",
    "version"    : (0, 4, 0),
    "title"      : "AI-Suite installation and operation",
    "file"       : os.path.basename(__file__),
    "description": "A dockerized suite of AI agents in a no-code, workflow, LLM environment",
    "author"     : "Trevor SANDY <trevor.sandy@gmail.com>",
    "author_url" : "https://github.com/trevorsandy/",
    "repository" : "https://github.com/trevorsandy/ai-suite",
    "issues"     : "https://github.com/trevorsandy/ai-suite/issues",
    "license"    : "Apache License 2.0",
    "copyright"  : "Copyright (c) 2025-present by Trevor SANDY"
}

def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    print("Running command:", " ".join(cmd))
    try:
        completed = subprocess.run(cmd, cwd=cwd, check=True)
        if completed.returncode != 0:
            print(f"Command Error: {completed.stderr}")
    except Exception as e:
        print(f"Command Exception: {e}.")

def launch_llama_process(args):
    """Launch Ollama/Llama.cpp server on the host"""
    llama_log_dir = "llama.cpp" if llama_cpp else ""
    llama_log_path = os.path.join(os.getcwd(), llama_log_dir, 'llama_start.log')
    llama_log = "".join(['>', llama_log_path, ' 2>&1'])
    if system == "Windows":
        win = "".join(['/c,"', llama_exe])
        cmd = ['powershell', '-Command', 'Start-Process cmd -Args', win, args,
               "".join([llama_log, '"']), '-WindowStyle Hidden']
    else:  # Unix-based systems (Linux, macOS)
        cmd = [llama_exe, args, llama_log]
    print("Running command:", " ".join(cmd))
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if completed.returncode != 0:
            print(f"Error: {llama} process: {completed.stderr}")
    except Exception as e:
        print(f"Exception: {llama} process: {e} - assuming {llama} did not start.")
    global attempted_launch
    attempted_launch = True
    print(f"Waiting for {llama} on host to initialize...")
    time.sleep(4)
    check_llama_process(None, {})

def check_llama_cpp_model(operation, env_vars, using_hf):
    """Check if the specified llama.cpp model exists, offer to download if not"""
    model_path = normalize_path(env_vars.get('LLAMACPP_MODEL_PATH'))
    model_name = env_vars.get('LLAMACPP_MODEL_NAME', 'gemma-4b')
    if not os.path.exists(model_path):
        proceed = True
        # Dictionary of common llama.cpp model names and their download identifiers
        llama_cpp_models = {
            "LLAMACPP_MODEL_GEMMA": "LLAMACPP_MODEL_GEMMA_ID",
            "LLAMACPP_MODEL_DEEPSEEK": "LLAMACPP_MODEL_DEEPSEEK_ID",
            "LLAMACPP_MODEL_MISTRAL": "LLAMACPP_MODEL_MISTRAL_ID",
            "LLAMACPP_MODEL_LLAMA": "LLAMACPP_MODEL_LLAMA_ID",
            "LLAMACPP_MODEL_QWEN": "LLAMACPP_MODEL_QWEN_ID",
            "LLAMACPP_MODEL_USER": "LLAMACPP_MODEL_USER_ID"
        }
        if operation != 'install' and not using_hf:
            print(f"{llama} model not found at {model_path}")
            response = input(f"Would you like to download the {model_name} model now? (y/n): ")
            proceed = response.lower() == 'y'
        if proceed:
            model_dir = os.path.dirname(model_path)
            if not os.path.exists(model_dir):
                os.makedirs(model_dir,exist_ok=True)
            best_match = None
            best_match_key = None
            best_match_score = 0
            for model_key in llama_cpp_models.keys():
                known_model = env_vars.get(model_key)
                if not known_model:
                    continue
                match_score = sum(c1 == c2 for c1, c2 in zip(model_name.lower(), known_model.lower()))
                if match_score > best_match_score:
                    best_match = known_model
                    best_match_key = model_key
                    best_match_score = match_score
            if best_match and best_match_key and best_match_score > len(best_match) / 2:
                print(f"Using {llama} model: {best_match}...")
                return env_vars.get(llama_cpp_models[best_match_key])
            else:
                print(f"Error: Unknown model '{model_name}', download model manually - Models:")
                proceed = False
        else: # User elected not to proceed
            print("Notice: Download the model manually and update your .env file - Models:")
        if not proceed:
            llama_server_args = env_vars.get('LLAMACPP_SERVER_ARGS')
            for model_key, model_value in llama_cpp_models.items():
                model = env_vars.get(model_key)
                model_id = env_vars.get(model_value)
                print(f"- {model} command: {llama_app} {llama_server_args} {model_id}")
            return None
    print(f"Using {llama} model: {model_name}...")
    return model_name

def check_llama_process(operation=None, env_vars={}):
    """Check for Ollama/Llama.cpp (on host) and attempt to launch if not running."""
    if not attempted_launch:
        print(f"Checking for {llama} process on host...")
    llama_running = False
    llama_proc = llama_app.lower()
    try:
        if system == "Windows":
            cmd = ["tasklist"]
        else:  # Unix-based systems (Linux, macOS)
            cmd = ["pgrep", "-f", llama_proc]
        print("Running command:", " ".join(cmd))
        completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if system == "Windows":
            llama_running = True if llama_proc in completed.stdout.lower() else False
        else:  # Unix-based systems (Linux, macOS)
            llama_running = completed.returncode == 0 if completed else False
    except Exception as e:
        print(f"Exception: {llama} process: {e} - assuming {llama} is not running.")

    stop_llama = operation == 'stop-llama'
    start_llama = not stop_llama and operation in ['start', 'unpause']

    if llama_running:
        if stop_llama:
            print(f"Stopping {llama} process on host...")
            if system == "Windows":
                cmd = ["taskkill", "/f", "/im", llama_proc]
            else:  # Unix-based systems (Linux, macOS)
                cmd = ["ps", "-C", llama_proc, "-o", "pid=|xargs", "kill", "-9"]
            print("Running command:", " ".join(cmd))
            os.system(" ".join(cmd))
        else:
            insert = "is now" if attempted_launch else "is"
            print(f"{llama} on host {insert} running...")
    else:
        if attempted_launch:
            print(f"Failed to launch {llama} on host - exiting...")
            sys.exit(1)
        print(f"{llama} is not running...")
        if start_llama:
            if llama_found:
                print(f"Attempting to launch {llama} on host...")
                llama_args = []
                if llama_cpp:
                    regex = r"(?:-hf|--hf-file|-m|--model|--model-url)"
                    llama_hf_repo = env_vars.get('LLAMA_ARG_HF_REPO')
                    llama_server_args = env_vars.get('LLAMACPP_SERVER_ARGS')
                    llama_models_dir = normalize_path(env_vars.get('LLAMACPP_MODELS_DIR'))
                    llama_model_arg = re.search(regex, llama_server_args)
                    if llama_models_dir:
                        if os.path.isdir(llama_models_dir):
                            default_models_dir = normalize_path(os.path.join('llama.cpp','models'))
                            if llama_models_dir != default_models_dir and os.listdir(llama_models_dir):
                                regex = r"\b{--models-dir}\b"
                                if not re.search(regex, llama_server_args):
                                    llama_args.extend(["--models-dir", llama_models_dir])
                        else:
                            print(f"Error: Models directory {llama_models_dir} does not exist.")
                    can_download = True if llama_hf_repo else False
                    if llama_server_args:
                        llama_args.extend([llama_server_args])
                    if not llama_hf_repo:
                        using_hf = False
                        if llama_model_arg:
                            using_hf = llama_model_arg.group() in ['-hf', '--hf-file']
                            can_download = llama_model_arg.group() not in ['-m', '--model']
                        llama_model = check_llama_cpp_model(operation, env_vars, using_hf)
                        if llama_model:
                            if not llama_model_arg:
                                llama_args.extend(['-hf'])
                            llama_args.extend([llama_model])
                        elif operation == 'install':
                            sys.exit(1)
                    if can_download and operation in ['install', 'update']:
                        print(f"""Configured to download {llama} model (this may take a while).\n
                                  Check container log for download progress...""")
                else:
                    llama_server_args = env_vars.get('OLLAMA_SERVER_ARGS')
                    if llama_server_args:
                        llama_args.extend([llama_server_args])

                args = " ".join(llama_args)
                launch_llama_process(args)
            else:
                print(textwrap.dedent(f"""\
                    Error: The {llama_app} file was not found at {llama_exe}.
                    If {llama} is installed in a non-standard location, you can set the LLAMA_PATH
                    environment variable with its full path (including the {llama} file) in .env and
                    re-run {info.get("file")} - exiting...
                    """))
                sys.exit(1)

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

def prepare_supabase_env(env_vars):
    """Write env_vars to .env in supabase/docker."""
    env_file = os.path.join("supabase", "docker", ".env")
    built_env_vars = env_vars
    built_env_vars['COMPOSE_IGNORE_ORPHANS'] = 'true'
    write_dotenv_file(env_file, built_env_vars)

def prepare_open_webui_tools_filesystem_env(env_vars):
    """Write env_vars to .env and compose.yaml to open-webui/tools/servers/filesystem."""
    env_file = os.path.join("open-webui", "tools", "servers", "filesystem", ".env")
    built_env_vars = env_vars
    built_env_vars['COMPOSE_IGNORE_ORPHANS'] = 'true'
    write_dotenv_file(env_file, built_env_vars)

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

def destroy_ai_suite(profile, install):
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
    if install:
        cmd.extend(["--volumes"])
    run_command(cmd)
    if install:
        cmd = ["docker", "volume", "prune", "--force"]
        run_command(cmd)

def operate_ai_suite(operation, profile, environment, env_vars):
    """Start, stop, pause or pull the AI-Suite containers (using its compose file)
       for the specified profile arguments and environment argument.
    """
    if not operation:
        operation = "stop"

    with open('.operation', 'w') as f:
        f.write(operation + ':' + llama.lower())

    supabase = False
    open_webui = False
    if profile and operation != 'pull':
        supabase = any(p for p in profile if p in ['supabase', 'ai-all'])
        open_webui = any(p for p in profile if p in open_webui_all_profiles)

    if operation == 'start' and environment:
        env_vars['POSTGRES_HOST'] = "db" if supabase else "postgres"
        load_dotenv_vars(env_vars)
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
    """Start the locally built container services (using its compose file)."""
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
                container_check_cmd = \
                    "[ -f /etc/searxng/uwsgi.ini ] && echo 'found' || echo 'not_found'"
                container_check = subprocess.run(
                    ["docker", "exec", container_name, "sh", "-c", container_check_cmd],
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
    """Convert Windows line endings to Linux/Unix/MacOS line endings."""
    if system == "Windows":
        print("Converting supavisor pooler line endings...")
        CR_LF = b'\r\n'
        LF = b'\n'
        file_path = "supabase/docker/volumes/pooler/pooler.exs"
        with open(file_path, 'rb') as f:
            content = f.read()
        modified_content = content.replace(CR_LF, LF)
        with open(file_path, 'wb') as f:
            f.write(modified_content)

def docker_compose_include(supabase, filesystem, verbose):
    """Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml"""
    compose_file = "docker-compose.yml"
    supabase_compose_file = "supabase/docker/docker-compose.yml"
    filesystem_compose_file = "open-webui/tools/servers/filesystem/compose.yaml"
    if not os.path.exists(compose_file):
        print(f"Error: Docker Compose file '{compose_file}' not found - include skipped...")
        return
    if supabase and not os.path.exists(supabase_compose_file):
        if verbose:
            print(f"Warning: Include file '{supabase_compose_file}' not found.")
        supabase = False
    if filesystem and not os.path.exists(filesystem_compose_file):
        if verbose:
            print(f"Warning: Include file '{filesystem_compose_file}' not found.")
        filesystem = False
    if verbose:
        supabase_ins = "add" if supabase else "remove"
        filesystem_ins = "add" if filesystem else "remove"
        print(f"Perform {supabase_ins} Supabase and {filesystem_ins} Filesystem "
              f"'include:' in {compose_file}...")
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
                if verbose:
                    print(f"Adding 'include:' element to {compose_file}...")
                content = "\n" + content
        elif compose_include in content and verbose:
            if verbose:
                print(f"Removing 'include:' element from {compose_file}...")

        if supabase and supabase_include not in content:
            if verbose:
                print(f"Adding include file ./{supabase_compose_file}...")
            content = supabase_include + content
        elif not supabase and supabase_include in content:
            if verbose:
                print(f"Removing include file ./{supabase_compose_file}...")
            content = content.replace(supabase_include, "")

        if filesystem and filesystem_include not in content:
            if verbose:
                print(f"Adding include file ./{filesystem_compose_file}...")
            content = filesystem_include + content
        elif not filesystem and filesystem_include in content:
            if verbose:
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

def normalize_path(path):
    """Normalize path for current platform"""
    if path:
        if path.startswith('~'):
            path = os.path.expanduser(path)
        elif path.strip() == '.':
            path = os.getcwd()
        path = os.path.abspath(path)
    return path

def check_prerequisites():
    """Check if required tools are installed"""
    required_tools = ['docker', 'git']
    missing_tools = []
    for tool in required_tools:
        if shutil.which(tool) is None:
            missing_tools.append(tool)
    if missing_tools:
        print(f"Missing required tools: {', '.join(missing_tools)}")
        print("Install them before continuing.")
        return False
    try:
        subprocess.run(
            ["docker", "info"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("Docker is not running. Start Docker Desktop.")
        return False
    return True

def get_dotenv_vars(env_file=None, force=False):
    """Load environment variables from .env file"""
    if env_file is None:
        env_file = os.path.join(".env")
    if not os.path.exists(env_file):
        if os.path.exists(".env.example"):
            print("The .env file was not found - creating from .env.example template...")
            shutil.copy('.env.example', '.env')
            print("⚠️ IMPORTANT: Edit .env file with secure passwords and keys - exiting...")
        else:
            print("The .env file was not found - exiting...")
        return {}
    else:
        with open(env_file, 'r') as f:
            env_content = f.read()
        default_secrets = [
            'N8N_ENCRYPTION_KEY=change_me_to_a_long_super-secret-key',
            'N8N_RUNNERS_AUTH_TOKEN=change_me_to_a_long_super-secret-key',
            'N8N_USER_MANAGEMENT_JWT_SECRET=change_me_to_a_longer_even-more-secret',
            'POSTGRES_PASSWORD=your-super-secret-postgres-password',
            'JWT_SECRET=your-super-secret-jwt-token-with-at-least-40-characters-long',
            'DASHBOARD_PASSWORD=your-super-secret-password-1',
            'FLOWISE_PASSWORD=your-super-secret-postgres-password',
            'NEO4J_AUTH=neo4j/your-super-secret-password-2',
            'CLICKHOUSE_PASSWORD=your-super-secret-password-3',
            'MINIO_ROOT_PASSWORD=your-super-secret-password-4',
            'LANGFUSE_SALT=your-super-secret-key-1',
            'NEXTAUTH_SECRET=your-super-secret-key-2',
            'ENCRYPTION_KEY=your-super-secret-key-3']
        unset_secrets = []
        for secret in default_secrets:
            if secret in env_content:
                unset_secrets.append(secret)
        if unset_secrets and not force:
            print("ERROR: YOUR .env FILE CONTAINS DEFAULT VALUES THAT NEED TO BE CHANGED!")
            for secret in unset_secrets:
                print(f"⚠️ CHANGE THIS VALUE ⚠️: {secret}")
            print("Exiting...")
            return {}

    env_vars = dotenv.dotenv_values(env_file)
    path = env_vars['PROJECTS_PATH']
    if not path:
        path = os.path.join('~', 'projects')
    env_vars['PROJECTS_PATH'] = normalize_path(path)

    return env_vars

def load_dotenv_vars(env_vars):
    """Load working environment variables into environment"""
    if env_vars:
        print("Loading working environment variables...")
        for env, var in env_vars.items():
            if not var:
                continue
            os.environ[env] = var
    else:
        env_file = os.path.join(".env")
        if not os.path.exists(env_file):
            if not get_dotenv_vars():
                sys.exit(1)
        print("Loading .env environment variables...")
        dotenv.load_dotenv(env_file)

def write_dotenv_file(env_file, env_vars):
    """Copy .env to .env in target compose file destination."""
    if env_file is None:
        print("Error: The .env file path to be written is not defined!")
        return
    if env_vars is None:
        print("Error: The env_vars dictionary to be written is empty!")
        return
    print(f"Writing .env file to {env_file}...")
    with open(env_file, 'w') as f:
        now = " ".join(['on:', datetime.datetime.now().ctime()])
        f.seek(0)
        f.truncate()
        f.write(f"# {now} - Generated {name} working .env environment variables.")
        f.write('\n')
        for env, var in env_vars.items():
            if not var:
                continue
            quoted_var = var if var.isalnum() else f"'{var}'"
            f.write("".join([env, '=', quoted_var, '\n']))

def set_dotenv_var(env_file, env, var, header):
    """Set or unset an environment variable and add optional header in .env file"""
    if not env:
        print("Error: A valid .env key was not specified.")
        return
    if env_file is None:
        env_file = os.path.join(".env")
    if not var:
        try:
            with open(env_file, 'r+') as f:
                lines = f.readlines()
                f.seek(0)
                f.truncate()
                for line in lines:
                    line_array = line.strip().split('=')
                    if len(line_array) > 1 and env == line_array[0].strip():
                        var_array = line_array[1].strip().split('#')
                        mod_line = line
                        if len(var_array) > 1 and var == var_array[0].strip():
                            mod_line = ''.join([env, '=    #', var_array[1], '\n'])
                        elif len(var_array) == 1:
                            mod_line = ''.join([env, '=\n'])
                        line = mod_line
                        f.write("# Omitted '<value>' to return 'False' when queried")
                        print(f"Notice: Value for {env} removed...")
                    f.write(line)
        except FileNotFoundError:
            print(f"Exception: File '{env_file}' not found.")
        return
    quote_mode = "auto"
    if header is not None:
        with open(env_file, 'r') as f:
            content = f.read()
        if not header in content:
            quote_mode = "never"
            env = "".join([header, env])
    print(f"Set '{env}' to {quote_mode}-quote '{var}' in {env_file}...")
    dotenv.set_key(env_file, env, var, quote_mode)

def configure_n8n_database_settings(supabase):
    """Set n8n database depends_on and Postgres profiles and volume in Docker Compose file."""
    compose_file = os.path.join("docker-compose.yml")
    try:
        with open(compose_file, 'r') as f:
            content = f.read()
        old_vol = "postgres_data" if supabase else "langfuse_postgres_data"
        regex = r"\b{}\b\:".format(old_vol)
        if re.search(regex, content):
            new_vol = "langfuse_postgres_data:" if supabase else "postgres_data:"
            print(f"Set Postgres volume: from '{old_vol}' to '{new_vol}' in {compose_file}...")
            modified_content = re.sub(r"\b{}\b\:".format(old_vol), new_vol, content)
            with open(compose_file, 'w') as f:
                f.write(modified_content)

        with open(compose_file, 'r+') as f:
            n8n_updated = False
            n8n_update = False
            old_db = "postgres:" if supabase else "db:"
            new_db = "db:" if supabase else "postgres:"
            lines = f.readlines()
            f.seek(0)
            f.truncate()
            for line in lines:
                if not n8n_updated:
                    if line == '  n8n-import:\n':
                        n8n_update = True
                    if line == '  n8n-runner:\n':
                        n8n_updated = True
                        n8n_update = False
                    if n8n_update:
                        if line == f'      {old_db}\n':
                            line = f"      {new_db}\n"
                    if n8n_updated:
                        print(f"Set n8n database depends_on: to '{new_db}' "
                              f"from '{old_db}' in {compose_file}...")
                f.write(line)
    except Exception as e:
        print(f"Exception: Update n8n database settings in {compose_file}: {e}")

def main():
    # Name and file globals
    global name, file
    name = INFO.get('name', 'placeholder')
    file = INFO.get('file', 'placeholder.py')


    # Banner
    print(f"""{name} version: {'.'.join(map(str, version))} LLM: {llama}""")

    # Profile, environment and operation arguments
    global open_webui_all_profiles
    llama_host_profiles = ['ollama', 'llama.cpp']
    ollama_docker_profiles = ['cpu', 'gpu-nvidia', 'gpu-amd']
    llamacpp_docker_profiles = ['cpp-cpu', 'cpp-gpu-nvidia', 'cpp-gpu-amd']
    llama_docker_profiles = ollama_docker_profiles + llamacpp_docker_profiles
    n8n_profiles = ['n8n', 'n8n-all']
    n8n_all_profiles = n8n_profiles + ['ai-all']
    open_webui_utils_profiles = ['open-webui-mcpo', 'open-webui-pipe']
    open_webui_profiles = ['open-webui', 'open-webui-all']
    open_webui_all_profiles = open_webui_profiles + n8n_all_profiles
    agent_all_profiles = open_webui_all_profiles + ['opencode']
    server_profiles = ['supabase', 'flowise', 'searxng', 'langfuse', 'neo4j', 'caddy']
    profiles = agent_all_profiles + open_webui_utils_profiles + server_profiles + \
               llama_docker_profiles + llama_host_profiles
    operations = ['stop', 'stop-llama', 'start', 'pause', 'unpause', 'update', 'install']
    environments = ['private', 'public']
    log_levels = ['OFF', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
    parser = argparse.ArgumentParser(
        prog=f'{file}',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(f'''\
            {INFO.get("description")}

            With {file}, you can install, start, stop, pause, update or install
            {name} with specified profile arguments (functional modules) and environment.
            ___________________________

            Command syntax:

            python {file} [--profile <arguments...>] [--environment <argument>] [--operation <argument>]

            Example commands:

            - Install functional modules n8n and opencode...
              ...with {llama} running on the Host:
              python {file} --profile n8n opencode

              ...with Ollama CPU running in Docker:
              python {file} --profile n8n opencode cpu

              ...with Llama.cpp AMD GPU in Docker and on production environment:
              python {file} --profile n8n opencode cpp-gpu-amd --environment public

            - Perform (stop, start, pause, unpause) operation...
              ...to stop n8n and opencode:
              python {file} --profile n8n opencode --operation stop

              ...to stop n8n, opencode and {llama} running on the Host:
              python {file} --profile n8n opencode --operation stop-llama

            - Perform (install, update) operation...
              ...to update all modules and restart using Ollama running on the Host:
              python {file} --operation update

              ...to update all modules and restart using Ollama CPU running in Docker:
              python {file} --profile ai-all cpu --operation update

              ...to install all modules and start using Ollama running on the Host:
              python {file} --operation install

              ...to install all modules and start using Llama.cpp Nvidia GPU running in Docker:
              python {file} --profile ai-all cpp-gpu-nvidia --operation install

            '''),
        epilog=textwrap.dedent(f'''\
            - Title: {INFO.get("title")}
            - File: {INFO.get("file")}
            - Author: {INFO.get("author")}
            - Author URL: {INFO.get("author_url")}
            - Repository: {INFO.get("repository")}
            - Report Issues: {INFO.get("issues")}
            - License: {INFO.get("license")}
            - Copyright: {INFO.get("copyright")}
            '''))
    parser.add_argument('-p', '--profile', type=str.lower, nargs='+', choices=profiles,
                        help='Docker Compose Profile arguments for functional modules and llama'
                             f'CPU/GPU options (default: open-webui - with {llama} running on Host)')
    parser.add_argument('-e', '--environment', type=str.lower, choices=environments, default='private',
                        help='Environment arguments used by Docker Compose to expose '
                             'or restrict network communication ports (default: private)')
    parser.add_argument('-o', '--operation', type=str.lower, choices=operations,
                        help='Docker container, volumes and image management arguments along '
                              f'with argument to stop {llama} running on Host.')
    parser.add_argument('-l', '--log', type=str.upper, choices=log_levels, default='INFO',
                        help='Enable stream (console) logging and set log level. File logging is always '
                             'enabled at DEBUG and is not affected by this argument (default: INFO)')

    args = parser.parse_args()
    # Detect operational status and current llama (Ollama/Llama.cpp) configuration
    global llama, llama_cpp
    status = None
    llama_cpp = False
    env_file = os.path.join(".env")
    if os.path.exists('.operation'):
        with open('.operation', 'r') as f:
            op_array = f.readline().split(':')
            status = op_array[0].strip() if op_array else None
            if len(op_array) > 1:
                llama_cpp = op_array[1].strip() == 'llama.cpp'
    elif os.path.exists(env_file):
        lpv = dotenv.get_key(env_file, 'LLAMA_PATH')
        llama_cpp = lpv and os.path.basename(lpv).lower().startswith('llama-server')
    llama = "Llama.cpp" if llama_cpp else "Ollama"


    # Detect platform
    global system
    system = platform.system()
    if system == "Windows":
        print("""Detected Windows platform...""")
    elif system == "Darwin":  # macOS
        print("""Detected macOS platform...""")
    else:  # Linux and other Unix-like systems
        print("""Detected Linux/Unix platform...""")

    # Check prerequisites
    if not check_prerequisites():
        sys.exit(1)

    # Load working environment variables
    mod_env_vars = {}
    env_vars = get_dotenv_vars()
    if not env_vars:
        sys.exit(1)

    # Detect default profile - no arguments specified
    default_profile = False if args.profile else True
    args.profile = [] if default_profile else args.profile

    # Process llama (Ollama/Llama.cpp) status checks
    llama_arg = "cpu"
    llama_in_host = default_profile or not \
        any(p for p in args.profile if p in llama_docker_profiles)
    if llama_in_host:
        global llama_found, llama_app, llama_exe, attempted_launch
        attempted_launch = False
        llama_found = False
        llama_path = normalize_path(env_vars.get('LLAMA_PATH'))
        llama_cpp = any(p for p in args.profile if p == 'llama.cpp')
        llama = "Llama.cpp" if llama_cpp else "Ollama"
        if llama_path:
            llama_exe = os.path.normpath(llama_path)
            llama_app = os.path.basename(llama_exe)
            llama_found = os.path.exists(llama_exe)
        if not llama_found:
            llama_app = "llama-server" if llama_cpp else "ollama"
            if system == "Windows":
                llama_app = "".join([llama_app, '.exe'])
                llama_dir = os.path.join("llama.cpp", "bin") if llama_cpp else "Ollama"
                for llama_sub in ['~\\AppData\\Local\\Programs', os.getcwd()]:
                    llama_exe = normalize_path(os.path.join(llama_sub, llama_dir, llama_app))
                    if os.path.exists(llama_exe):
                        llama_found = True
                        break
            else: # Unix-based systems (Linux, macOS)
                for llama_path in ['/bin', '/usr/local/bin', '/usr/bin']:
                    llama_exe = os.path.join(llama_path, llama_app)
                    if os.path.exists(llama_exe):
                        llama_found = True
                        break
            mod_env_vars.update({'LLAMA_PATH': llama_exe})
        # Check if llama exe (llama-server, ollama) matches profile argument (llama.cpp, ollama)
        if (llama_cpp and not llama_app.lower().startswith('llama-server')) or \
           (not llama_cpp and not llama_app.lower().startswith('ollama')):
            llama_cpp = llama_app.lower().startswith('llama-server')
            llama = "Llama.cpp" if llama_cpp else "Ollama"
            llama_mismatch = "ollama" if llama_cpp else "llama.cpp"
            print(f"""Notice: The executable '{llama_app}' did not match the '{llama}'
                      profile argument - argument updated to '{llama.lower()}'...""")
            args.profile.remove(llama_mismatch) if llama_mismatch in args.profile else None
            args.profile.extend([llama.lower()]) if llama_cpp else None
        llama_host = "host.docker.internal"
        llama_host_var = llama_host if llama_cpp else llama_host + ":${OLLAMA_PORT}"
        check_llama_process(args.operation, env_vars)
    else:
        llama_cpp = any(p for p in args.profile if p in llamacpp_docker_profiles)
        llama = "Llama.cpp" if llama_cpp else "Ollama"
        llama_host_var = "0.0.0.0" if llama_cpp else "ollama:${OLLAMA_PORT}"
        # Check if more than one llama CPU/GPU argument specified, use first argument
        if any(p for p in args.profile if p in llama_docker_profiles):
            first_argument = False
            for profile_arg in llama_docker_profiles:
                if not first_argument:
                    if any(p for p in args.profile if p == profile_arg):
                        print(f"""{name} will use {llama} CPU/GPU profile argument '{profile_arg}'...""")
                        first_argument = True
                else:
                    args.profile.remove(profile_arg) if profile_arg in args.profile else None
        # Check if any llama host profile arguments specified and remove if found
        for profile_arg in llama_host_profiles:
            if any(p for p in args.profile if p == profile_arg):
                print(f"""A llama in host profile argument cannot be specified with
                          llama CPU/GPU profile argument  - removing '{profile_arg}'...""")
                args.profile.remove(profile_arg)
    # Assemble .env updates, set respective keys in .env file and reload .env vars
    llama_host_env = "LLAMA_ARG_HOST" if llama_cpp else "OLLAMA_HOST"
    oai_base_url_var = "${LLAMACPP_HOST}" if llama_cpp else "${OLLAMA_HOST}"
    mod_env_vars.update({llama_host_env: llama_host_var, 'OPENAI_API_BASE_URL': oai_base_url_var})
    for env, var in mod_env_vars.items():
        set_dotenv_var(env_file, env, var, None)
    env_vars = get_dotenv_vars(env_file, True)

    # Process operation argument
    build = False
    if args.operation:
        if args.operation == 'stop-llama':
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
        build = args.operation in ['update', 'install']
        if build:
            install = args.operation == 'install'
            if args.operation == 'update':
                user_confirm = input(textwrap.dedent(f"""\
                    Performing an {name} update can impact its integrity.
                    Consider backing up your data to enable rollback.
                    [Type 'Got-It' to continue]: """))
                if len(user_confirm) == 0 or user_confirm.lower() != 'got-it':
                    print(f"""Received [{user_confirm}].""") if user_confirm else None
                    print(f"""{name} update was not confirmed - exiting...""")
                    sys.exit(0)
            args.operation = 'pull'
            insert = "Installing" if install == 'install' else "Updating"
            if default_profile:
                print(f"""{insert} all container images including {llama}...""")
                llama_arg = "cpp-cpu" if llama_cpp else "cpu"
                args.profile.extend([llama_arg])
            else:
                print(f"""{insert} container images for {args.profile}...""")
            docker_compose_include(True, True, False)
            destroy_ai_suite(args.profile, install)
        operate_ai_suite(args.operation, args.profile, args.environment, env_vars)
        if not build:
            sys.exit(0)
    os.remove('.operation') if os.path.exists('.operation') else None

    # Manually set default profile argument
    if default_profile:
        if build:
            args.profile.remove(llama_arg) if llama_arg in args.profile else None
        else:
            args.profile = ['open-webui']

    # Setup Supabase
    if any(p for p in args.profile if p == 'supabase'):
        if not any(p for p in args.profile if p in n8n_all_profiles):
            print(f"""Profile argument 'supabase' requires argument in {n8n_all_profiles}
                      - removing 'supabase'...""")
            args.profile.remove('supabase')
    supabase = \
        any(p for p in args.profile if p in ['supabase', 'ai-all'])
    if supabase:
        args.profile.remove('supabase') if 'supabase' in args.profile else None
        clone_supabase_repo()
        convert_supabase_pooler_line_endings()

    if any(p for p in args.profile if p in n8n_all_profiles):
        env_vars['POSTGRES_HOST'] = "db" if supabase else "postgres"
        configure_n8n_database_settings(supabase)

    if supabase:
        prepare_supabase_env(env_vars)
    elif 'langfuse' in args.profile:
        print("""Profile argument 'langfuse' requires Supabase - removing 'langfuse'...'""")
        args.profile.remove('langfuse')

    # Generate SearXNG secret key and check docker-compose.yml
    if any(p for p in args.profile if p in ['searxng', 'ai-all']):
        generate_searxng_secret_key()
        check_and_fix_docker_compose_for_searxng()

    # Setup Open WebUI Functions and Tools Filesystem repos
    open_webui = \
        any(p for p in args.profile if p in open_webui_all_profiles)
    if open_webui:
        clone_open_webui_functions_repos()
        clone_open_webui_tools_filesystem_repo()
        prepare_open_webui_tools_filesystem_env(env_vars)

    # Add or remove Supabase and Filesystem include compose.yml in docker-compose.yml
    docker_compose_include(supabase, open_webui, True)

    # Stop and remove AI-Suite containers
    if not build:
        destroy_ai_suite(args.profile, False)

    # Load environment variables
    load_dotenv_vars(env_vars)

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

    # Unset Compose ignore orphans variable
    env = "COMPOSE_IGNORE_ORPHANS"
    if env in os.environ:
        del os.environ[env]

    # Check if open-webui-mcpo specified with required profile arguments, else remove open-webui-mcpo
    if any(p for p in args.profile if p == 'open-webui-mcpo'):
        if not any(p for p in args.profile if p in open_webui_all_profiles):
            print(f"""Profile argument 'open-webui-mcpo' requires argument in
                      {open_webui_all_profiles} - removing 'open-webui-mcpo'...""")
            args.profile.remove('open-webui-mcpo')

    # Check if open-webui-pipe specified with required profile arguments, else remove open-webui-pipe
    if any(p for p in args.profile if p == 'open-webui-pipe'):
        if not any(p for p in args.profile if p in open_webui_all_profiles):
            print(f"""Profile argument 'open-webui-pipe' requires argument in
                      {open_webui_all_profiles} - removing 'open-webui-pipe'...""")
            args.profile.remove('open-webui-pipe')

    # Check if profile arguments n8n and open-webui specified, remove redundant open-webui
    if any(p for p in args.profile if p == 'n8n'):
        if any(p for p in args.profile if p == 'open-webui'):
            print("""Profiles arguments 'n8n' and 'open-webui' detected - removing 'open-webui'...""")
            args.profile.remove('open-webui')

    # Check if more than one Ollama CPU/GPU argument specified, use first argument
    if any(p for p in args.profile if p in ollama_docker_profiles):
        first_argument = False
        for profile_arg in ollama_docker_profiles:
            if not first_argument:
                if any(p for p in args.profile if p == profile_arg):
                    print(f"""{name} will use Ollama CPU/GPU profile argument '{profile_arg}'...""")
                    first_argument = True
            else:
                args.profile.remove(profile_arg) if profile_arg in args.profile else None

    # Then start the AI-Suite services
    start_ai_suite(args.profile, args.environment, build)

    with open('.operation', 'w') as f:
        f.write('start' + ':' + llama.lower())

if __name__ == "__main__":
    main()
