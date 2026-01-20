# rt_gait_edge

Real-time multiple people gait recognition in the edge

# Prerequisites
This project is based on the previous work: [High performance inference of gait recognition models on embedded systems](https://www.sciencedirect.com/science/article/pii/S2210537922001457). Therefore, you must first clone the original repository:
```
git clone https://github.com/PaulaRuizB/Embedded-Gait
```

# Inference 

The inference is performed using NVIDIA Triton as inference server. Similarly, we use NVIDIA Performance Analyzer as inference client to measure inference performance. Both applications are executed using Docker containers. In addition, we have developed a inference client that calculates energy consumption per inference. Following, more details are given.

## Inference Server
The inference server runs inferences and must be running on the Jetson platform. The best way to run the server is using docker images. In our experiments, we have employed the image named `nvcr.io/nvidia/tritonserver:24.01-py3-igpu` that can be downloaded from <https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver/tags>. The comamnd to run the docker container is:

```
docker run --runtime nvidia --rm --net=host -v /[*pathtomodelrepository]*/model_repository/:/models nvcr.io/nvidia/tritonserver:24.01-py3-igpu tritonserver --model-repository=/models
```

_Comment: when the container starts, it executes the `/opt/nvidia_entrypoint.sh` file. This script performs several checks. Among them, it checks if the driver is installed by executing `nvidia-smi` command. As this command is not present in Jetson, the container shows the message  “Failed to detect NVIDIA driver version”. This message can be dismissed as the driver is working._

Models employed for inferences must be storage in the host directory `/[*pathtomodelrepository]*/model_repository/`

In the `model_repository` directory, a specific hierarchy must be used for each model. Following, an example of the hierarchy for the `2Dbase` model is shown:

```text
model_repository/
└── 2Dbase/
    └── 1/
        └── model.plan
```

In the file `model_repository.tgz` you have an example of model repository including two gait recognition models, `3D_best_0_batchd` (3D convolutions, best quantization, no pruning and dynamic batch) and `2D_int8_40_batchd` (2D convolutions, int8 quantization, 40% pruned and dynamic batch) in TensorRT (`model.plan`)

## Performance analyzer

It automatically executes several inferences and extracts performance metrics. Performance analyzer is in another docker image with the `sdk` tag. We have used `nvcr.io/nvidia/tritonserver:24.01-py3-igpu-sdk`. In order to run the container on the Jetson platform, execute:

```
sudo docker run --runtime nvidia -it --rm --net=host nvcr.io/nvidia/tritonserver:24.01-py3-igpu-sdk
```

Before running this container, the Server container must be already running as the performance analyzer runs the inferences in the server. As performance evaluation does not require accuracy measurements, real input samples are not necessary. Thus, they are not necessary to run the `perf_analyzer` command. 

Several commands can be used to run inferences on the Performance Analyzer container. Please have a look at the NVIDIA Triton performance Analyzer manual.

The script `performance_sweeping.sh`, using performance analyzer, executes several configurations and calculates the performance. 

## Energy consumption

The files `3DGait_client_ver2.py` and `energy_merter.py` allow running different configurations with concurrency and batching values, and calculating the energy consumption per inference. The script `energy_sweeping.sh` shows how to do it. 

## Our papers: 

If you find this code useful in your research, please consider citing:

* Original paper: [High performance inference of gait recognition models on embedded systems](https://www.sciencedirect.com/science/article/pii/S2210537922001457)


        @article{ruiz2022high,
        title={High performance inference of gait recognition models on embedded systems},
        author={Ruiz-Barroso, Paula and Castro, Francisco M and Delgado-Esca{\~n}o, Rub{\'e}n and Ramos-C{\'o}zar, Juli{\'a}n and Guil, Nicol{\'a}s},
        journal={Sustainable Computing: Informatics and Systems},
        volume={36},
        pages={100814},
        year={2022},
        publisher={Elsevier}
        }

  
* Our paper: [Real-time multiple people gait recognition in the edge](https://www.nature.com/articles/s41598-025-02351-x).

          @article{ruiz2025real,
          title={Real-time multiple people gait recognition in the edge},
          author={Ruiz-Barroso, Paula and Gonz{\'a}lez-Linares, Jos{\'e} Mar{\'\i}a and Castro, Francisco M and Guil, Nicol{\'a}s},
          journal={Scientific Reports},
          volume={15},
          number={1},
          pages={19276},
          year={2025},
          publisher={Nature Publishing Group UK London}
          }
  
## 📈Traffic stats:

This section displays the accumulated historical data for views and clones, updated daily to bypass GitHub's 14-day retention limit:

Metric | Status |
| :--- | :--- |
| **Total Views** | ![Views](https://img.shields.io/badge/dynamic/json?color=blue&label=views&query=count&url=https%3A%2F%2Fraw.githubusercontent.com%2FPaulaRuizB%2Frt_gait_edge%2Fmain%2Fstats%2Fviews.json) |
| **Unique Visitors** | ![Unique Views](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=unique%20visitors&query=uniques&url=https%3A%2F%2Fraw.githubusercontent.com%2FPaulaRuizB%2Frt_gait_edge%2Fmain%2Fstats%2Fviews.json) |
| **Total Clones** | ![Clones](https://img.shields.io/badge/dynamic/json?color=orange&label=clones&query=count&url=https%3A%2F%2Fraw.githubusercontent.com%2FPaulaRuizB%2Frt_gait_edge%2Fmain%2Fstats%2Fclones.json) |
| **Unique Cloners** | ![Unique Clones](https://img.shields.io/badge/dynamic/json?color=yellow&label=unique%20cloners&query=uniques&url=https%3A%2F%2Fraw.githubusercontent.com%2FPaulaRuizB%2Frt_gait_edge%2Fmain%2Fstats%2Fclones.json) |

> *Data automatically updated every 24 hours via GitHub Actions. Historical logs stored in `/stats`.*
