#! /bin/bash

# prepares a pre-train zstd dictionary from addok formatted json data
# Usage: ./zstd-train.sh myfile.json sample_number output_file
# Requires: jq, zstd

TMPDIR=/tmp/zstd-train
mkdir -p $TMPDIR
shuf $1 | head -n $2 | jq -s -c .[] > $TMPDIR/zstd-train.json
for L in {1..$2}; do head -n +$L $TMPDIR/zstd-train.json | tail -n 1 > $TMPDIR/$L ; done
zstd --train $TMPDIR/* -o $3
rm -rf $TMPDIR
