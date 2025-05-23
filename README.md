# rt_gait_edge

Real-time multiple people gait recognition in the edge

### Prerequisites
1. This project is based on the previous work: [High performance inference of gait recognition models on embedded systems](https://www.sciencedirect.com/science/article/pii/S2210537922001457). Therefore, you must first clone the original repository:
```
git clone https://github.com/PaulaRuizB/Embedded-Gait
```


### Our papers: 

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

  
* The paper describing this project has been accepted and will be available soon.

# Deployment on Triton

## Inference Server
It runs inferences. It must be running on the Jetson platform. The best way to run the server is using docker images. In our experiments,  we have employed the image named  nvcr.io/nvidia/tritonserver:24.01-py3-igpu that can be downloaded from <https://catalog.ngc.nvidia.com/orgs/nvidia/containers/tritonserver/tags>.

Deployment command: 

docker run --runtime nvidia --rm --net=host -v /[*pathtomodelrepository]*/model\_repository/:/models nvcr.io/nvidia/tritonserver:24.01-py3-igpu tritonserver --model-repository=/models

_Comment: when the container starts, it executes the /opt/nvidia\_entrypoint.sh file. This batch file performs several checks. Among them, it checks if the driver is installed by executing nvidia-smi command. As this command is not present in Jetson, the container shows the message  “ Failed to detect NVIDIA driver version.”. This message can be dismissed as the driver is working._

Models employed for inferences must be storage in the host directory /[*pathtomodelrepository]*/model\_repository/ 

In the model\_repository directory, a specific hierarchy must be used for each model. An example:
model\_repository

2Dbase/

model\_repository

2Dbase/

`  `1/

`    `model.plan

## Performance Analyzer

It automatically executes several inferences and extracts performance metrics. Performance analyzer is in another docker image with the “sdk” tag. We have used nvcr.io/nvidia/tritonserver:24.01-py3-igpu-sdk. In order to run the container, the following command is executed in the Jetson platform:

sudo docker run --runtime nvidia -it --rm --net=host nvcr.io/nvidia/tritonserver:24.01-py3-igpu-sdk

Before running this container, the Server container must be already running as the performance analyzer runs the inferences in the server. As performance does not calculate accuracy, no real input samples are required. Thus, they are not necessary to run the perf\_analyzer command. 

Several commands can be used to run inferences on the Performance Analyze container. Please have a look at the NVIDIA Triton performance Analyzer manual.




