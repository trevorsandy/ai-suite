#!/usr/bin/env python3
"""
Trevor SANDY

This script will verify the status of a OpenCode Docker container by it's name
to determine if the container is running. If the container is running, it will
attempt to connect and run OpenCode.

Set the PROJECT_PATH env variable to your working project directory before
running OpenCode if you wish to set the work path to your current project but
you will NOT launch OpenCode from the root of your working project.

If the PROJECT_PATH var is not defined, the currend working directory from
which OpenCode was launched is assumed.

You can also pass the project_path entry to ./opencode/run_opencode_docker.py
as an anargument with -p, --project_path.

See 'PROJECT_PATH environment variable' and 'PROJECTS_PATH environment variable'
sections in README.md

"""

import os
import pathlib
import argparse
import subprocess

CONTAINER = 'opencode'
FAIL = -1

def container_is_running():
    """:return: True if container name found in output check, else False."""
    cmd = " ".join(['docker', 'ps', '-a', '--format', '"{{.Names}}"', '--filter',
                   f'name=^/{CONTAINER}$'])
    print("Running command:", cmd)
    try:
        bytes = subprocess.check_output(cmd, shell=True)
        running = bytes.find(CONTAINER.encode()) != FAIL
        insert = ('is', 'running...') if running else ('is not', 'running - exiting...')
        print("Container", " ".join([CONTAINER, insert[0], insert[1]]))
        return running
    except subprocess.CalledProcessError:
        return False

def container_env_var(env_var):
    """:return: container environment variable."""
    cmd = " ".join(['docker', 'exec', CONTAINER, 'printenv', env_var])
    print("Running command:", cmd)
    try:
        bytes = subprocess.check_output(cmd, shell=True)
        print(f"Container env var: {env_var} = {bytes.decode().strip()}")
        return bytes.decode().strip()
    except subprocess.CalledProcessError as e:
        print(f"Container env var: {env_var} not found: {e}")
        return ""

def container_work_dir(project_path):
    """:return: current work path converted to container bind mounted work path """
    print("Perform project path to container work path conversion...")
    if project_path is None:
        project_path = os.environ.get('PROJECT_PATH')
    if project_path is None:
        project_path = os.getcwd()
    work_path = pathlib.Path('/root', 'projects').as_posix()
    projects_path = os.path.normcase(container_env_var('PROJECTS_PATH'))
    if projects_path != "":
        abs_project_path = os.path.normcase(os.path.abspath(project_path))
        rel_project_path = os.path.normcase(os.path.relpath(project_path, start=projects_path))
        if abs_project_path.startswith(projects_path):
            work_path = pathlib.Path('/root', 'projects', rel_project_path).as_posix()
        else:
            print(f"Warning: project path does not start with container projects path...")
    else:
        print(f"Warning: container projects path not defined...")
    print(f"Project path: {project_path}, work path: {work_path}")
    return work_path

def main():
    print("Launching OpenCode...")
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--project_path', type=str,
                   help='Current project path which is racommended to be '
                        'within and relative to PROJECTS_PATH defined in '
                        'the AI-Suite .env file.')
    args = parser.parse_args()

    if not container_is_running():
        exit(FAIL)

    print(f"Connecting to container {CONTAINER}...")
    work_dir = container_work_dir(args.project_path)
    cmd = ['docker', 'exec', '-it', '-w', work_dir, CONTAINER, '/bin/sh', '-c',
           '/usr/local/bin/opencode', '.']

    print(f"Running launch command: {" ".join(cmd)}...")
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
    except Exception as e:
        print(f"Exception: {e}.")

if __name__ == "__main__":
    main()
