from django.urls import path
from . import views

urlpatterns = [
    path(
        "",
        views.project_list,
        name="project_list"
    ),
    path(
        "project/<int:project_id>/",
        views.editor,
        name="editor"
    ),

    path(
        "file/<int:file_id>/",
        views.open_file,
        name="open_file"
    ),

    path(
        "file/<int:file_id>/save/",
        views.save_file,
        name="save_file"
    ),

    path(
        "new_project/",
        views.create_project,
        name="new_project"
    ),

    path(
        "terminal/<int:project_id>/",
        views.terminal,
        name="terminal"
    ),

    path(
        "project/<int:project_id>/create-file/",
        views.create_file,
        name="create_file"
    ),

    path(
        "project/<int:project_id>/create-folder/",
        views.create_folder,
        name="create_folder"
    ),
]