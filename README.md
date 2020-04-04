# alphamesh-addon
A Blender (2.8x) addon to create concave hulls (alpha-shapes)

![Demo](./images/Screenshot%202020-03-15%20at%2014.25.53.png)

## Installation:

To be able to use the AlphaMesh addon you will have to install scipy into your Blender's python. If you want to find out, where your Blender's python is try this in Scripting:

```(python)
>>> bpy.app.binary_path_python
'.../.../python3.7m'
```

### SciPy installation for MacOS

```(bash)
/Applications/.../Blender.app/Contents/Resources/2.83/python/bin/python3.7m -m pip install --user scipy
```

### SciPy installation for Windows

```(cmd)
C:\Program Files\Blender Foundation\Blender 2.82\2.82\python\bin\python.exe" -m pip install --user scipy
```

### Addon installation

To install the Addon just go to Preferences, Install Addon...


## Usage:

You'll find a section called "AlphaMesh addon" in Object Properties. This will be active when you select an AlphaMesh object (you find them in Add->Mesh->AlphaMesh). Just select an object and then its particle system. The Alpha value defines how concave the mesh will be.

![Adding](./images/Screenshot%202020-03-15%20at%2014.20.26.png)

![Adding](./images/Screenshot%202020-03-15%20at%2014.25.48.png)

