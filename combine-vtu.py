#!/usr/bin/env python3

# This script combines 'Velocity' data arrays from multiple VTU files into a
# single VTU file.
#
# Usage:
#
#   combine-vtu.py PATH
#
#   PATH: Path to the VTU files.
#
# Output:
#
#   results-combined.vtu in current directory

import argparse
import sys
from pathlib import Path

# Import only the non-rendering VTK modules.  This keeps the script usable on
# headless systems such as Sherlock, where libGL.so.1 may not be available.
from vtkmodules.vtkCommonDataModel import vtkUnstructuredGrid
from vtkmodules.vtkIOXML import (
    vtkXMLUnstructuredGridReader,
    vtkXMLUnstructuredGridWriter,
)


def remove_arrays(mesh):
    """Remove all data arrays from the mesh."""
    array_names_to_keep = ["GlobalNodeID", "GlobalElementID"]

    point_data = mesh.GetPointData()
    if point_data:
        for i in range(point_data.GetNumberOfArrays() - 1, -1, -1):
            name = point_data.GetArrayName(i)
            if name and name not in array_names_to_keep:
                point_data.RemoveArray(name)

    cell_data = mesh.GetCellData()
    if cell_data:
        for i in range(cell_data.GetNumberOfArrays() - 1, -1, -1):
            name = cell_data.GetArrayName(i)
            if name and name not in array_names_to_keep:
                cell_data.RemoveArray(name)

    field_data = mesh.GetFieldData()
    if field_data:
        for i in range(field_data.GetNumberOfArrays() - 1, -1, -1):
            name = field_data.GetArrayName(i)
            field_data.RemoveArray(name)

    mesh.Modified()


def read_mesh(file_name):
    """Read a mesh from a VTU file."""
    reader = vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(file_name))
    reader.Update()

    if reader.GetErrorCode() != 0:
        raise RuntimeError(f"VTU reader failed for {file_name}")

    mesh = reader.GetOutput()
    if mesh is None or mesh.GetNumberOfPoints() == 0:
        raise RuntimeError(f"VTU file contains no points: {file_name}")
    return mesh


def add_data(new_mesh, step_num, file_name):
    """Add velocity data from a mesh to the new mesh."""
    mesh = read_mesh(file_name)
    velocity = mesh.GetPointData().GetArray("Velocity")
    if velocity is None:
        raise ValueError(f"Mesh {file_name} does not contain data named 'Velocity'.")
    if velocity.GetNumberOfTuples() != new_mesh.GetNumberOfPoints():
        raise ValueError(
            f"Velocity array in {file_name} has {velocity.GetNumberOfTuples()} "
            f"tuples, expected {new_mesh.GetNumberOfPoints()}"
        )

    # Deep-copy the array because it belongs to the reader's output object.
    velocity_copy = velocity.NewInstance()
    velocity_copy.DeepCopy(velocity)
    velocity_copy.SetName(f"Velocity_{step_num}")
    new_mesh.GetPointData().AddArray(velocity_copy)
    new_mesh.Modified()


def create_new_mesh(mesh):
    """Create a new mesh from 'mesh' with all data removed."""
    new_mesh = vtkUnstructuredGrid()
    new_mesh.DeepCopy(mesh)

    remove_arrays(new_mesh)

    return new_mesh


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine point-data Velocity arrays from VTU files into one VTU."
    )
    parser.add_argument("path", type=Path, help="Directory containing input VTU files")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("results-combined.vtu"),
        help="Output VTU path (default: results-combined.vtu)",
    )
    args = parser.parse_args()

    directory = args.path
    if not directory.is_dir():
        print(f"Input directory does not exist: {directory}", file=sys.stderr)
        sys.exit(1)

    sorted_files = sorted(directory.glob("*.vtu"), key=lambda p: p.name)
    if not sorted_files:
        print(f"No VTU files found in {directory}")
        sys.exit(1)

    first_file = sorted_files[0]
    try:
        first_file = sorted_files[0]
        mesh = read_mesh(first_file)
        print(f"Using mesh geometry from: {first_file}")
        new_mesh = create_new_mesh(mesh)

        for step_num, file_path in enumerate(sorted_files, start=1):
            print(f"Reading file: {file_path}")
            add_data(new_mesh, step_num, file_path)

        writer = vtkXMLUnstructuredGridWriter()
        writer.SetInputData(new_mesh)
        writer.SetFileName(str(args.output))
        if writer.Write() == 0:
            raise RuntimeError(f"Could not write output file: {args.output}")
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    print(f"Converted file is {args.output}")
