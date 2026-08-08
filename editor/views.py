from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from .models import Project, File
import subprocess
import os

running_servers = {}

def create_project(request):

    if request.method == "POST":

        projectname = request.POST.get(
            "projectname",
            ""
        ).strip()

        if not projectname:
            messages.error(
                request,
                "Project name cannot be empty."
            )
            return redirect("project_list")

        project_path = (
            settings.PROJECTS_DIR
            / projectname
        )

        if project_path.exists():

            messages.error(
                request,
                f"Project '{projectname}' already exists."
            )

            return redirect("project_list")

        try:

            call_command(
                "startproject",
                projectname,
                project_path
            )

            project = Project.objects.create(
                name=projectname
            )

            sync_project_files(project)

        except Exception as e:

            messages.error(
                request,
                f"Could not create project: {e}"
            )

            return redirect("project_list")

        messages.success(
            request,
            f"Project '{projectname}' created successfully."
        )

        return redirect(
            "editor",
            project_id=project.id
        )

    return render(
        request,
        "new_project.html"
    )

def create_file(request, project_id):
    project = get_object_or_404(
        Project,
        id=project_id
    )

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        path = request.POST.get("path", "").strip()

        project_path = settings.PROJECTS_DIR / project.name
        file_path = project_path / path / name

        # Prevent paths such as ../../something
        try:
            file_path.resolve().relative_to(
                project_path.resolve()
            )
        except ValueError:

            messages.error(
                request,
                "Invalid file path."
            )

            return redirect(
                "editor",
                project_id=project.id
            )

        # Check if the file already exists
        if file_path.exists():

            messages.error(
                request,
                "Project already exists."
            )

            return redirect(
                "editor",
                project_id=project.id
            )

        # Make sure the parent folder exists
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # Create the actual file
        file_path.touch()

        # Add it to database
        File.objects.create(
            project=project,
            name=name,
            path=str(
                file_path.relative_to(project_path)
            ),
            content="",
            is_directory=False
        )

        messages.success(
            request,
            f"{name} created successfully."
        )

    return redirect(
        "editor",
        project_id=project.id
    )


def create_folder(request, project_id):

    project = get_object_or_404(
        Project,
        id=project_id
    )

    if request.method == "POST":

        name = request.POST.get("name")
        path = request.POST.get("path", "")

        project_path = settings.PROJECTS_DIR / project.name

        folder_path = project_path / path / name

        # Create actual folder
        folder_path.mkdir(
            parents=True,
            exist_ok=True
        )

        # Add folder to database
        File.objects.create(
            project=project,
            name=name,
            path=str(
                folder_path.relative_to(project_path)
            ),
            content="",
            is_directory=True
        )

        return redirect(
            "editor",
            project_id=project.id
        )

    return redirect(
        "editor",
        project_id=project.id
    )

def build_file_tree(project):

    items = project.file_set.all()

    tree = []

    for item in items:

        parts = item.path.replace("\\", "/").split("/")

        current_level = tree

        for index, part in enumerate(parts):

            is_last = index == len(parts) - 1

            # Already exists at this level
            existing = next(
                (
                    x for x in current_level
                    if x["name"] == part
                ),
                None
            )

            if existing:
                current_level = existing["children"]

            else:

                node = {
                    "name": part,
                    "is_directory": (
                        item.is_directory
                        if is_last
                        else True
                    ),
                    "children": [],
                    "file": item if is_last and not item.is_directory else None,
                }

                current_level.append(node)
                current_level = node["children"]
    return tree

def sync_project_files(project):

    project_path = settings.PROJECTS_DIR / project.name

    existing_paths = set()

    for path in project_path.rglob("*"):

        relative_path = str(
            path.relative_to(project_path)
        )

        existing_paths.add(relative_path)

        if path.is_dir():

            File.objects.update_or_create(
                project=project,
                path=relative_path,
                defaults={
                    "name": path.name,
                    "is_directory": True,
                    "content": "",
                }
            )

        elif path.is_file():

            try:
                content = path.read_text(
                    encoding="utf-8"
                )
            except UnicodeDecodeError:
                continue

            File.objects.update_or_create(
                project=project,
                path=relative_path,
                defaults={
                    "name": path.name,
                    "is_directory": False,
                    "content": content,
                }
            )

    # Remove database records whose files no longer exist
    File.objects.filter(
        project=project
    ).exclude(
        path__in=existing_paths
    ).delete()

def save_file(request, file_id):

    file = get_object_or_404(
        File,
        id=file_id
    )

    if request.method == "POST":

        content = request.POST.get("content", "")

        # Update database copy
        file.content = content
        file.save()

        # Update actual file
        file_path = (
            settings.PROJECTS_DIR
            / file.project.name
            / file.path
        )

        file_path.write_text(
            content,
            encoding="utf-8"
        )

    return redirect(
        "open_file",
        file_id=file.id
    )

def project_list(request):
    projects = Project.objects.all()
    for project in projects:
        project_path = settings.PROJECTS_DIR / project.name
        if not project_path.exists():
            project.delete()
    projects = Project.objects.all()
    return render(
        request,
        "project_list.html",
        {"projects": projects}
    )

def open_file(request, file_id):

    file = get_object_or_404(
        File,
        id=file_id,
        is_directory=False
    )

    project = file.project

    tree = build_file_tree(project)

    return render(
        request,
        "editor.html",
        {
            "project": project,
            "tree": tree,
            "selected_file": file,
        }
    )

def terminal(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project_path = settings.PROJECTS_DIR / project.name
    output = ""

    if request.method == "POST":
        command = request.POST.get("command", "").strip()
        action = request.POST.get("action")
        env = os.environ.copy()
        env.pop("DJANGO_SETTINGS_MODULE", None)
        env["PYTHONPATH"] = str(project_path)

        if action == "stop":
            process = running_servers.get(project_id)
            if process and process.poll() is None:
                process.terminate()
                process.wait()
                del running_servers[project_id]
                output = "Server stopped."
            else:
                output = "No server is running."

        # Ignore empty form submissions when clicking "Run"
        elif not command:
            output = "Please enter a command."

        # Start Django server
        elif command == "python manage.py runserver":
            if project_id in running_servers:
                output = "Server is already running."
            else:
                process = subprocess.Popen(
                    [
                        "python",
                        "manage.py",
                        "runserver",
                        "8002",
                        "--noreload"
                    ],
                    cwd=project_path,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                running_servers[project_id] = process
                output = "Development server started on port 8002."

        else:
            try:
                # Use shlex.split to handle quoted arguments correctly (e.g., git commit -m "my commit")
                import shlex
                cmd_args = shlex.split(command)
                
                result = subprocess.run(
                    cmd_args,
                    cwd=project_path,
                    capture_output=True,
                    text=True,
                    env=env
                )
                output = result.stdout + result.stderr
                sync_project_files(project)
            except Exception as e:
                output = f"Error executing command: {str(e)}"

    server_running = (
        project_id in running_servers
        and running_servers[project_id].poll() is None
    )

    server_url = "http://127.0.0.1:8002/"

    return render(
        request,
        "terminal.html",
        {
            "output": output,
            "project": project,
            "server_running": server_running,
            "server_url": server_url,
        }
    )

def editor(request, project_id):

    project = get_object_or_404(
        Project,
        id=project_id
    )

    tree = build_file_tree(project)

    return render(
        request,
        "editor.html",
        {
            "project": project,
            "tree": tree,
        }
    )