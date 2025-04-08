int samples   = chi("samples");
float radius  = chf("radius");

// Open a point cloud handle
int handle = pcopen(0, "P", @P, radius, samples);

float accum    = 0.0;
int   count    = 0;
while (pciterate(handle))
{
    vector posHit;
    pcimport(handle, "P", posHit);

    // Distance-based weight (simple linear falloff)
    float dist = distance(@P, posHit);
    float w = 1.0 - clamp(dist / radius, 0.0, 1.0);

    accum += w;
    count++;
}

// If you want a normalized accumulation by max possible weight
// or by the number of points found, you could do:
f@photonAccum = accum / float(samples);

