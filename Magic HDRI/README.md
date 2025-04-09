# Magic HDRI
The "magic" HDRI is a technique designed to improve render times for interior scenes. The trick involves pre-rendering a 360° HDRI and then reprojecting it onto objects outside the camera view. This simplifies global illumination and reflections, reducing overall rendering complexity.

In the included HIP file, there’s a Karma Shader that uses coordsys to project the HDRI onto scene geometry. A camera frustum is also provided to prevent the "magic" HDRI from appearing in the camera view.

Performance
This optimization can vary depending on the scene, but render times can improve significantly—typically between 1.5x to 5x faster.

Limitations
The result may not perfectly match the original render but is usually very close.

Compositing control is limited, as only one AOV is available for the entire HDRI.

# Overview

# How to use it
An example scene can be found in `template/magicHdri.hip`.