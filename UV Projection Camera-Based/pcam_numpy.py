
from pxr import Usd, UsdGeom, Gf, Sdf, Vt
import hou
import math
import numpy as np
import logging

logger = logging.getLogger(__name__)

def pinhole_uv_projection_np(camera_inv_matrix, points_np, focal_mm, filmback_mm_x, filmback_mm_y):
    # Transform world points to camera space
    transformed = np.c_[points_np, np.ones(len(points_np))] @ np.array(camera_inv_matrix)
    x_cam, y_cam, z_cam = transformed[:, 0], transformed[:, 1], -transformed[:, 2]

    # Avoid division by near-zero depth
    near_zero = np.abs(z_cam) < 1e-12
    z_cam[near_zero] = 1.0  # avoid divide-by-zero; we'll clamp UV to center later

    tan_half_fov_x = math.tan(math.atan2(filmback_mm_x * 0.5, focal_mm))
    tan_half_fov_y = math.tan(math.atan2(filmback_mm_y * 0.5, focal_mm))

    u = 0.5 + 0.5 * (x_cam / z_cam / tan_half_fov_x)
    v = 0.5 + 0.5 * (y_cam / z_cam / tan_half_fov_y)

    u[near_zero] = 0.5
    v[near_zero] = 0.5

    return np.stack([u, v], axis=1)


def calculate_facing_ratio_vertex_np(camera_pos, normals_np, points_np):
    view_dirs = camera_pos - points_np
    norms = np.linalg.norm(view_dirs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    view_dirs = view_dirs / norms
    dots = np.sum(normals_np * view_dirs, axis=1)
    return np.clip(dots, 0.0, 1.0)


def calculate_facing_ratio_faceVarying_np(camera_pos, normals_np, face_vertex_indices, points_np):
    view_dirs = camera_pos - points_np[face_vertex_indices]
    norms = np.linalg.norm(view_dirs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    view_dirs = view_dirs / norms
    dots = np.sum(normals_np * view_dirs, axis=1)
    dots = np.clip(dots, 0.0, 1.0)

    accum = np.zeros((len(points_np),), dtype=np.float32)
    count = np.zeros((len(points_np),), dtype=np.int32)

    np.add.at(accum, face_vertex_indices, dots)
    np.add.at(count, face_vertex_indices, 1)
    count[count == 0] = 1  # Avoid divide-by-zero
    return accum / count


def main():
    node = hou.pwd()
    stage = node.editableStage()

    # Retrieve node parameters
    primpattern   = node.parm('primpat').eval()
    sourceframe   = int(node.parm('src_frame').eval())
    primvarname   = node.parm('attr_name').eval()
    camera_path   = node.parm('camera').eval()

    logger.info("=== Debug: Parameter Retrieval ===")
    logger.info(f"Prim Pattern: {primpattern}")
    logger.info(f"Source Frame: {sourceframe}")
    logger.info(f"Primvar Name: {primvarname}")
    logger.info(f"Camera Path : {camera_path}")

    # Validate camera
    camera_prim = stage.GetPrimAtPath(camera_path)
    if not camera_prim or not camera_prim.IsA(UsdGeom.Camera):
        raise ValueError(f"Invalid camera: {camera_path}")

    usd_camera       = UsdGeom.Camera(camera_prim)
    focal_length     = usd_camera.GetFocalLengthAttr().Get()
    h_aperture       = usd_camera.GetHorizontalApertureAttr().Get()
    v_aperture       = usd_camera.GetVerticalApertureAttr().Get()

    SCALE_TO_MM = 100.0
    focal_mm    = focal_length * SCALE_TO_MM
    haperture_mm= h_aperture  * SCALE_TO_MM
    vaperture_mm= v_aperture  * SCALE_TO_MM

    logger.info("=== Camera Debug ===")
    logger.info(f"Focal Length (mm)         : {focal_mm}")
    logger.info(f"Horizontal Aperture (mm)  : {haperture_mm}")
    logger.info(f"Vertical Aperture (mm)    : {vaperture_mm}")

    # Compute camera world transform
    timecode = Usd.TimeCode(sourceframe)
    camera_world_xf = UsdGeom.Xformable(usd_camera).ComputeLocalToWorldTransform(timecode)
    cam_no_scale = Gf.Matrix4d(camera_world_xf)
    camera_inv = cam_no_scale.GetInverse()

    camera_position = np.array([camera_world_xf[3][0], camera_world_xf[3][1], camera_world_xf[3][2]])
    
    # Select matching mesh prims
    lop_sel = hou.LopSelectionRule()
    lop_sel.setPathPattern(primpattern + " & %type:Mesh")
    matching_paths = lop_sel.expandedPaths(stage=stage)

    logger.info("=== Matching Meshes ===")
    for mp in matching_paths:
        logger.info(f"  {mp}")

    for primpath in matching_paths:
        prim = stage.GetPrimAtPath(primpath)
        if not prim or not prim.IsValid():
            logger.info(f"Skipping invalid prim: {primpath}")
            continue

        points_attr = prim.GetAttribute("points")
        normals_attr = prim.GetAttribute("normals")

        if not points_attr or not normals_attr:
            logger.info(f"Missing points or normals on {primpath}, skipping.")
            continue

        points_data = points_attr.Get(timecode)
        normals_data = normals_attr.Get(timecode)

        if not points_data or not normals_data:
            logger.info(f"Missing data on {primpath}, skipping.")
            continue

        obj_xform = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(timecode)

        points_np = np.array(points_data, dtype=np.float64)
        points_world_np = (np.c_[points_np, np.ones(len(points_np))] @ np.array(obj_xform))[:, :3]

        normal_interp = normals_attr.GetMetadata("interpolation")
        if not normal_interp:
            logger.info(f"Could not determine normal interpolation on {primpath}, defaulting to 'vertex'")
            normal_interp = "vertex"

        if normal_interp == UsdGeom.Tokens.vertex:
            logger.info("vertex (point in Houdini) detected")
            normals_np = np.array(normals_data, dtype=np.float32)
            facing_ratios = calculate_facing_ratio_vertex_np(camera_position, normals_np, points_world_np)
        else:
            logger.info("faceVarying (vertex in Houdini) detected")
            mesh = UsdGeom.Mesh(prim)
            face_vertex_indices = mesh.GetFaceVertexIndicesAttr().Get(timecode)
            face_vertex_indices = np.array(face_vertex_indices, dtype=np.int32)
            normals_np = np.array(normals_data, dtype=np.float32)
            facing_ratios = calculate_facing_ratio_faceVarying_np(camera_position, normals_np, face_vertex_indices, points_world_np)

        uv_out = pinhole_uv_projection_np(camera_inv, points_world_np, focal_mm, haperture_mm, vaperture_mm)
        combined = np.hstack([uv_out, facing_ratios[:, None]])

        vt_array = Vt.Vec3fArray.FromNumpy(combined.astype(np.float32))

        primvars_api = UsdGeom.PrimvarsAPI(prim)
        primvar = primvars_api.CreatePrimvar(
            primvarname,
            Sdf.ValueTypeNames.Float3Array,
            UsdGeom.Tokens.vertex
        )
        primvar.Set(vt_array)

        logger.info(f"Created primvar '{primvarname}' on {primpath} with {len(vt_array)} items.")
