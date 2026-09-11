#!/bin/bash
#SBATCH --job-name=combine-vtu
#SBATCH --time=04:00:00
#SBATCH --mem=64G
#SBATCH --cpus-per-task=1
#SBATCH --output=combine-vtu-%j.out
#SBATCH --error=combine-vtu-%j.err

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: sbatch combine_vtu.slurm INPUT_DIRECTORY [OUTPUT_FILE]" >&2
    exit 2
fi

input_dir="$1"
output_file="${2:-${input_dir%/}/results-combined.vtu}"
repo_dir="${HOME}/combine-vtu-sherlock"
venv_dir="${HOME}/venvs/combine-vtu"

module purge
module load python/3.12.1

if [[ ! -x "${venv_dir}/bin/python" ]]; then
    echo "Missing virtual environment: ${venv_dir}" >&2
    echo "Create it with the setup commands in README.md before submitting." >&2
    exit 1
fi

source "${venv_dir}/bin/activate"

echo "Host: $(hostname)"
echo "Input: ${input_dir}"
echo "Output: ${output_file}"
python "${repo_dir}/combine-vtu.py" "${input_dir}" \
    --output "${output_file}" \
    --stream

echo "Finished: ${output_file}"
