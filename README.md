# Combine VTU velocity files

Combines the point-data array named `Velocity` from every `.vtu` file in a
directory into one unstructured-grid VTU file. The output arrays are named
`Velocity_1`, `Velocity_2`, and so on, in filename-sorted order.

## Sherlock setup

Use a Python 3 module and create the environment once:

```bash
module purge
module load python/3.12.1
python3 -m venv $HOME/venvs/combine-vtu
source $HOME/venvs/combine-vtu/bin/activate
python -m pip install --upgrade pip
python -m pip install -r $HOME/combine-vtu-sherlock/requirements.txt
```

The script imports only VTK's non-rendering modules, so it does not require
`libGL.so.1` on a headless login node.

## Run

```bash
source $HOME/venvs/combine-vtu/bin/activate
cd $SCRATCH/P01/96-procs
python $HOME/combine-vtu-sherlock/combine-vtu.py . \
    --output results-combined.vtu
```

All input files must contain a point-data array named exactly `Velocity` and
must have the same mesh geometry and point ordering.
