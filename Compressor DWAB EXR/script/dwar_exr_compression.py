import hou
import pxr.Usd as Usd

# Get the input node and its stage
lopNode = hou.pwd().inputs()[0]
stage = lopNode.stage()

# List to store matching primitive paths
matching_prims = []

# Loop through all primitives in the stage
for prim in stage.Traverse():
    # Check if the path starts with the specified prefix
    if prim.GetPath().pathString.startswith("/Render/Products/Vars/"):
        # Check if the primitive has an attribute named 'driver:parameters:aov:format'
        data_type_attr = prim.GetAttribute("driver:parameters:aov:format")
        if data_type_attr:
            # Check if the attribute's value is 'color4h' or 'color3h'
            value = data_type_attr.Get()
            if value in ["color4h", "color3h"]:
                matching_prims.append(prim.GetPath().pathString)

# Convert the list to a single space-separated string
result = " ".join(matching_prims)
return result