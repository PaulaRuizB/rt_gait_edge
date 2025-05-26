import threading
import time
from queue import Queue

class EnergyMeter(threading.Thread):
	def __init__(self, device, sleep_time, mode, descartes):
		self.device = device
		self.sleep_time = float(sleep_time / 1000.0)
		self.mode = mode
		self.queue = Queue()
		self.total_energy = 0.0
		self.COUNTER = 0
		self.time = 0.0
		self.steps = 0
		self.sensors = dict()
		self.descartes = descartes
		if self.device == 'orin':
			# GPU
			self.sensors['GPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr1_input', 'r')
			self.sensors['VGPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/in1_input', 'r')
			# CPU
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr2_input', 'r')
			# SoC - GPU - CPU (rest of SoC components)
			self.sensors['SOC'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr3_input', 'r')
			# Computer Vision modules + Deep Learning Accelerators
			self.sensors['CV'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr1_input', 'r')
			# Memory
			self.sensors['VDDRQ'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr2_input', 'r')
			# Other components of the board (eMMC, video, audio, etc)
			self.sensors['SYS5V'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr3_input', 'r')   
		elif self.device == 'orin2':
			# GPU
			self.sensors['GPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr1_input', 'r')
			self.sensors['VGPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/in1_input', 'r')
    		# CPU
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr2_input', 'r')
			# SoC - GPU - CPU (rest of SoC components)
			self.sensors['SOC'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr3_input', 'r')
			# Computer Vision modules + Deep Learning Accelerators
			self.sensors['CV'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr1_input', 'r')
            # Memory
			self.sensors['VDDRQ'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr2_input', 'r')
            # Other components of the board (eMMC, video, audio, etc)
			self.sensors['SYS5V'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr3_input', 'r')
		else:
			print("Device not supported\n")
			return

		# Launch threads.
		self.measuring = False
		self.executing = True
		threading.Thread.__init__(self)

	def run(self):
		while self.executing:
			while self.measuring:
				t = time.time_ns()			
				mA = float(self.sensors[self.mode].read().strip())
				mV = float(self.sensors['VGPU'].read().strip())
				self.total_energy = self.total_energy + (self.sleep_time * mA * mV/1000.0)
				self.sensors[self.mode].seek(0)
				self.sensors['VGPU'].seek(0)

				time.sleep(max(self.sleep_time - ((time.time_ns() - t) / 1e9), 0))

		#print((time.time_ns() - t) / (1000.0*1000.0*1000.0))
				#time.sleep(self.sleep_time)
			#time.sleep(self.sleep_time)


	# def write_function(self):
	# 	while self.measuring or not self.queue.empty():
	# 		if not self.queue.empty():
	# 			self.file.write(self.queue.get() + '\n')

	def start_measuring(self):
		self.total_energy = 0.0
		self.time = 0.0
		self.measuring = True

	def stop_measuring(self):
		self.measuring = False

	def finish(self):
		self.measuring = False
		self.executing = False
		self.join()

if __name__ == '__main__':
    measurer = EnergyMeter('xavier', 100, 'GPU', '/tmp/', 'prueba.txt')
    measurer.start()
    time.sleep(5)
    measurer.finish()
    print(measurer.total_energy)
