#!/usr/bin/env bash

if [ "$1" != "" ]; then
    CLI_OUT_PATH=$1
else
    echo "Path to cli output cannot be empty"
    exit
fi

SIMBAD_ANALYZER_WORKDIR="${SIMBAD_ANALYZER_WORKDIR:-.}"

declare -a output_files=(
  "time_points.parquet"
  "large_clones.parquet"
  "clone_snapshots.parquet"
  "final_snapshot.csv"
  "clone_stats.parquet"
  "clone_stats_scalars.parquet"
  "large_muller_order.parquet"
  "muller_data.parquet"
  "final_mutation_freq.parquet"
  "clone_counts.parquet"
  "large_final_mutations.parquet"
)

CLI_OUT_CONTENT=$(tail -10 $CLI_OUT_PATH)
RANDOM_FROM=10
RANDOM_TO=1000

for i in "${output_files[@]}"
do
   ARTIFACT_PATH="$SIMBAD_ANALYZER_WORKDIR/$i"
   NUM_CHARS=$(shuf -i $RANDOM_FROM-$RANDOM_TO -n 1)
   echo $CLI_OUT_CONTENT > "$ARTIFACT_PATH"
   head /dev/urandom | tr -dc A-Za-z0-9 | head -c $NUM_CHARS >> "$ARTIFACT_PATH"
   echo $ARTIFACT_PATH
   sleep 3s
done