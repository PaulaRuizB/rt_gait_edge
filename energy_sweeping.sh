#/bin/bash

for b in 1 4 8 12 16 20 24 28 32
do
	python 3DGait_client_ver2.py -m 3D_best_0_batchd -a -b $b -conc 8 -iter 300 
done
