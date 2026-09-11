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
import tempfile
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


def write_ascii_array(stream, velocity, name):
    """Write one velocity array as an ASCII VTK XML DataArray."""
    components = velocity.GetNumberOfComponents()
    stream.write(
        f'    <DataArray type="Float64" Name="{name}" '
        f'NumberOfComponents="{components}" format="ascii">\n'
    )
    values = []
    for index in range(velocity.GetNumberOfTuples()):
        values.extend(str(value) for value in velocity.GetTuple(index))
        if len(values) >= 4096:
            stream.write("      " + " ".join(values) + "\n")
            values.clear()
    if values:
        stream.write("      " + " ".join(values) + "\n")
    stream.write("    </DataArray>\n")


def combine_streaming(sorted_files, output):
    """Combine files while retaining only one velocity array in memory.

    The streaming output uses ASCII XML, which is slower and usually larger
    than VTK's binary output, but avoids retaining all timesteps in RAM.
    """
    with tempfile.TemporaryDirectory(prefix="combine-vtu-") as temp_dir:
        geometry_path = Path(temp_dir) / "geometry.vtu"
        geometry_mesh = create_new_mesh(read_mesh(sorted_files[0]))
        writer = vtkXMLUnstructuredGridWriter()
        writer.SetInputData(geometry_mesh)
        writer.SetFileName(str(geometry_path))
        writer.SetDataModeToAscii()
        if writer.Write() == 0:
            raise RuntimeError(f"Could not write temporary geometry: {geometry_path}")

        with geometry_path.open("r", encoding="utf-8") as source, output.open(
            "w", encoding="utf-8"
        ) as destination:
            point_data_open = False
            for line in source:
                if "<PointData" not in line:
                    destination.write(line)
                    continue

                destination.write(line.replace("/>", ">"))
                if "/>" not in line:
                    # The geometry-only writer normally emits an empty pair
                    # of PointData tags. Consume that empty section.
                    for inner_line in source:
                        if "</PointData>" in inner_line:
                            break

                if "/>" in line:
                    point_data_open = True
                else:
                    point_data_open = True
                for step_num, file_path in enumerate(sorted_files, start=1):
                    print(f"Reading file: {file_path}")
                    mesh = read_mesh(file_path)
                    velocity = mesh.GetPointData().GetArray("Velocity")
                    if velocity is None:
                        raise ValueError(
                            f"Mesh {file_path} does not contain data named 'Velocity'."
                        )
                    if velocity.GetNumberOfTuples() != geometry_mesh.GetNumberOfPoints():
                        raise ValueError(
                            f"Velocity array in {file_path} has "
                            f"{velocity.GetNumberOfTuples()} tuples, expected "
                            f"{geometry_mesh.GetNumberOfPoints()}"
                        )
                    write_ascii_array(destination, velocity, f"Velocity_{step_num}")
                destination.write("    </PointData>\n")
            if not point_data_open:
                raise RuntimeError("Could not locate PointData section in temporary VTU")


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
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Use low-memory streaming mode (ASCII output; slower/larger file)",
    )
    args = parser.parse_args()

    directory = args.path
    if not directory.is_dir():
        print(f"Input directory does not exist: {directory}", file=sys.stderr)
        sys.exit(1)

    output_path = args.output.resolve()
    sorted_files = sorted(
        (path for path in directory.glob("*.vtu") if path.resolve() != output_path),
        key=lambda p: p.name,
    )
    if not sorted_files:
        print(f"No VTU files found in {directory}")
        sys.exit(1)

    first_file = sorted_files[0]
    try:
        if args.stream:
            print("Using low-memory streaming mode (ASCII VTU output)")
            combine_streaming(sorted_files, args.output)
        else:
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
