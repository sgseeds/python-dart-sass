"""
Compiler path detection for the embedded Sass compiler.
"""

import os
import platform
import sys
from pathlib import Path
from typing import List, Optional
import shutil


def _detect_platform() -> str:
    """
    Detect the platform string for the compiler module.
    
    Returns:
        Platform string like 'linux-x64', 'darwin-arm64', etc.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize architecture names
    arch_map = {
        'x86_64': 'x64',
        'amd64': 'x64',
        'i386': 'x32',
        'i686': 'x32',
        'aarch64': 'arm64',
        'arm64': 'arm64',
        'armv7l': 'arm',
        'armv6l': 'arm',
        'riscv64': 'riscv64',
    }
    
    arch = arch_map.get(machine, machine)
    
    # Handle special cases
    if system == 'linux':
        # TODO: Detect musl vs glibc
        # For now, assume glibc
        return f"linux-{arch}"
    elif system == 'darwin':
        return f"darwin-{arch}"
    elif system == 'windows':
        return f"win32-{arch}"
    else:
        return f"{system}-{arch}"


def _get_compiler_module_name() -> str:
    """
    Get the compiler module name for the current platform.
    
    Returns:
        Module name like 'sass-embedded-linux-x64'
    """
    platform_str = _detect_platform()
    return f"sass-embedded-{platform_str}"


def _find_dart_sass_executable() -> Optional[List[str]]:
    """
    Find the Dart Sass executable in various locations.
    
    Returns:
        List of command parts [executable, snapshot] or None if not found
    """
    # Try to find dart executable and sass.snapshot
    dart_exe = shutil.which('dart')
    if dart_exe:
        # Look for sass.snapshot in common locations
        possible_snapshot_paths = [
            # Node.js sass-embedded installation
            Path.home() / '.local/share/mise/installs/node/22.16.0/lib/node_modules/sass-embedded/node_modules/sass-embedded-linux-x64/dart-sass/src/sass.snapshot',
            # Global pub cache
            Path.home() / '.pub-cache' / 'global_packages' / 'sass' / 'bin' / 'sass.snapshot',
            # Local installation
            Path.cwd() / 'sass.snapshot',
            # System installation
            Path('/usr/local/lib/sass/sass.snapshot'),
            Path('/usr/lib/sass/sass.snapshot'),
        ]
        
        for snapshot_path in possible_snapshot_paths:
            if snapshot_path.exists():
                return [dart_exe, str(snapshot_path)]
    
    # Try to find Node.js sass-embedded dart executable directly
    node_sass_dart = Path.home() / '.local/share/mise/installs/node/22.16.0/lib/node_modules/sass-embedded/node_modules/sass-embedded-linux-x64/dart-sass/src/dart'
    node_sass_snapshot = Path.home() / '.local/share/mise/installs/node/22.16.0/lib/node_modules/sass-embedded/node_modules/sass-embedded-linux-x64/dart-sass/src/sass.snapshot'
    if node_sass_dart.exists() and node_sass_snapshot.exists():
        return [str(node_sass_dart), str(node_sass_snapshot)]
    
    # Try to find sass executable directly, but exclude our own Python script
    sass_exe = shutil.which('sass')
    if sass_exe:
        # Check if it's a Python script (our own CLI)
        try:
            with open(sass_exe, 'r') as f:
                first_line = f.readline().strip()
                # If it's a Python script, skip it
                if first_line.startswith('#!') and 'python' in first_line:
                    pass  # Skip our own Python script
                else:
                    return [sass_exe]
        except (IOError, OSError, UnicodeDecodeError):
            # If we can't read it, assume it's a binary and try it
            return [sass_exe]
    
    # Try to find dart-sass executable
    dart_sass_exe = shutil.which('dart-sass')
    if dart_sass_exe:
        return [dart_sass_exe]
    
    return None


def get_compiler_command() -> List[str]:
    """
    Get the full command for the embedded compiler executable.
    
    Returns:
        List of command parts to execute the compiler
        
    Raises:
        RuntimeError: If no suitable compiler is found
    """
    # First, try to use environment variable override
    compiler_path = os.environ.get('SASS_EMBEDDED_COMPILER_PATH')
    if compiler_path:
        if os.path.isfile(compiler_path) and os.access(compiler_path, os.X_OK):
            return [compiler_path]
        else:
            raise RuntimeError(f"SASS_EMBEDDED_COMPILER_PATH points to invalid executable: {compiler_path}")
    
    # Try to find platform-specific embedded compiler package
    # This would be installed as optional dependencies
    module_name = _get_compiler_module_name()
    
    try:
        # Try to import the platform-specific module
        import importlib
        module = importlib.import_module(module_name.replace('-', '_'))
        
        # Look for the executable in the module
        module_path = Path(module.__file__).parent
        
        # Try dart + sass.snapshot first (preferred approach)
        dart_exe = module_path / 'dart-sass/src/dart'
        if platform.system().lower() == 'windows':
            dart_exe = module_path / 'dart-sass/src/dart.exe'
        
        snapshot_path = module_path / 'dart-sass/src/sass.snapshot'
        if dart_exe.exists() and snapshot_path.exists() and os.access(dart_exe, os.X_OK):
            return [str(dart_exe), str(snapshot_path)]
        
        # Try sass executable as fallback
        sass_exe = module_path / 'dart-sass/sass'
        if platform.system().lower() == 'windows':
            sass_exe = module_path / 'dart-sass/sass.bat'
        
        if sass_exe.exists() and os.access(sass_exe, os.X_OK):
            return [str(sass_exe)]
        
    except ImportError:
        # Platform-specific module not available
        pass
    
    # Try to find system-installed Dart Sass
    system_command = _find_dart_sass_executable()
    if system_command:
        return system_command
    
    # Try fallback to regular sass package (pure JS implementation)
    try:
        import sass
        sass_js_path = Path(sass.__file__).parent / 'sass.js'
        if sass_js_path.exists():
            node_exe = shutil.which('node')
            if node_exe:
                return [node_exe, str(sass_js_path)]
    except ImportError:
        pass
    
    # No compiler found
    raise RuntimeError(
        f"Embedded Dart Sass couldn't find the embedded compiler executable. "
        f"Please install the optional dependency {module_name} or ensure "
        f"'dart' and 'sass' are available in your PATH, or set "
        f"SASS_EMBEDDED_COMPILER_PATH environment variable."
    )
