#!/usr/bin/env python3
"""
start_services.py

This script starts the Supabase stack first, waits for it to initialize, and then starts
the AI-Suite stack. Both stacks use the same Docker Compose project name ("ai-suite")
so they appear together in Docker Desktop.
"""

import os
import subprocess
import shutil
import time
import argparse
import platform
import sys

def run_command(cmd, cwd=None):
    """Run a shell command and print it."""
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)

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

def prepare_supabase_env():
    """Copy .env to .env in supabase/docker."""
    env_path = os.path.join("supabase", "docker", ".env")
    env_example_path = os.path.join(".env")
    print("Copying .env in root to .env in supabase/docker...")
    shutil.copyfile(env_example_path, env_path)

def stop_existing_containers(profile=None):
    print("Stopping and removing existing containers for the unified project 'ai-suite'...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile and profile != "none":
        cmd.extend(["--profile", profile])
    cmd.extend(["-f", "docker-compose.yml", "down"])
    run_command(cmd)

def start_supabase(environment=None):
    """Start the Supabase services (using its compose file)."""
    print("Starting Supabase services...")
    cmd = ["docker", "compose", "-p", "ai-suite", "-f", "supabase/docker/docker-compose.yml"]
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.supabase.yml"])
    cmd.extend(["up", "-d"])
    run_command(cmd)

def start_ai_suite(profile=None, environment=None):
    """Start the AI-Suite services (using its compose file)."""
    print("Starting AI-Suite services...")
    cmd = ["docker", "compose", "-p", "ai-suite"]
    if profile and profile != "none":
        cmd.extend(["--profile", profile])
    cmd.extend(["-f", "docker-compose.yml"])
    if environment and environment == "private":
        cmd.extend(["-f", "docker-compose.override.private.yml"])
    if environment and environment == "public":
        cmd.extend(["-f", "docker-compose.override.public.yml"])
    cmd.extend(["up", "-d"])
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
            print(f"Error creating settings.yml: {e}")
            return
    else:
        print(f"SearXNG settings.yml already exists at {settings_path}")

    print("Generating SearXNG secret key...")

    # Detect the platform and run the appropriate command
    system = platform.system()

    try:
        if system == "Windows":
            print("Detected Windows platform, using PowerShell to generate secret key...")
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
            print("Detected macOS platform, using sed command with empty string parameter...")
            # macOS sed command requires an empty string for the -i parameter
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", "", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        else:  # Linux and other Unix-like systems
            print("Detected Linux/Unix platform, using standard sed command...")
            # Standard sed command for Linux
            openssl_cmd = ["openssl", "rand", "-hex", "32"]
            random_key = subprocess.check_output(openssl_cmd).decode('utf-8').strip()
            sed_cmd = ["sed", "-i", f"s|ultrasecretkey|{random_key}|g", settings_path]
            subprocess.run(sed_cmd, check=True)

        print("SearXNG secret key generated successfully.")

    except Exception as e:
        print(f"Error generating SearXNG secret key: {e}")
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
        # Read the docker-compose.yml file
        with open(docker_compose_path, 'r') as file:
            content = file.read()

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
            print(f"Error checking Docker container: {e} - assuming first run")

        cap_drop = "cap_drop:\n      - ALL\n"
        cap_drop_comment = "   #cap_drop:\n   #  - ALL  # Temporarily commented out for first run\n"

        if is_first_run and cap_drop in content:
            print(f"First run detected for SearXNG. Temporarily commenting {cap_drop} directive...")
            # Temporarily comment out the cap_drop line
            modified_content = content.replace(cap_drop, cap_drop_comment)

            # Write the modified content back
            with open(docker_compose_path, 'w') as file:
                file.write(modified_content)

            print(f"Note: After the first run completes successfully, uncomment {cap_drop} in docker-compose.yml for security.")
        elif not is_first_run and cap_drop_comment in content:
            print(f"SearXNG has been initialized. Uncommenting {cap_drop} directive for security...")
            # Uncomment the cap_drop line
            modified_content = content.replace(cap_drop_comment, cap_drop)

            # Write the modified content back
            with open(docker_compose_path, 'w') as file:
                file.write(modified_content)

    except Exception as e:
        print(f"Error checking/modifying docker-compose.yml for SearXNG: {e}")

# Treat Selfhosted Supavisor Pooler Keeps Restarting.
# See: https://github.com/supabase/supabase/issues/30210
def convert_supabase_pooler_line_endings():
    """converting Windows line endings to Linux/Unix/MacOS line endings."""
    system = platform.system()
    if system == "Windows":
        print("Converting supavisor pooler line endings...")
        WINDOWS_LINE_ENDING = b'\r\n'
        UNIX_LINE_ENDING = b'\n'
        file_path = r"supabase/docker/volumes/pooler/pooler.exs"
        with open(file_path, 'rb') as open_file:
            content = open_file.read()
        # Windows ➡ Unix
        content = content.replace(WINDOWS_LINE_ENDING, UNIX_LINE_ENDING)
        with open(file_path, 'wb') as open_file:
            open_file.write(content)

def include_supabase_docker_compose(supabase=False):
    """Add or remove supabase supabase_docker_compose_file"""
    supabase_docker_compose_path = "supabase/docker/docker-compose.yml"
    if not os.path.exists(supabase_docker_compose_path):
        print(f"Error: Supabase Docker Compose file not found at {supabase_docker_compose_path}")
        return
    docker_compose_path = "docker-compose.yml"
    if not os.path.exists(docker_compose_path):
        print(f"Error: Docker Compose file not found at {docker_compose_path}")
        return

    try:
        with open(docker_compose_path, 'r') as file:
            content = file.read()
        supabase_docker_compose_include = f"include:\n  - ./{supabase_docker_compose_path}\n\n"
        if supabase and supabase_docker_compose_include not in content:
            print(f"Including ./{supabase_docker_compose_path} to {docker_compose_path}...")
            with open(docker_compose_path, 'w') as file:
                file.write(supabase_docker_compose_include + content)
        elif not supabase and supabase_docker_compose_include in content:
            print(f"Excluding ./{supabase_docker_compose_path} from {docker_compose_path}...")
            modified_content = content.replace(supabase_docker_compose_include, "")
            with open(docker_compose_path, 'w') as file:
                file.write(modified_content)
    except Exception as e:
        print(f"Error processing {docker_compose_path}: {e}")

def main():
    profiles = ['owui', 'owui-all', 'ai-all',
                'cpu', 'gpu-nvidia', 'gpu-amd', 'none']
    parser = argparse.ArgumentParser(description='Start the AI-Suite and Supabase services.')
    parser.add_argument('--profile', choices=profiles, default=['owui', 'cpu'],
                      help='Profile to use for Docker Compose (default: cpu)')
    parser.add_argument('--environment', choices=['private', 'public'], default='private',
                      help='Environment to use for Docker Compose (default: private)')
    args = parser.parse_args()

    clone_supabase_repo()
    convert_supabase_pooler_line_endings()
    prepare_supabase_env()

    # Include or exclude supabase_docker_compose in docker-compose.yml
    include_supabase_docker_compose(supabase)

    # Generate SearXNG secret key and check docker-compose.yml
    generate_searxng_secret_key()
    check_and_fix_docker_compose_for_searxng()

    stop_existing_containers(args.profile)

    # Start Supabase first
    start_supabase(args.environment)

    # Give Supabase some time to initialize
    print("Waiting for Supabase to initialize...")
    time.sleep(10)

    # Then start the AI-Suite services
    start_ai_suite(args.profile, args.environment)

if __name__ == "__main__":
    main()
