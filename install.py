import os
import shutil
import subprocess
import sys
import platform
import argparse

def get_krita_dir():
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Windows":
        return os.path.join(os.getenv("APPDATA"), "krita", "pykrita")
    elif system == "Darwin": # macOS
        return os.path.join(home, "Library", "Application Support", "krita", "pykrita")
    else: # Linux
        return os.path.join(home, ".local", "share", "krita", "pykrita")

def check_package_installed(krita_dir, package_name, min_version=None):
    """Check if a package is already installed in the target directory.
    
    Returns True if package exists and (optionally) meets minimum version requirement.
    """
    import glob
    
    # Find the dist-info directory for the package
    pattern = os.path.join(krita_dir, f"{package_name}-*.dist-info")
    matches = glob.glob(pattern)
    
    if not matches:
        # Also check for the package directory itself
        pkg_dir = os.path.join(krita_dir, package_name)
        if os.path.isdir(pkg_dir):
            return True  # Package exists, version unknown
        return False
    
    # If no version check needed, package exists
    if min_version is None:
        return True
    
    # Parse version from dist-info directory name
    import re
    for match in matches:
        version_match = re.search(rf"{package_name}-(\d+\.\d+(?:\.\d+)?)", match)
        if version_match:
            installed_version = version_match.group(1)
            # Simple version comparison (works for major.minor.patch)
            installed_parts = [int(x) for x in installed_version.split('.')]
            min_parts = [int(x) for x in min_version.split('.')]
            # Pad to same length
            max_len = max(len(installed_parts), len(min_parts))
            installed_parts.extend([0] * (max_len - len(installed_parts)))
            min_parts.extend([0] * (max_len - len(min_parts)))
            if installed_parts >= min_parts:
                return True
    
    return False

def clean_pip_packages(krita_dir, packages_to_keep):
    """Remove old pip packages from target directory to avoid version conflicts."""
    # Common package directory names that might cause conflicts
    package_patterns = [
        "numpy", "numpy-*.dist-info",
        "PyOpenGL", "PyOpenGL-*.dist-info",
        "PyOpenGL_accelerate", "PyOpenGL_accelerate-*.dist-info",
        "matplotlib", "matplotlib-*.dist-info",
        "opencv", "opencv-*.dist-info",
        "cv2",
        "seaborn", "seaborn-*.dist-info",
        "types_seaborn", "types_seaborn-*.dist-info",
        "pandas", "pandas-*.dist-info",
        "pandas_stubs", "pandas_stubs-*.dist-info",
    ]

    import glob
    for pattern in package_patterns:
        for path in glob.glob(os.path.join(krita_dir, pattern)):
            if os.path.exists(path):
                print(f"Removing old package: {os.path.basename(path)}")
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Install Krita 3D Pose Plugin")
    parser.add_argument("--clean", action="store_true", help="Force clean old dependencies before installing")
    parser.add_argument("--force-deps", action="store_true", help="Force reinstall dependencies even if already present")
    args = parser.parse_args()
    
    project_dir = os.path.dirname(os.path.abspath(__file__))
    krita_dir = get_krita_dir()

    print(f"Installing to: {krita_dir}")

    os.makedirs(krita_dir, exist_ok=True)

    # Clean old pip packages only if --clean flag is provided
    if args.clean:
        print("Cleaning old dependencies...")
        clean_pip_packages(krita_dir, [])

    # Files/Folders to copy
    items = ["krita_3d_pose", "pose_engine", "poses"]
    files = ["krita_3d_pose.desktop"]

    for item in items:
        src = os.path.join(project_dir, item)
        dst = os.path.join(krita_dir, item)
        if os.path.exists(src):
            print(f"Copying {item}...")
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    for f in files:
        src = os.path.join(project_dir, f)
        dst = os.path.join(krita_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)

    # Check if dependencies need to be installed
    needs_numpy = args.force_deps or not check_package_installed(krita_dir, "numpy", "2.0.0")
    needs_pyopengl = args.force_deps or not check_package_installed(krita_dir, "PyOpenGL", "3.1.0")
    
    if not needs_numpy and not needs_pyopengl:
        print("All dependencies already installed. Skipping pip install.")
        print("Done! Restart Krita.")
        return

    # Dependencies with pinned versions for compatibility
    # numpy>=2.0,<2.3.0 required by opencv-python
    # We use numpy 2.2.x which satisfies this constraint
    #
    # IMPORTANT: Krita uses Python 3.10, so we need to download wheels for cp310
    # even if the system Python is a different version.
    # We use --python-version, --implementation, --abi, and --platform flags
    # to tell pip to download the correct wheel.

    # Detect platform for wheel selection
    system = platform.system()
    if system == "Linux":
        platform_tag = "manylinux_2_17_x86_64"
    elif system == "Windows":
        platform_tag = "win_amd64"
    elif system == "Darwin":
        # macOS - check for ARM vs Intel
        if platform.machine() == "arm64":
            platform_tag = "macosx_11_0_arm64"
        else:
            platform_tag = "macosx_10_9_x86_64"
    else:
        platform_tag = None

    # Base pip command with Python 3.10 targeting
    pip_base = [
        sys.executable, "-m", "pip", "install", "--upgrade",
        "--target", krita_dir,
        "--python-version", "3.10",
        "--implementation", "cp",
        "--abi", "cp310",
    ]

    if platform_tag:
        pip_base.extend(["--platform", platform_tag])

    # Build single combined pip command for all needed packages
    packages_to_install = []
    
    if needs_numpy:
        # numpy needs --only-binary for compiled extensions
        packages_to_install.append("numpy>=2.0.0,<2.3.0")
    
    if needs_pyopengl:
        packages_to_install.extend(["PyOpenGL>=3.1.0", "PyOpenGL_accelerate>=3.1.0"])

    if packages_to_install:
        print("Installing dependencies for Python 3.10 (Krita's Python version)...")
        print("Note: Warnings about system-wide packages can be ignored.")
        print("  These don't affect the plugin since Krita uses its own Python environment.")

        # Install numpy separately with --only-binary flag
        if needs_numpy:
            pip_cmd_numpy = pip_base + [
                "--only-binary", ":all:",
                "numpy>=2.0.0,<2.3.0"
            ]
            try:
                print("Installing numpy...")
                subprocess.check_call(pip_cmd_numpy)
            except subprocess.CalledProcessError:
                print("Failed to install numpy. Please ensure 'pip' is installed.")
                return

        # Install PyOpenGL (pure Python, no special flags needed)
        if needs_pyopengl:
            pip_cmd_pyopengl = [
                sys.executable, "-m", "pip", "install", "--upgrade",
                "--target", krita_dir,
                "PyOpenGL>=3.1.0",
                "PyOpenGL_accelerate>=3.1.0"
            ]
            try:
                print("Installing PyOpenGL...")
                subprocess.check_call(pip_cmd_pyopengl)
            except subprocess.CalledProcessError:
                print("Failed to install PyOpenGL. Please ensure 'pip' is installed.")
                return

    print("Done! Restart Krita.")

if __name__ == "__main__":
    main()