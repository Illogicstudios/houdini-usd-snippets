# Zebra Checker
A tool that facilitates the visualization of overexposure.

As part of our use of Karma, we have identified that correct exposure of the scene to lighting is crucial for optimizing rendering times. The engine uses an oracle based on a variance threshold to stop the calculation of a pixel once a certain acceptable noise level is reached.<br>

Overexposed images require a longer calculation time, because the noise threshold takes longer to reach when the illumination values are very high. Conversely, a scene that is too dark will quickly reach this threshold, but will produce a more noisy rendering once re-exposed in compositing. It is therefore essential to adjust the exposure correctly at the lighting stage to optimize both rendering time and image quality.<br>

We also found that artists tend to overexpose their scenes, largely due to the marked roll-off of highlights introduced by ACES, which can distort the perception of actual exposure.
To accompany them, we have integrated a zebra checker inspired by the tools used in real photography. We plan to enrich this feature by adding a False Color view, as well as access to a library of physically correct illumination values, in order to strengthen artistic decision-making while respecting the physical constraints of rendering.

# Overview
<img src="https://github.com/user-attachments/assets/069e09c8-28cf-478d-a955-6f018e5f7028" width="448" height="252"><br>
<img src="https://github.com/user-attachments/assets/4b1af54f-0e97-4a5d-aa77-c4cb9a95f239" width="252" height="252">

# How to use it
This tool can be found as recipe in `template/zebra.hip`.
