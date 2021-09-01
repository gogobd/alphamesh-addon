# AlphaMesh Addon by Gogo.

bl_info = {
    "name": "Alpha Mesh addon",
    "author": "Georg Gogo. BERNHARD <gogo@bluedynamics.com>",
    "version": (0, 2, 2),
    "blender": (2, 82, 0),
    "location": "Properties > Object Tab",
    "description": ("Alpha Mesh addon (using SciPy)"),
    "warning": "",  # used for warning icon and text in addons panel
    "wiki_url": "",
    "tracker_url": "",
    "category": "Object"}

import bpy

import os
import sys
import time
import math
import ctypes
from math import ceil, floor
from collections import defaultdict

import bmesh
from bpy.types import Operator, Panel, UIList
from bpy.props import FloatVectorProperty, IntProperty, StringProperty, FloatProperty, BoolProperty, CollectionProperty
from bpy_extras.object_utils import AddObjectHelper, object_data_add

try:
    import numpy as np
    from scipy.spatial import Delaunay
except ImportError as e:
    bpy_executable = bpy.app.binary_path_python
    hint = """
    ERROR: Alphamesh addon could not be installed
    Run this and try again:
    %(bpy_executable)s -m ensurepip
    %(bpy_executable)s -m pip install --upgrade pip
    %(bpy_executable)s -m pip install --force scipy
    This will install scipy into your Blender's python.
    """ % {'bpy_executable': bpy_executable}
    print(hint)
    os.system("%(bpy_executable)s -m ensurepip && %(bpy_executable)s -m pip install --upgrade pip && %(bpy_executable)s -m pip install --force scipy" % {'bpy_executable': bpy_executable})
    import numpy as np
    from scipy.spatial import Delaunay


DEFAULT_QHULL_OPTIONS='Qbb Qc Qz Qx Q12'
current_frame = -2
IS_RENDERING = False


class Timer(object):

    def __init__(self):
        self.start_time = time.time()
        self.last_lap = self.start_time
        pass

    def lap(self):
        now = time.time()
        res = now - self.last_lap
        self.last_lap = now
        return res

    def stop(self):
        now = time.time()
        return now - self.start_time


def add_alphamesh(self, context):
    mesh = bpy.data.meshes.new(name="AlphaMesh")
    obj = bpy.data.objects.new("AlphaMesh", mesh)
    bpy.context.collection.objects.link(obj)
    # context.view_layer.objects.active = obj
    # bpy.ops.outliner.item_activate(extend=False, deselect_all=True)
    obj['isAlphaMesh'] = True
    obj.AlphaMesh_active = True
    obj.AlphaMesh_res = 1.0
    obj.AlphaMesh_outeronly = True
    obj.AlphaMesh_smooth = True
    obj.shape_key_add(name="Base")
    obj['qhull_options'] = DEFAULT_QHULL_OPTIONS


class OBJECT_OT_add_alphamesh(Operator, AddObjectHelper):
    """Create a new Alpha Mesh Object"""
    bl_idname = "mesh.add_alphamesh"
    bl_label = "Add alphamesh Object"
    bl_options = {'REGISTER', 'UNDO'}

    scale = FloatVectorProperty(
        name="scale",
        default=(1.0, 1.0, 1.0),
        subtype='TRANSLATION',
        description="scaling",
    )

    def execute(self, context):
        add_alphamesh(self, context)
        return {'FINISHED'}


def add_alphamesh_button(self, context):
    self.layout.operator(
        OBJECT_OT_add_alphamesh.bl_idname,
        text="AlphaMesh",
        icon='OUTLINER_DATA_META')


def alphamesh_prerender(context, depsgraph):
    global IS_RENDERING
    IS_RENDERING = True
    print("_prerender context:", context)
    print("_prerender depsgraph:", depsgraph)
    alphamesh(context, depsgraph)


def alphamesh_postrender(context, depsgraph):
    global IS_RENDERING
    IS_RENDERING = False
    print("_postrender context:", context)
    print("_postrender depsgraph:", depsgraph)
    alphamesh(context, depsgraph)


def alphamesh_frame(context, depsgraph):
    print("_frame context:", context)
    print("_frame depsgraph:", depsgraph)
    alphamesh(context, depsgraph)


def alpha_shape_3D(pos, alpha, options, only_outer=True):
    """
    Compute the alpha shape (concave hull) of a set of 3D points.
    Parameters:
        pos - np.array of shape (n,3) points.
        alpha - alpha value.
    return
        outer surface vertex indices, edge indices, and triangle indices
    """

    tetra = Delaunay(pos, qhull_options=options)
    # Find radius of the circumsphere.
    # By definition, radius of the sphere fitting inside the tetrahedral needs 
    # to be smaller than alpha value
    # http://mathworld.wolfram.com/Circumsphere.html
    tetrapos = np.take(pos,tetra.vertices,axis=0)
    normsq = np.sum(tetrapos**2,axis=2)[:,:,None]
    ones = np.ones((tetrapos.shape[0],tetrapos.shape[1],1))
    a = np.linalg.det(np.concatenate((tetrapos,ones),axis=2))
    Dx = np.linalg.det(np.concatenate((normsq,tetrapos[:,:,[1,2]],ones),axis=2))
    Dy = -np.linalg.det(np.concatenate((normsq,tetrapos[:,:,[0,2]],ones),axis=2))
    Dz = np.linalg.det(np.concatenate((normsq,tetrapos[:,:,[0,1]],ones),axis=2))
    c = np.linalg.det(np.concatenate((normsq,tetrapos),axis=2))
    r = np.sqrt(Dx**2+Dy**2+Dz**2-4*a*c)/(2*np.abs(a))

    # Find tetrahedrals
    tetras = tetra.vertices[r<alpha,:]

    # triangles
    TriComb = np.array([(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)])
    Triangles = tetras[:,TriComb].reshape(-1,3)
    Triangles = np.sort(Triangles,axis=1)
    if only_outer:
        # Remove triangles that occurs twice, because they are within shapes
        TrianglesDict = defaultdict(int)
        for tri in Triangles:TrianglesDict[tuple(tri)] += 1
        Triangles=np.array([tri for tri in TrianglesDict if TrianglesDict[tri] == 1])
    #edges
    EdgeComb=np.array([(0, 1), (0, 2), (1, 2)])
    Edges=Triangles[:,EdgeComb].reshape(-1,2)
    Edges=np.sort(Edges,axis=1)
    Edges=np.unique(Edges,axis=0)
    Triangles=np.sort(Triangles,axis=1)
    Triangles=np.unique(Triangles,axis=0)
    Vertices = np.unique(Edges)
    return Vertices,Edges,Triangles


def alphamesh(context, depsgraph):
    global current_frame

    scn = bpy.context.scene
    active_before = bpy.context.view_layer.objects.active

    print("context arg is  ", context)
    print("depsgraph arg is", depsgraph)
    print("bpy depsgraph is", bpy.context.evaluated_depsgraph_get())

    if depsgraph is None:
        if IS_RENDERING:
            return
        else:
            depsgraph = bpy.context.evaluated_depsgraph_get()

    depsgraph.update()

    if current_frame == scn.frame_current:
        print("Skipping recalculation of frame %d." % current_frame)
        return
    timer = Timer()
    print("Starting AlphaMesh calcs...")
    AlphaMesh_infos = []
    for object in bpy.context.scene.objects:
        if 'isAlphaMesh' in object:
            if not object.AlphaMesh_active:
                # bm = bmesh.new()
                # bm.to_mesh(object.data)
                continue
            if not object.get('qhull_options'):
                object['qhull_options'] = DEFAULT_QHULL_OPTIONS
            obj_alphamesh = object
            # obj_alphamesh = obj_alphamesh.evaluated_get(depsgraph)
            AlphaMesh_info = {
                'obj_alphamesh': obj_alphamesh,
                'Emitter_infos': [],
            }
            for item in object.AlphaMeshEmitters:
                if item.active == True:
                    if item.obj != '':
                        if item.psys != '':
                            EmitterInfo = {
                                'object_name': item.obj,
                                'particlesystem_name': item.psys,
                            }
                            AlphaMesh_info['Emitter_infos'].append(EmitterInfo)
            AlphaMesh_infos.append(AlphaMesh_info)

    print("%d active AlphaMesh instance(s) found" % len(AlphaMesh_infos))

    for AlphaMesh_info in AlphaMesh_infos:
        # degp = bpy.context.evaluated_depsgraph_get()
        # depsgraph.update()

        obj_alphamesh = AlphaMesh_info['obj_alphamesh']
        Emitter_infos = AlphaMesh_info['Emitter_infos']

        print("  ----AlphaMesh Object:", obj_alphamesh.name, "----")

        np_verts=[]
        for Emitter_info in Emitter_infos:
            obj_name = Emitter_info['object_name']
            particlesystem_name = Emitter_info['particlesystem_name']
            obj = depsgraph.objects.get(obj_name, None)
            obj = obj.evaluated_get(depsgraph)
            psys = obj.particle_systems[particlesystem_name]
            # psys = depsgraph.objects.get(obj_name, None).particle_systems[particlesystem_name]
            particles = psys.particles
            psysize = len(particles)

            np_verts = np_verts + [np.array(particle.location) for index, particle in particles.items() if particle.alive_state == 'ALIVE']

        mesh = obj_alphamesh.data
        bm = bmesh.new()
        if len(np_verts) > 3:
            np_verts = np_verts + np.random.uniform(low=-1e-11, high=1e-11, size=(len(np_verts),3,))    # jitter

            print('  pack %d particles:' % len(np_verts), timer.lap(), 'sec')
            vertices, edges, triangles = alpha_shape_3D(
            # vertices, edges, triangles = alpha_shape_3d_alternative(
                np_verts,
                alpha=obj_alphamesh.AlphaMesh_res,
                options=obj_alphamesh['qhull_options'],
                only_outer = obj_alphamesh.AlphaMesh_outeronly,
            )

            print('  alpha shape:', timer.lap(), 'sec')
            print('      %s particles, %s vertices, %s edges, %s triangles' % (len(np_verts), len(vertices), len(edges), len(triangles)))

            lookup={}
            for i, v in enumerate(vertices):
                lookup[v] = i
                bm.verts.new(np_verts[v])  # add a new vert

            print('  vertices added:', timer.lap(), 'sec')

            bm.verts.ensure_lookup_table()

            for t in triangles:
                a,b,c = t
                bm.faces.new([bm.verts[lookup[a]], bm.verts[lookup[b]], bm.verts[lookup[c]]])
            print('  triangles added:', timer.lap(), 'sec')

            for f in bm.faces:
                 f.smooth = obj_alphamesh.AlphaMesh_smooth

            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            mesh.update(calc_edges=True)
            print('  normals:', timer.lap(), 'sec')

        bm.to_mesh(mesh)
        bm.clear()
        mesh.update()
        bm.free()  # always do this when finished
        print('  Bmesh:', timer.lap(), 'sec')

    bpy.context.view_layer.objects.active = active_before
    current_frame = scn.frame_current
    if IS_RENDERING:
        time.sleep(1)
    print('Total:', timer.stop(), 'sec')


class OBJECT_UL_AlphaMeshEmitters(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        split = layout.split(factor=0.1)
        split.prop(item, "active", text="")
        split.prop(item, "name", text="", emboss=False, translate=False, icon='OUTLINER_OB_META')


class UIListPanel_AlphaMesh(Panel):
    """Creates a Panel in the Object properties window"""
    bl_label = "AlphaMesh addon"
    bl_idname = "OBJECT_PT_ui_list_example"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "object"
    # bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        obj = context.object        
        if 'isAlphaMesh' in obj:
            layout = self.layout
            box = layout.box()
            row = box.row()
            row.template_list("OBJECT_UL_AlphaMeshEmitters", "", obj, "AlphaMeshEmitters", obj, "AlphaMeshEmitters_index")
            col = row.column(align=True)
            col.operator("op.alphameshemitters_item_add", icon="ADD", text="").add = True
            col.operator("op.alphameshemitters_item_add", icon="REMOVE", text="").add = False
            if obj.AlphaMeshEmitters and obj.AlphaMeshEmitters_index < len(obj.AlphaMeshEmitters):
                row = box.row()
                row.label(text='Object: ')
                row.prop_search(obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index], "obj", context.scene, "objects", text="")
                if obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index].obj != '':
                    if bpy.data.objects[obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index].obj].type != 'MESH':
                        obj.AlphaMeshEmitter[obj.AlhaMeshEmitters_index].obj = ''
                    else:
                        row = box.row()
                        row.label(text='Particles: ')
                        row.prop_search(obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index], "psys",
                                        bpy.data.objects[obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index].obj], "particle_systems",
                                        text="")
                        if obj.AlphaMeshEmitters[obj.AlphaMeshEmitters_index].psys != '':
                            row = box.row()
            box = layout.box()
            row = box.row()
            row.prop(obj, "AlphaMesh_res", text="alpha:")
            row = box.row()
            row.prop(obj, "AlphaMesh_outeronly", text="only outer")
            row = box.row()
            row.prop(obj, "AlphaMesh_smooth", text="smooth")
            row = box.row()
            row.prop(obj, "AlphaMesh_active", text="active")
            box = layout.box()
            row = box.row()
            row.operator("object.simple_operator_updatealphamesh", text="Update AlphaShape", icon="MESH_DATA")
            row = box.row()
            row.operator("object.simple_operator_renderall", text="Render Animation (workaround)", icon='RENDER_ANIMATION')
            box = box.box()
            box.active = False
            box.alert = False
            row = box.row()
            row.alignment = 'CENTER'
            row.label(text="AlphaMesh addon by Gogo.")
        else:
            layout = self.layout
            box = layout.box()
            row = box.row()
            row.label(text='Please select an AlphaMesh object!', icon='ERROR')


class OBJECT_OT_alphameshemitters_item_add(bpy.types.Operator):
    bl_label = "Add/Remove items from AlphaMeshEmitter object"
    bl_idname = "op.alphameshemitters_item_add"
    add = bpy.props.BoolProperty(default=True)

    def invoke(self, context, event):
        add = self.add
        ob = context.object
        if ob != None:
            item = ob.AlphaMeshEmitters
            if add:
                item.add()
                l = len(item)
                item[-1].name = ("AlphaMeshEmitter." + str(l))
                item[-1].active = True
                item[-1].res = 0.25
                item[-1].id = l
            else:
                index = ob.AlphaMesh_index
                item.remove(index)
        return {'FINISHED'}


class AlphaMeshEmitter(bpy.types.PropertyGroup):
    # name = StringProperty()
    active = BoolProperty()
    id = IntProperty()
    obj = StringProperty()
    psys = StringProperty()


def render_one_by_one():
    global current_frame

    current_frame = -2
    scene = bpy.context.scene
    fp = scene.render.filepath
    fe = scene.render.file_extension
    try:
        for frame in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(frame)
            filename = fp + ('image_%04d' % frame)
            scene.render.filepath = filename    
            if not os.path.isfile(filename + fe):
                bpy.ops.render.render(write_still=True)
                time.sleep(3)
    except KeyboardInterrupt:
        print("Interrupted rendering.")
    scene.render.filepath = fp


class SimpleOperator_RenderAll(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator_renderall"
    bl_label = "Render frames one by one"

    # @classmethod
    # def poll(cls, context):
    #     return context.active_object is not None

    def execute(self, context):
        self.report({'INFO'}, "Animation rendering started.")
        render_one_by_one()
        self.report({'INFO'}, "Animation rendering finished!")
        return {'FINISHED'}


class SimpleOperator_UpdateAlphaMesh(bpy.types.Operator):
    """Tooltip"""
    bl_idname = "object.simple_operator_updatealphamesh"
    bl_label = "Update AlphaMesh"

    @classmethod
    def poll(cls, context):
        return context.active_object.get('isAlphaMesh')

    def execute(self, context):
        global current_frame
        self.report({'INFO'}, "Update AlphaMesh started.")
        current_frame = -2
        alphamesh(context, depsgraph=None)
        self.report({'INFO'}, "Update AlphaMesh finished!")
        return {'FINISHED'}


classes_list = [
    OBJECT_OT_add_alphamesh,
    OBJECT_UL_AlphaMeshEmitters,
    UIListPanel_AlphaMesh,
    OBJECT_OT_alphameshemitters_item_add,
    AlphaMeshEmitter,
    SimpleOperator_RenderAll,
    SimpleOperator_UpdateAlphaMesh,
]


def register():
    for item in classes_list:
        bpy.utils.register_class(item)
    bpy.types.VIEW3D_MT_mesh_add.append(add_alphamesh_button)
    bpy.types.Object.AlphaMeshEmitters = CollectionProperty(type=AlphaMeshEmitter)
    bpy.types.Object.AlphaMeshEmitters_index = IntProperty()
    bpy.types.Object.AlphaMesh_res = FloatProperty(precision=4)
    bpy.types.Object.AlphaMesh_outeronly = BoolProperty()
    bpy.types.Object.AlphaMesh_smooth = BoolProperty()
    bpy.types.Object.AlphaMesh_active = BoolProperty()
    bpy.types.Scene.AlphaMesh_context = StringProperty(default="WINDOW")


def unregister():
    bpy.utils.unregister_class(SimpleOperator_RenderAll)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_alphamesh_button)
    for item in classes_list:
        bpy.utils.unregister_class(item)
    del bpy.types.Object['isAlphaMesh']


if alphamesh not in bpy.app.handlers.frame_change_post:
    print('Registering AlphaMesh addon handlers...')
    bpy.app.handlers.persistent(alphamesh_frame)
    bpy.app.handlers.frame_change_post.append(alphamesh_frame)
    bpy.app.handlers.persistent(alphamesh_prerender)
    # bpy.app.handlers.render_init.append(alphamesh_prerender)
    bpy.app.handlers.render_pre.append(alphamesh_prerender)
    bpy.app.handlers.persistent(alphamesh_postrender)
    bpy.app.handlers.render_post.append(alphamesh_postrender)
    bpy.app.handlers.render_cancel.append(alphamesh_postrender)
    bpy.app.handlers.render_complete.append(alphamesh_postrender)
    print('AlphaMesh addon handlers created successfully.')


if __name__ == '__main__':
    register()
