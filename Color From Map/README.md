# 🎨 Houdini LOP VEX Snippet – Color From Map

This is a small VEX snippet for a **Wrangle LOP** in Houdini Solaris.  
It samples a texture using UVs and writes the result to the `displayColor` primvar for easy viewport previews.

---

## 🔧 Code

```c
vector color = colormap(chs("location"), u@primvars:st);
v@primvars:displayColor = color;
usd_setprimvarinterpolation(0, @primpath, "displayColor", "faceVarying");
