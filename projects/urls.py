from django.urls import path
from . import views

app_name = 'projects'

urlpatterns = [
    # Project CRUD endpoints
    path('', views.project_list, name='project_list'),  # GET: list, POST: create
    path('<int:project_id>/', views.project_detail, name='project_detail'),  # GET: detail
    
    # Project action endpoints
    path('<int:project_id>/upload_code/', views.upload_code, name='upload_code'),  # POST: upload files
    path('<int:project_id>/scan/', views.scan_project, name='scan_project'),  # POST: trigger scan
    path('<int:project_id>/convert/', views.convert_project, name='convert_project'),  # POST: trigger conversion
    path('<int:project_id>/download/', views.download_project, name='download_project'),  # GET: download ZIP
    path('<int:project_id>/upload_to_drive/', views.upload_to_drive, name='upload_to_drive'),  # POST: upload to Google Drive
] 