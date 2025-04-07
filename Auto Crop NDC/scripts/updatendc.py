from pxr import Usd, UsdGeom, Gf, Sdf
import hou


def get_NDC_bounds_and_update_primvar(
    stage: Usd.Stage,
    object_prim_paths: list[str],
    camera_prim_path: str,
    padding: float = 0.0
) -> tuple[float, float, float, float] | None:
    """
    Computes the combined bounding box of multiple prims in normalized device coordinates (0..1)
    at the current Houdini frame, with an optional 'padding' in NDC space.
    
    Updates a float4 attribute 'dataWindowNDC' on /Render/rendersettings.
    """

    current_frame = hou.frame()

    # Validate camera
    camera_prim = stage.GetPrimAtPath(camera_prim_path)
    if not camera_prim:
        print("No valid camera for NDC.")
        return None

    # Fetch render settings prim
    render_settings_prim = stage.GetPrimAtPath("/Render/rendersettings")
    if not render_settings_prim.IsValid():
        hou.ui.displayMessage(
            "Could not find /Render/rendersettings on the stage.",
            severity=hou.severityType.Error
        )
        return None

    # Get render resolution
    resolution_attr = render_settings_prim.GetAttribute("resolution")
    if not resolution_attr or not resolution_attr.HasValue():
        hou.ui.displayMessage(
            "No valid 'resolution' attribute found on /Render/rendersettings.",
            severity=hou.severityType.Error
        )
        return None

    resolution = resolution_attr.Get()
    if not resolution or len(resolution) < 2:
        hou.ui.displayMessage(
            "'resolution' attribute is not a valid 2D resolution.",
            severity=hou.severityType.Error
        )
        return None

    res_x, res_y = resolution
    if res_y == 0:
        hou.ui.displayMessage(
            "Render resolution has a zero height (res_y=0).",
            severity=hou.severityType.Error
        )
        return None

    render_aspect = float(res_x) / float(res_y)

    # Aspect ratio conform policy
    policy_attr = render_settings_prim.GetAttribute("aspectRatioConformPolicy")
    policy_val = policy_attr.Get() if policy_attr and policy_attr.HasValue() else "expandAperture"

    # Prepare camera info
    cam = UsdGeom.Camera(camera_prim)
    focal_length = cam.GetFocalLengthAttr().Get()
    aperture_x = cam.GetHorizontalApertureAttr().Get()
    aperture_y = cam.GetVerticalApertureAttr().Get()

    if focal_length is None or aperture_x is None or aperture_y is None:
        hou.ui.displayMessage(
            "Camera is missing focal/aperture attributes.",
            severity=hou.severityType.Error
        )
        return None

    camera_transform = UsdGeom.Xformable(camera_prim).ComputeLocalToWorldTransform(
        Usd.TimeCode(current_frame)
    )
    camera_transform_inv = camera_transform.GetInverse()

    # Determine camera aperture
    camera_aspect = float(aperture_x) / float(aperture_y)

    if policy_val == "expandAperture":
        if camera_aspect < render_aspect:
            effective_aperture_x = aperture_y * render_aspect
            effective_aperture_y = aperture_y
        else:
            effective_aperture_x = aperture_x
            effective_aperture_y = aperture_x / render_aspect
    else:
        if camera_aspect < render_aspect:
            effective_aperture_x = aperture_x
            effective_aperture_y = aperture_x / render_aspect
        else:
            effective_aperture_x = aperture_y * render_aspect
            effective_aperture_y = aperture_y

    ndc_x_vals = []
    ndc_y_vals = []

    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode(current_frame),
        [UsdGeom.Tokens.default_]
    )

    # Compute bounding boxes for all primitives
    for object_prim_path in object_prim_paths:
        object_prim = stage.GetPrimAtPath(object_prim_path)
        if not object_prim:
            print(f"Invalid prim: {object_prim_path}")
            continue

        obj_bbox = bbox_cache.ComputeWorldBound(object_prim)
        bbox_range = obj_bbox.ComputeAlignedRange()
        min_bound = bbox_range.GetMin()
        max_bound = bbox_range.GetMax()

        corners = [
            Gf.Vec3d(min_bound[0], min_bound[1], min_bound[2]),
            Gf.Vec3d(max_bound[0], min_bound[1], min_bound[2]),
            Gf.Vec3d(min_bound[0], max_bound[1], min_bound[2]),
            Gf.Vec3d(max_bound[0], max_bound[1], min_bound[2]),
            Gf.Vec3d(min_bound[0], min_bound[1], max_bound[2]),
            Gf.Vec3d(max_bound[0], min_bound[1], max_bound[2]),
            Gf.Vec3d(min_bound[0], max_bound[1], max_bound[2]),
            Gf.Vec3d(max_bound[0], max_bound[1], max_bound[2]),
        ]

        for corner in corners:
            camera_space_point = camera_transform_inv.Transform(corner)
            if camera_space_point[2] >= 0:
                continue

            ndc_x = (camera_space_point[0] * focal_length) / (
                abs(camera_space_point[2]) * (effective_aperture_x * 0.5)
            )
            ndc_y = (camera_space_point[1] * focal_length) / (
                abs(camera_space_point[2]) * (effective_aperture_y * 0.5)
            )

            ndc_x = ndc_x * 0.5 + 0.5
            ndc_y = ndc_y * 0.5 + 0.5

            ndc_x_vals.append(ndc_x)
            ndc_y_vals.append(ndc_y)

    if not ndc_x_vals or not ndc_y_vals:
        print("Objects are not visible in camera frustum at frame", current_frame)
        return None

    min_x = max(0.0, min(ndc_x_vals) - padding)
    min_y = max(0.0, min(ndc_y_vals) - padding)
    max_x = min(1.0, max(ndc_x_vals) + padding)
    max_y = min(1.0, max(ndc_y_vals) + padding)

    # Update dataWindowNDC attribute
    data_window_attr = render_settings_prim.GetAttribute("dataWindowNDC")
    if not data_window_attr.IsValid():
        data_window_attr = render_settings_prim.CreateAttribute(
            "dataWindowNDC",
            Sdf.ValueTypeNames.Float4,
            custom=True
        )

    timecode = Usd.TimeCode(current_frame)  # Use Houdini's current frame
    data_window_attr.Set(Gf.Vec4f(min_x, min_y, max_x, max_y), timecode)

    print(f"Frame {current_frame}: dataWindowNDC = ({min_x}, {min_y}, {max_x}, {max_y})")
    return (min_x, min_y, max_x, max_y)


# Example usage:
stage = hou.pwd().editableStage()
camera = hou.pwd().parent().parm("camera").eval()
prims_str = hou.pwd().parent().parm("primitives").eval()

# Split the primitives string into a list
primitives = prims_str.split()

try:
    get_NDC_bounds_and_update_primvar(
        stage=stage,
        object_prim_paths=primitives,
        camera_prim_path=camera,
        padding=0.03
    )
except Exception as e:
    print(f"Failed to calculate NDC bounds: {e}")
