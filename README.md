# Krita 3D Pose Plugin

<p align="center">
  <img src="img/logo.png" alt="3D Pose Plugin Logo" width="200">
</p>

A Krita plugin for 3D character posing with skeletal animation support, and multi-model scene management.

## Features

- **3D Model Loading** - Import GLB/glTF models with skeletal animations
- **Transform Gizmos** - Interactive translation, rotation, and scale tools
- **Multi-Model Support** - Pose multiple characters in a single scene
- **Viewport Rendering** - OpenGL-accelerated real-time preview

## Screenshot

![Usage Example](img/usage%20example.png)

## Requirements

- Krita >= 5.0.0
- Python >= 3.8
- PyQt5 >= 5.15.0
- PyOpenGL >= 3.1.0
- NumPy >= 1.20.0

## Installation

Run the provided install script:

```bash
./install_to_krita.sh
```

This script will:
- Copy plugin files (`krita_3d_pose`, `pose_engine`, `poses`)
- Copy the `.desktop` file
- Install Python dependencies (PyOpenGL, numpy) to Krita's plugin directory

After installation, restart Krita and enable the **3D Editor** docker from `Settings → Dockers → 3D Editor`

## License

MIT License
