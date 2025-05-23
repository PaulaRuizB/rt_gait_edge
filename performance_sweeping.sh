#/bin/bash

for b in 1 4 8 12 16 20 24 28 32
do
	for c in 1 4 8 12 16 20 24 28 32
	do
		echo "perf_analyzer -a -m $1 -b $b --concurrency-range ${c}:${c} -f sal$1_b${b}_c${c}.txt"
		perf_analyzer -a -m $1 -b $b --concurrency-range ${c}:${c} -f sal$1_b${b}_c${c}.txt
	done
done
