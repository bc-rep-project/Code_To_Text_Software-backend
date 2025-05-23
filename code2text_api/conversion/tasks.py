"""
Celery tasks for code-to-text conversion.
"""

import os
import logging
import shutil
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

@shared_task
def convert_repository_to_text(conversion_id):
    """
    Convert a repository to text files.
    
    Args:
        conversion_id: ID of the conversion to process.
    """
    # Import here to avoid circular imports
    from .models import Conversion
    
    try:
        # Get the conversion
        conversion = Conversion.objects.get(id=conversion_id)
        
        # Update status
        conversion.status = 'in_progress'
        conversion.save()
        
        repository = conversion.repository
        
        # Check if repository exists
        if not repository.storage_path or not os.path.exists(repository.storage_path):
            raise Exception("Repository storage path not found")
        
        # Create output directory
        output_dir = os.path.join(settings.CONVERTED_STORAGE_PATH, f"conversion_{conversion.id}")
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert files
        convert_directory(repository.storage_path, output_dir)
        
        # Update conversion
        conversion.status = 'completed'
        conversion.end_time = timezone.now()
        conversion.result_path = output_dir
        conversion.save()
        
        return True
    except Exception as e:
        logger.error(f"Error in conversion task: {str(e)}")
        
        try:
            # Update conversion with error
            conversion = Conversion.objects.get(id=conversion_id)
            conversion.status = 'failed'
            conversion.error_message = str(e)
            conversion.end_time = timezone.now()
            conversion.save()
        except Exception as inner_e:
            logger.error(f"Error updating conversion status: {str(inner_e)}")
        
        return False


def convert_directory(input_dir, output_dir):
    """
    Recursively convert all files in a directory to text files.
    
    Args:
        input_dir: Input directory path.
        output_dir: Output directory path.
    """
    for root, dirs, files in os.walk(input_dir):
        # Skip .git directory
        if '.git' in root:
            continue
        
        # Create corresponding output directory
        rel_path = os.path.relpath(root, input_dir)
        curr_output_dir = os.path.join(output_dir, rel_path)
        os.makedirs(curr_output_dir, exist_ok=True)
        
        # Convert each file
        for file in files:
            input_file = os.path.join(root, file)
            
            # Skip binary files
            if is_binary_file(input_file):
                continue
            
            # Create output file name (preserve extension in filename but add .txt)
            output_file = os.path.join(curr_output_dir, f"{file}.txt")
            
            try:
                convert_file_to_text(input_file, output_file)
            except Exception as e:
                logger.error(f"Error converting file {input_file}: {str(e)}")


def convert_file_to_text(input_file, output_file):
    """
    Convert a file to text.
    
    Args:
        input_file: Input file path.
        output_file: Output file path.
    """
    try:
        with open(input_file, 'r', encoding='utf-8', errors='replace') as f_in:
            content = f_in.read()
        
        with open(output_file, 'w', encoding='utf-8') as f_out:
            # Add a header with original filename and path
            f_out.write(f"# Original file: {os.path.basename(input_file)}\n")
            f_out.write(f"# Original path: {os.path.dirname(input_file)}\n")
            f_out.write(f"# Converted at: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f_out.write("#" + "-" * 50 + "\n\n")
            f_out.write(content)
    
    except Exception as e:
        logger.error(f"Error in convert_file_to_text: {str(e)}")
        raise


def is_binary_file(file_path):
    """
    Check if a file is binary.
    
    Args:
        file_path: Path to the file.
    
    Returns:
        bool: True if the file is binary, False otherwise.
    """
    # Common binary file extensions
    binary_extensions = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
        '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
        '.zip', '.tar', '.gz', '.tgz', '.rar', '.7z',
        '.exe', '.dll', '.so', '.dylib',
        '.pyc', '.pyo', '.pyd',
        '.class',
        '.jar', '.war', '.ear',
        '.mp3', '.mp4', '.avi', '.mov', '.flv', '.wmv',
    }
    
    # Check extension
    _, ext = os.path.splitext(file_path)
    if ext.lower() in binary_extensions:
        return True
    
    # Check file content (first few bytes)
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk  # If null byte is found, it's likely binary
    except Exception:
        return True  # If we can't read the file, assume it's binary 