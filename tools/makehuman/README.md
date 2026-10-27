# The people's bodies (MakeHuman on the Quaternius skeleton)

`web/people/mh_body_m.gltf` and `mh_body_f.gltf` are MakeHuman 1.3 bodies (CC0 assets): a young African man and
woman, each with eyes, brows and lashes. They are fitted onto the skeleton and bind pose of the Quaternius Universal
Base Characters (CC0), in `quaternius/`. Because the joints and inverse bind matrices are unchanged, every clip in
`anims.glb` and every hair, wear and accessory model still fits.

To rebuild them:

1. In a venv with `numpy PyQt5 PyOpenGL`, with the MakeHuman 1.3.0 source and its CC0 asset packs unpacked into
   `makehuman/data`, run `python mh_dump.py <makehuman dir> <out dir> '<spec json>'`. The spec used:

   ```
   {"m":{"mods":{"Gender":1.0,"African":1.0,"Age":0.5,"Muscle":0.65,"Weight":0.5,"Height":0.6},"parts":{"body":["proxymeshes/male_generic/male_generic.proxy","Proxymeshes"],"eyes":["eyes/low-poly/low-poly.mhclo","Eyes"],"brows":["eyebrows/eyebrow001/eyebrow001.mhclo","Eyebrows"],"lashes":["eyelashes/eyelashes01/eyelashes01.mhclo","Eyelashes"]}},"f":{"mods":{"Gender":0.0,"African":1.0,"Age":0.5,"Muscle":0.5,"Weight":0.5,"Height":0.5},"parts":{"body":["proxymeshes/female_generic/female_generic.proxy","Proxymeshes"],"eyes":["eyes/low-poly/low-poly.mhclo","Eyes"],"brows":["eyebrows/eyebrow010/eyebrow010.mhclo","Eyebrows"],"lashes":["eyelashes/eyelashes02/eyelashes02.mhclo","Eyelashes"]}}}
   ```

   This writes `mh_m.npz` and `mh_f.npz`: the proxy meshes, UVs, MakeHuman weights and joints.
2. Run `python fit.py quaternius/body_m.gltf mh_m.npz <out> m <makehuman>/data/skins/young_african_male/young_darkskinned_male_diffuse.png`,
   and the same for `f`. This needs numpy and Pillow.
   - Each MakeHuman bone segment is moved onto its Quaternius bone: a swing to the bone's direction, a stretch to its
     length, and a 1:1 scale across.
   - The head is fitted box to box, so the hair still sits right.
   - The weights are MakeHuman's own, summed onto the matching Quaternius joints.
   - Plain dark underwear is painted into the skin texture.
