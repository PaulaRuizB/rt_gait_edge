#!/usr/bin/env python
# Copyright 2020-2022, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import os
import sys
from functools import partial

import numpy as np
import tritonclient.grpc as grpcclient
import tritonclient.grpc.model_config_pb2 as mc
import tritonclient.http as httpclient
from PIL import Image
from tritonclient.utils import InferenceServerException, triton_to_np_dtype
import time
import requests

from energy_meter_siroco import EnergyMeter

if sys.version_info >= (3, 0):
    import queue
else:
    import Queue as queue


class UserData:
    def __init__(self):
        self._completed_requests = queue.Queue()
        #self._sampletimes=[]
        


# Callback function used for async_stream_infer()
def completion_callback(user_data, result, error):
    # passing error raise and handling out
    user_data._completed_requests.put((result, error))
    #user_data._sampletimes.append(time.time())

FLAGS = None


def parse_model(model_metadata, model_config):
    """
    Check the configuration of a model to make sure it meets the
    requirements for an image classification network (as expected by
    this client)
    """
    if len(model_metadata.inputs) != 1:
        raise Exception("expecting 1 input, got {}".format(len(model_metadata.inputs)))
    if len(model_metadata.outputs) != 1:
        raise Exception(
            "expecting 1 output, got {}".format(len(model_metadata.outputs))
        )

    if len(model_config.input) != 1:
        raise Exception(
            "expecting 1 input in model configuration, got {}".format(
                len(model_config.input)
            )
        )

    input_metadata = model_metadata.inputs[0]
    input_config = model_config.input[0]
    output_metadata = model_metadata.outputs[0]

    if output_metadata.datatype != "FP32":
        raise Exception(
            "expecting output datatype to be FP32, model '"
            + model_metadata.name
            + "' output type is "
            + output_metadata.datatype
        )

    # Output is expected to be a vector. But allow any number of
    # dimensions as long as all but 1 is size 1 (e.g. { 10 }, { 1, 10
    # }, { 10, 1, 1 } are all ok). Ignore the batch dimension if there
    # is one.
    output_batch_dim = model_config.max_batch_size > 0
    non_one_cnt = 0
    for dim in output_metadata.shape:
        if output_batch_dim:
            output_batch_dim = False
        elif dim > 1:
            non_one_cnt += 1
            if non_one_cnt > 1:
                raise Exception("expecting model output to be a vector")
            
    # Model input must have 3 dims, either CHW or HWC (not counting
    # the batch dimension), either CHW or HWC
    input_batch_dim = model_config.max_batch_size > 0
    expected_input_dims = 3 + (1 if input_batch_dim else 0)
    if len(input_metadata.shape) != expected_input_dims:
        raise Exception(
            "expecting input to have {} dimensions, model '{}' input has {}".format(
                expected_input_dims, model_metadata.name, len(input_metadata.shape)
            )
        )

    if type(input_config.format) == str:
        FORMAT_ENUM_TO_INT = dict(mc.ModelInput.Format.items())
        input_config.format = FORMAT_ENUM_TO_INT[input_config.format]

    #if (input_config.format != mc.ModelInput.FORMAT_NCHW) and (
    #    input_config.format != mc.ModelInput.FORMAT_NHWC
    #):
    #    raise Exception(
    #        "unexpected input format "
    #        + mc.ModelInput.Format.Name(input_config.format)
    #        + ", expecting "
    #        + mc.ModelInput.Format.Name(mc.ModelInput.FORMAT_NCHW)
    #        + " or "
    #       + mc.ModelInput.Format.Name(mc.ModelInput.FORMAT_NHWC)
    #   )

    if input_config.format == mc.ModelInput.FORMAT_NHWC:
        h = input_metadata.shape[1 if input_batch_dim else 0]
        w = input_metadata.shape[2 if input_batch_dim else 1]
        c = input_metadata.shape[3 if input_batch_dim else 2]
    else:
        c = input_metadata.shape[1 if input_batch_dim else 0]
        h = input_metadata.shape[2 if input_batch_dim else 1]
        w = input_metadata.shape[3 if input_batch_dim else 2]

    return (
        model_config.max_batch_size,
        input_metadata.name,
        output_metadata.name,
        c,
        h,
        w,
        input_config.format,
        input_metadata.datatype,
    )


def preprocess(img, format, dtype, c, h, w, scaling, protocol):
    """
    Pre-process an image to meet the size, type and format
    requirements specified by the parameters.
    """
    # np.set_printoptions(threshold='nan')

    if c == 1:
        sample_img = img.convert("L")
    else:
        sample_img = img.convert("RGB")

    resized_img = sample_img.resize((w, h), Image.BILINEAR)
    resized = np.array(resized_img)
    if resized.ndim == 2:
        resized = resized[:, :, np.newaxis]

    npdtype = triton_to_np_dtype(dtype)
    typed = resized.astype(npdtype)

    if scaling == "INCEPTION":
        scaled = (typed / 127.5) - 1
    elif scaling == "VGG":
        if c == 1:
            scaled = typed - np.asarray((128,), dtype=npdtype)
        else:
            scaled = typed - np.asarray((123, 117, 104), dtype=npdtype)
    else:
        scaled = typed

    # Swap to CHW if necessary
    if format == mc.ModelInput.FORMAT_NCHW:
        ordered = np.transpose(scaled, (2, 0, 1))
    else:
        ordered = scaled

    # Channels are in RGB order. Currently model configuration data
    # doesn't provide any information as to other channel orderings
    # (like BGR) so we just assume RGB.
    return ordered

def generate_random_sample (b, c, h, w, f):
    #return torch.rand(b,c,h,w)
    return np.random.rand(b,c,h,w,f).astype(np.float32)
    
def postprocess(results, output_name, batch_size, supports_batching):
    """
    Post-process results to show classifications.
    """

    output_array = results.as_numpy(output_name)
    if supports_batching and len(output_array) != batch_size:
        raise Exception(
            "expected {} results, got {}".format(batch_size, len(output_array))
        )

    # Include special handling for non-batching models
    for results in output_array:
        if not supports_batching:
            results = [results]
        for result in results:
            if output_array.dtype.type == np.object_:
                cls = "".join(chr(x) for x in result).spliºt(":")
            else:
                cls = result.split(":")
            print("    {} ({}) = {}".format(cls[0], cls[1], cls[2]))


def requestGenerator(batched_image_data1, input_name1, 
                     output_name, output_shape, dtype, FLAGS):
    protocol = FLAGS.protocol.lower()

    if protocol == "grpc":
        client = grpcclient
    else:
        client = httpclient

    # Set the input data
    inputs = [client.InferInput(input_name1, batched_image_data1.shape, dtype)]
    inputs[0].set_data_from_numpy(batched_image_data1)

    outputs = [client.InferRequestedOutput(output_name, class_count=FLAGS.classes)]

    yield inputs, outputs, FLAGS.model_name, FLAGS.model_version
    
def get_metrics():
    metrics_url = "http://localhost:8002/metrics"
    r = requests.get(metrics_url)
    r.raise_for_status()
    return r.text

def get_metrics_values(metrics, model_name):
    patterns = [
        model_name
    ]
    values=[]
    for line in metrics.split('\n'):
        if patterns[0] in line:
            fields = line.split()
            values.append(fields[1])
    return values
            
    

def convert_http_metadata_config(_metadata, _config):
    # NOTE: attrdict broken in python 3.10 and not maintained.
    # https://github.com/wallento/wavedrompy/issues/32#issuecomment-1306701776
    try:
        from attrdict import AttrDict
    except ImportError:
        # Monkey patch collections
        import collections
        import collections.abc

        for type_name in collections.abc.__all__:
            setattr(collections, type_name, getattr(collections.abc, type_name))
        from attrdict import AttrDict

    return AttrDict(_metadata), AttrDict(_config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        default=False,
        help="Enable verbose output",
    )
    parser.add_argument(
        "-a",
        "--async",
        dest="async_set",
        action="store_true",
        required=False,
        default=False,
        help="Use asynchronous inference API",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        required=False,
        default=False,
        help="Use streaming inference API. "
        + "The flag is only available with gRPC protocol.",
    )
    parser.add_argument(
        "-conc",
        type=int,
        required=False,
        default=1,
        help="Concurrency. Default is 1.",
    )
    parser.add_argument(
        "-iter",
        type=int,
        required=False,
        default=100,
        help="Concurrency. Default is 1.",
    )
    
    parser.add_argument(
        "-m", "--model-name", type=str, required=True, help="Name of model"
    )
    parser.add_argument(
        "-x",
        "--model-version",
        type=str,
        required=False,
        default="",
        help="Version of model. Default is to use latest version.",
    )
    parser.add_argument(
        "-b",
        "--batch-size",
        type=int,
        required=False,
        default=1,
        help="Batch size. Default is 1.",
    )
    parser.add_argument(
        "-c",
        "--classes",
        type=int,
        required=False,
        default=1,
        help="Number of class results to report. Default is 1.",
    )
    parser.add_argument(
        "-s",
        "--scaling",
        type=str,
        choices=["NONE", "INCEPTION", "VGG"],
        required=False,
        default="NONE",
        help="Type of scaling to apply to image pixels. Default is NONE.",
    )
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        required=False,
        default="localhost:8000",
        help="Inference server URL. Default is localhost:8000.",
    )
    parser.add_argument(
        "-i",
        "--protocol",
        type=str,
        required=False,
        default="HTTP",
        help="Protocol (HTTP/gRPC) used to communicate with "
        + "the inference service. Default is HTTP.",
    )
    parser.add_argument(
        "image_filename",
        type=str,
        nargs="?",
        default=None,
        help="Input image / Input folder.",
    )
    FLAGS = parser.parse_args()
    
     # Initialize thread that measures energy
    energy_measurer_GPU = EnergyMeter('orin2', 2, 'GPU', 0)
    energy_measurer_GPU.start()
    energy = []
    
    if FLAGS.streaming and FLAGS.protocol.lower() != "grpc":
        raise Exception("Streaming is only allowed with gRPC protocol")

    try:
        if FLAGS.protocol.lower() == "grpc":
            # Create gRPC client for communicating with the server
            triton_client = grpcclient.InferenceServerClient(
                url=FLAGS.url, verbose=FLAGS.verbose
            )
        else:
            # Specify large enough concurrency to handle the
            # the number of requests.
            concurrency = 32 if FLAGS.async_set else 1
            triton_client = httpclient.InferenceServerClient(
                url=FLAGS.url, verbose=FLAGS.verbose, concurrency=concurrency
            )
    except Exception as e:
        print("client creation failed: " + str(e))
        sys.exit(1)

    # Make sure the model matches our requirements, and get some
    # properties of the model that we need for preprocessing
    try:
        model_metadata = triton_client.get_model_metadata(
            model_name=FLAGS.model_name, model_version=FLAGS.model_version
        )
        #model_metadata1 = triton_client.get_model_metadata(
        #    model_name=FLAGS.model_name, model_version=FLAGS.model_version
        #)
    except InferenceServerException as e:
        print("failed to retrieve the metadata: " + str(e))
        sys.exit(1)

    try:
        model_config = triton_client.get_model_config(
            model_name=FLAGS.model_name, model_version=FLAGS.model_version
        )
    except InferenceServerException as e:
        print("failed to retrieve the config: " + str(e))
        sys.exit(1)

    if FLAGS.protocol.lower() == "grpc":
        model_config = model_config.config
    else:
        model_metadata, model_config = convert_http_metadata_config(
            model_metadata, model_config
        )
     

    #max_batch_size, input_name, output_name, c, h, w, format, dtype = parse_model(
    #    model_metadata, model_config
    #)
    
      ##################################################
      # Extraemos valores del modelo y la configuracion
      ################################################
      
    if len(model_metadata.inputs) != 1:
        raise Exception("expecting 1 input, got {}".format(len(model_metadata.inputs))
        )
    if len(model_metadata.outputs) != 1:
        raise Exception(
            "expecting 1 output, got {}".format(len(model_metadata.outputs))
        )
            
    max_batch_size = model_config.max_batch_size

    c = model_metadata.inputs[0].shape[1] # 25
    h = model_metadata.inputs[0].shape[2] # 60
    w = model_metadata.inputs[0].shape[3] # 60
    f = model_metadata.inputs[0].shape[4] # 2
    
    input_name = model_metadata.inputs[0].name
    output_name = model_metadata.outputs[0].name
    output_shape = model_metadata.outputs[0].shape
    dtype = model_metadata.inputs[0].datatype


    supports_batching = max_batch_size > 0
    if not supports_batching and FLAGS.batch_size != 1:
        print("ERROR: This model doesn't support batching.")
        sys.exit(1)
        
    batched_image_data = generate_random_sample(FLAGS.batch_size, c, h, w, f)

    num_launches = FLAGS.iter
    launches = num_launches
    min_latency = 9999.0
    min_energy = 9999.0
    start_wall = time.time()
    
       
    # Send requests of FLAGS.batch_size images. If the number of
    # images isn't an exact multiple of FLAGS.batch_size then just
    # start over with the first images until the batch is filled.
    # requests = []
    responses = []
    result_filenames = []
    request_ids = []
    inferences_time = []
    image_idx = 0
    user_data = UserData()

    
    sent_count = 0

    if FLAGS.streaming:
         triton_client.start_stream(partial(completion_callback, user_data))
            
    # Current metrics value        
    metrics = get_metrics()
    init_values = get_metrics_values(metrics, FLAGS.model_name)
    start_time = time.time()
    acc_energy = 0
    
     # START
    request_time_start=[]
    cont_request = 0
    
    energy_measurer_GPU.start_measuring() 
    
    while (launches > 0):
        # Holds the handles to the ongoing HTTP async requests.
        # Start energy measurement
        async_requests = []
        try:
            for inputs, outputs, model_name, model_version in requestGenerator(
                batched_image_data, input_name,
                output_name, output_shape, dtype, FLAGS):
                
                if FLAGS.streaming:
                    triton_client.async_stream_infer(
                        FLAGS.model_name,
                        inputs,
                        request_id=str(cont_request),
                        model_version=FLAGS.model_version,
                         outputs=outputs,
                    ) 
                    cont_request += 1

                elif FLAGS.async_set:
                    if FLAGS.protocol.lower() == "grpc":
                            start = time.time()
                            triton_client.async_infer(
                                FLAGS.model_name,
                                inputs,
                                partial(completion_callback, user_data),
                                request_id=str(cont_request),
                                model_version=FLAGS.model_version,
                                outputs=outputs,
                            )
                            cont_request += 1
                    else:
                        for i in range(FLAGS.conc):
                            async_requests.append(
                                triton_client.async_infer(
                                    FLAGS.model_name,
                                    inputs=inputs,
                                    request_id=str(i),
                                    model_version=FLAGS.model_version,
                                    outputs=outputs,
                                )
                            )
                            cont_request += 1
                else:
                    responses.append(
                         triton_client.infer(
                            FLAGS.model_name,
                            inputs,
                            request_id=str(sent_count),
                            model_version=FLAGS.model_version,
                            outputs=outputs,
                        )
                    )
                    cont_request += 1

        except InferenceServerException as e:
            print("inference failed: " + str(e))
            if FLAGS.streaming:
                triton_client.stop_stream()
            sys.exit(1)
            
        launches -= 1
        if FLAGS.protocol.lower() == "grpc":
            if FLAGS.streaming or FLAGS.async_set:
                processed_count = 0
                while processed_count < num_launches:
                    (results, error) = user_data._completed_requests.get()
                    #if processed_count == 0:
                    #    first_annotatedtime = user_data._sampletimes[processed_count]-start
                    #if processed_count == sent_count-1:
                    #    last_annotatedtime = user_data._sampletimes[processed_count]-start
                    #print("Request time " + str(request_time[processed_count]-start_wall) + "\tResponse time: " + str(user_data._sampletimes[processed_count] -start_wall)
                    #      +"\tDif: "+ str(user_data._sampletimes[processed_count]- request_time[processed_count])) 
                    processed_count += 1
                    if error is not None:
                        print("inference failed: " + str(error))
                        sys.exit(1)
                    responses.append(results)
                    end_response = time.time()

                  #  energy_measurer_GPU.stop_measuring()
                  #  acc_energy = energy_measurer_GPU.total_energy
                #if first_annotatedtime < min_latency:
                #   first_latency = first_annotatedtime
                #    last_latency = last_annotatedtime
                #    min_energy = energy_measurer_GPU.total_energy
        
        else:
            if FLAGS.async_set:
                # Collect results from the ongoing async requests
                # for HTTP Async requests
                 for async_request in async_requests:
                    responses.append(async_request.get_result())
                
                #print ("Async Time: ", stop-start

        #for response in responses:
        #    length = len(response._buffer)
        #    if length != 4096 :
        #        print("Output error")
        #        sys.exit(1)
            
        # print("PASS")
     
    acc_energy = energy_measurer_GPU.total_energy
    energy_measurer_GPU.stop_measuring()
    energy_measurer_GPU.finish()
    end_time = time.time()
    
    if FLAGS.streaming:
                triton_client.stop_stream()
    
    # Gets metrics before starting
    metrics = get_metrics()
    end_values = get_metrics_values(metrics, FLAGS.model_name)
    number_of_inferences = int(end_values[2])-int(init_values[2])
    print("", "Batch=",int(FLAGS.batch_size), "Conc=", int(FLAGS.conc), "Inferences=", number_of_inferences, "Energy_per_inference(mJ)=", acc_energy/number_of_inferences)

"""
    print("Number of succesul requested inferences: ", int(end_values[0])-int(init_values[0]))
    print("Number of failed requested inferences: ", int(end_values[1])-int(init_values[1]))
    print("Number of inferences performed (num_inf*batch_size): ", int(end_values[2])-int(init_values[2]))
    print("Number of inference batch executions: ", int(end_values[3])-int(init_values[3]))
    
    print("Inference request duration (us): ", (int(end_values[4])-int(init_values[4]))/number_of_inferences)
    print("Inference queue duration (us): ", (int(end_values[5])-int(init_values[5]))/number_of_inferences)
    print("Inference compute input duration (us): ", (int(end_values[6])-int(init_values[6]))/number_of_inferences)
    print("Inference compute infer duration (us): ", (int(end_values[7])-int(init_values[7]))/number_of_inferences)
    print("Inference compute output duration (us): ", (int(end_values[8])-int(init_values[8]))/number_of_inferences)
    ##

    #print ("Latencia per sample=", min_latency/(FLAGS.conc * FLAGS.batch_size))
    
    #print("Thoughput (samples per second): ", (FLAGS.conc * FLAGS.batch_size)/last_latency)
    print("Latency: ", end_time - start_time)
    print("Latency per inference: ", (end_time - start_time)/(num_launches) * int(FLAGS.conc))
    print("Troughput (inferences/second): ", number_of_inferences/((int(end_values[4])-int(init_values[4]))/1000000.0)) 
    print("Troughput: ", ((num_launches) * int(FLAGS.conc) * FLAGS.batch_size)/(end_time - start_time))
"""
    #print("", int(FLAGS.batch_size), int(FLAGS.conc), acc_energy/number_of_inferences)
    
   
    

        
