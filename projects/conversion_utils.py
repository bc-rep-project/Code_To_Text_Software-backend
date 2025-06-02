import os
import shutil
import logging
import tempfile
import zipfile
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class CodebaseConverter:
    """
    Converts all files in a repository to text format while preserving directory structure.
    
    This class handles the conversion of source code files to .txt format, with proper
    handling of binary files, encoding issues, and directory exclusions.
    """
    
    # Directories to exclude from conversion
    EXCLUDED_DIRS = {
        '.git', '.hg', '.svn', '.bzr',  # Version control
        '__pycache__', '.pytest_cache', '.tox',  # Python cache
        'node_modules', '.npm', 'dist', 'build',  # Node.js
        '.vscode', '.idea', '.vs',  # IDE directories
        'vendor', 'packages',  # Package directories  
        '.DS_Store', 'Thumbs.db',  # OS files
        'venv', 'env', '.env',  # Virtual environments
        'target', 'bin', 'obj',  # Build outputs
        '.gradle', '.m2',  # Build tools
        'coverage', '.nyc_output',  # Coverage reports
    }
    
    # File extensions to exclude (binary files)
    EXCLUDED_EXTENSIONS = {
        # Executables and binaries
        '.exe', '.dll', '.so', '.dylib', '.a', '.lib', '.o', '.obj', '.bin',
        # Archives
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.7z', '.rar', '.iso',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.ico', '.webp', '.tiff',
        # Videos
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv', '.m4v',
        # Audio
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma', '.m4a',
        # Documents (binary)
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        # Fonts
        '.ttf', '.otf', '.woff', '.woff2', '.eot',
        # Database files
        '.db', '.sqlite', '.sqlite3', '.mdb',
        # Other binary formats
        '.jar', '.war', '.ear', '.class', '.pyc', '.pyo', '.pyd',
        '.swf', '.fla', '.psd', '.ai', '.sketch',
    }
    
    # Text file extensions that should definitely be converted
    TEXT_EXTENSIONS = {
        # Source code
        '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp',
        '.cs', '.vb', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.scala', '.clj', '.elm',
        '.dart', '.lua', '.perl', '.pl', '.r', '.sh', '.bash', '.zsh', '.fish', '.ps1',
        # Web technologies
        '.html', '.htm', '.css', '.scss', '.sass', '.less', '.xml', '.xsl', '.xslt',
        # Configuration and data
        '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf', '.properties',
        '.env', '.gitignore', '.gitattributes', '.dockerignore', '.editorconfig',
        # Documentation
        '.md', '.rst', '.txt', '.rtf', '.tex', '.adoc', '.org',
        # Build files
        '.makefile', '.cmake', '.gradle', '.sbt', '.pom', '.gemspec', '.podspec',
        # Others
        '.sql', '.graphql', '.proto', '.thrift', '.avro', '.zig', '.nim', '.crystal',
    }
    
    def __init__(self, source_directory: str, output_base_directory: str):
        """
        Initialize the converter.
        
        Args:
            source_directory: Path to the source repository/codebase
            output_base_directory: Base directory for conversion output
        """
        self.source_directory = Path(source_directory).resolve()
        self.output_base_directory = Path(output_base_directory).resolve()
        self.stats = {
            'total_files_processed': 0,
            'files_converted': 0,
            'files_skipped_binary': 0,
            'files_skipped_encoding': 0,
            'files_skipped_excluded': 0,
            'total_size_bytes': 0,
            'directories_processed': 0,
            'conversion_errors': []
        }
        
    def convert_repository_to_text(self) -> Tuple[str, Dict]:
        """
        Convert all files in the repository to text format.
        
        Returns:
            Tuple of (converted_directory_path, conversion_stats)
        """
        start_time = datetime.now()
        
        # Create output directory
        project_basename = self.source_directory.name
        converted_project_path = self.output_base_directory / f"{project_basename}_converted"
        
        # Clean up existing output if it exists
        if converted_project_path.exists():
            shutil.rmtree(converted_project_path)
        converted_project_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Starting conversion of {self.source_directory} to {converted_project_path}")
        
        # Process all files
        self._process_directory(self.source_directory, converted_project_path)
        
        # Calculate conversion duration
        duration = (datetime.now() - start_time).total_seconds()
        self.stats['conversion_duration_seconds'] = duration
        
        # Create conversion summary
        self._create_conversion_summary(converted_project_path)
        
        logger.info(f"Conversion completed in {duration:.2f}s. "
                   f"Converted {self.stats['files_converted']} files, "
                   f"skipped {self.stats['files_skipped_binary'] + self.stats['files_skipped_encoding']} files")
        
        return str(converted_project_path), self.stats
    
    def _process_directory(self, source_dir: Path, target_dir: Path):
        """
        Recursively process a directory and convert files.
        
        Args:
            source_dir: Source directory path
            target_dir: Target directory path
        """
        try:
            for item in source_dir.iterdir():
                if item.is_dir():
                    # Skip excluded directories
                    if item.name in self.EXCLUDED_DIRS or item.name.startswith('.'):
                        logger.debug(f"Skipping excluded directory: {item}")
                        continue
                    
                    # Create corresponding directory in target
                    new_target_dir = target_dir / item.name
                    new_target_dir.mkdir(exist_ok=True)
                    self.stats['directories_processed'] += 1
                    
                    # Recursively process subdirectory
                    self._process_directory(item, new_target_dir)
                    
                elif item.is_file():
                    self._process_file(item, target_dir)
                    
        except PermissionError as e:
            logger.warning(f"Permission denied accessing directory {source_dir}: {e}")
            self.stats['conversion_errors'].append(f"Permission denied: {source_dir}")
        except Exception as e:
            logger.error(f"Error processing directory {source_dir}: {e}")
            self.stats['conversion_errors'].append(f"Directory error {source_dir}: {str(e)}")
    
    def _process_file(self, source_file: Path, target_dir: Path):
        """
        Process a single file and convert it to text format.
        
        Args:
            source_file: Source file path
            target_dir: Target directory path
        """
        self.stats['total_files_processed'] += 1
        
        try:
            # Get file size
            file_size = source_file.stat().st_size
            self.stats['total_size_bytes'] += file_size
            
            # Skip very large files (>10MB) that might be binaries
            if file_size > 10 * 1024 * 1024:
                logger.info(f"Skipping large file (>10MB): {source_file}")
                self.stats['files_skipped_binary'] += 1
                return
            
            # Check if file should be excluded by extension
            file_extension = source_file.suffix.lower()
            if file_extension in self.EXCLUDED_EXTENSIONS:
                logger.debug(f"Skipping binary file by extension: {source_file}")
                self.stats['files_skipped_binary'] += 1
                return
            
            # Create target file path
            base_filename = source_file.stem  # filename without extension
            target_file = target_dir / f"{base_filename}.txt"
            
            # Handle filename conflicts
            counter = 1
            original_target = target_file
            while target_file.exists():
                target_file = target_dir / f"{base_filename}_{counter}.txt"
                counter += 1
            
            # Try to convert the file
            if self._convert_file_to_text(source_file, target_file):
                self.stats['files_converted'] += 1
            else:
                self.stats['files_skipped_encoding'] += 1
                
        except Exception as e:
            logger.error(f"Error processing file {source_file}: {e}")
            self.stats['conversion_errors'].append(f"File error {source_file}: {str(e)}")
    
    def _convert_file_to_text(self, source_file: Path, target_file: Path) -> bool:
        """
        Convert a single file to text format.
        
        Args:
            source_file: Source file path
            target_file: Target text file path
            
        Returns:
            True if conversion was successful, False otherwise
        """
        try:
            # First, try to detect if it's a binary file by reading a sample
            if self._is_binary_file(source_file):
                logger.debug(f"Skipping binary file: {source_file}")
                self._create_placeholder_file(source_file, target_file, "Binary file")
                return False
            
            # Try to read and convert the file
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings_to_try:
                try:
                    with open(source_file, 'r', encoding=encoding) as f:
                        content = f.read()
                    
                    # Create header with file information
                    header = self._create_file_header(source_file, encoding)
                    
                    # Write converted content
                    with open(target_file, 'w', encoding='utf-8') as f:
                        f.write(header)
                        f.write(content)
                    
                    logger.debug(f"Successfully converted {source_file} using {encoding} encoding")
                    return True
                    
                except UnicodeDecodeError:
                    continue  # Try next encoding
                except Exception as e:
                    logger.warning(f"Error reading {source_file} with {encoding}: {e}")
                    continue
            
            # If all encodings failed, create a placeholder
            logger.warning(f"Could not decode file with any encoding: {source_file}")
            self._create_placeholder_file(source_file, target_file, "Could not decode with any encoding")
            return False
            
        except Exception as e:
            logger.error(f"Error converting file {source_file}: {e}")
            self._create_placeholder_file(source_file, target_file, f"Conversion error: {str(e)}")
            return False
    
    def _is_binary_file(self, file_path: Path) -> bool:
        """
        Check if a file is binary by examining its content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file appears to be binary
        """
        try:
            # Read first 8192 bytes
            with open(file_path, 'rb') as f:
                chunk = f.read(8192)
            
            # If file is empty, it's not binary
            if not chunk:
                return False
            
            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True
            
            # Check ratio of non-printable characters
            text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
            non_text_count = sum(1 for byte in chunk if byte not in text_chars)
            
            # If more than 30% non-text characters, consider it binary
            return non_text_count / len(chunk) > 0.30
            
        except Exception:
            # If we can't read it, assume it's binary
            return True
    
    def _create_file_header(self, source_file: Path, encoding: str) -> str:
        """
        Create a header for the converted text file.
        
        Args:
            source_file: Original source file path
            encoding: Encoding used for conversion
            
        Returns:
            Header string
        """
        relative_path = source_file.relative_to(self.source_directory)
        file_size = source_file.stat().st_size
        
        header = f"""// ======================================
// Original file: {relative_path}
// File size: {file_size} bytes
// Encoding: {encoding}
// Converted on: {datetime.now().isoformat()}
// ======================================

"""
        return header
    
    def _create_placeholder_file(self, source_file: Path, target_file: Path, reason: str):
        """
        Create a placeholder file for files that couldn't be converted.
        
        Args:
            source_file: Original source file path
            target_file: Target placeholder file path
            reason: Reason for creating placeholder
        """
        try:
            relative_path = source_file.relative_to(self.source_directory)
            file_size = source_file.stat().st_size
            
            placeholder_content = f"""// ======================================
// PLACEHOLDER FILE
// ======================================
// Original file: {relative_path}
// File size: {file_size} bytes
// Reason: {reason}
// Created on: {datetime.now().isoformat()}
// ======================================

This file could not be converted to text format.
Original file: {source_file.name}
Reason: {reason}

If this file is important for your codebase documentation,
you may need to handle it manually.
"""
            
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(placeholder_content)
                
        except Exception as e:
            logger.error(f"Error creating placeholder file {target_file}: {e}")
    
    def _create_conversion_summary(self, output_dir: Path):
        """
        Create a summary file with conversion statistics.
        
        Args:
            output_dir: Output directory path
        """
        try:
            summary_file = output_dir / "CONVERSION_SUMMARY.txt"
            
            summary_content = f"""# Codebase Conversion Summary

## Conversion Details
- Source Directory: {self.source_directory}
- Output Directory: {output_dir}
- Conversion Date: {datetime.now().isoformat()}
- Conversion Duration: {self.stats.get('conversion_duration_seconds', 0):.2f} seconds

## Statistics
- Total Files Processed: {self.stats['total_files_processed']}
- Files Successfully Converted: {self.stats['files_converted']}
- Files Skipped (Binary): {self.stats['files_skipped_binary']}
- Files Skipped (Encoding Issues): {self.stats['files_skipped_encoding']}
- Files Skipped (Excluded): {self.stats['files_skipped_excluded']}
- Total Size Processed: {self.stats['total_size_bytes'] / 1024 / 1024:.2f} MB
- Directories Processed: {self.stats['directories_processed']}

## Conversion Rate
- Success Rate: {(self.stats['files_converted'] / max(self.stats['total_files_processed'], 1)) * 100:.1f}%

## Excluded Directories
{', '.join(sorted(self.EXCLUDED_DIRS))}

## Excluded File Extensions
{', '.join(sorted(self.EXCLUDED_EXTENSIONS))}
"""

            if self.stats['conversion_errors']:
                summary_content += "\n## Conversion Errors\n"
                for error in self.stats['conversion_errors'][:10]:  # Limit to first 10 errors
                    summary_content += f"- {error}\n"
                if len(self.stats['conversion_errors']) > 10:
                    summary_content += f"... and {len(self.stats['conversion_errors']) - 10} more errors\n"
            
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_content)
                
        except Exception as e:
            logger.error(f"Error creating conversion summary: {e}")


def create_conversion_zip(converted_directory: str, project_name: str) -> str:
    """
    Create a ZIP file from the converted directory.
    
    Args:
        converted_directory: Path to the converted files directory
        project_name: Name of the project for the ZIP file
        
    Returns:
        Path to the created ZIP file
    """
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, f"{project_name}_converted.zip")
    
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            converted_path = Path(converted_directory)
            
            for file_path in converted_path.rglob('*'):
                if file_path.is_file():
                    # Create relative path within the ZIP
                    arcname = file_path.relative_to(converted_path)
                    zipf.write(file_path, arcname)
        
        logger.info(f"Created conversion ZIP file: {zip_path}")
        return zip_path
        
    except Exception as e:
        logger.error(f"Error creating ZIP file: {e}")
        raise


def perform_codebase_conversion(project, source_directory: str) -> Dict:
    """
    Perform the complete codebase conversion process.
    
    Args:
        project: Django project instance
        source_directory: Path to the source code directory
        
    Returns:
        Dictionary with conversion results
    """
    try:
        # Create temporary output directory
        with tempfile.TemporaryDirectory(prefix="conversion_") as temp_output_base:
            # Initialize converter
            converter = CodebaseConverter(source_directory, temp_output_base)
            
            # Perform conversion
            converted_dir, stats = converter.convert_repository_to_text()
            
            # Create ZIP file
            zip_path = create_conversion_zip(converted_dir, project.project_name)
            
            return {
                'success': True,
                'zip_path': zip_path,
                'stats': stats
            }
            
    except Exception as e:
        logger.error(f"Codebase conversion failed for project {project.id}: {e}")
        return {
            'success': False,
            'error': str(e)
        } 