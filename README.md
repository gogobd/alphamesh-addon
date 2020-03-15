# alphamesh-addon
A Blender (2.8x) addon to create concave hulls (alpha-shapes)

![Demo](./images/Screenshot%202020-03-15%20at%2014.25.53.png)

## Installation:

To be able to use the AlphaMesh addon you will have to install scipy into your Blender's python.

### MacOS

```(bash)
/Applications/.../Blender.app/Contents/Resources/2.83/python/bin/python3.7m -m pip install --user scipy
```

### Windows

```(cmd)
C:\Program Files\Blender Foundation\Blender 2.82\2.82\python\bin\python.exe" -m pip install --user scipy
```


## Usage:

You'll find a section called "AlphaMesh addon" in Object Properties. This will be active when you select an AlphaMesh object (you find them in Add->Mesh->AlphaMesh). Just select an object and then its particle system.

![Adding](./images/Screenshot%202020-03-15%20at%2014.20.26.png)

![Adding](./images/Screenshot%202020-03-15%20at%2014.25.48.png)

