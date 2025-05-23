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
		if self.device == 'nano':
			# Whole board
			self.sensors['POM_5V_IN'] = open('/sys/bus/i2c/drivers/ina3221x/6-0040/iio:device0/in_current0_input', 'r')
			# GPU
			self.sensors['POM_5V_GPU'] = open('/sys/bus/i2c/drivers/ina3221x/6-0040/iio:device0/in_current1_input', 'r')
			# CPU
			self.sensors['POM_5V_CPU'] = open('/sys/bus/i2c/drivers/ina3221x/6-0040/iio:device0/in_current2_input', 'r')

			if self.mode == 'GPU':
				self.mode = 'POM_5V_GPU'
			else:
				self.mode = 'POM_5V_CPU'
		elif self.device == 'xavier':
			# GPU
			self.sensors['GPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon3/curr1_input', 'r')
			# CPU
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon3/curr2_input', 'r')
			# SoC - GPU - CPU (rest of SoC components)
			self.sensors['SOC'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon3/curr3_input', 'r')
			# Computer Vision modules + Deep Learning Accelerators
			self.sensors['CV'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon4/curr1_input', 'r')
			# Memory
			self.sensors['VDDRQ'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon4/curr2_input', 'r')
			# Other components of the board (eMMC, video, audio, etc)
			self.sensors['SYS5V'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon4/curr3_input', 'r')

		elif self.device == 'orin':
			# GPU
			self.sensors['GPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon0/curr1_input', 'r')
			# CPU
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon0/curr2_input', 'r')
			# SoC - GPU - CPU (rest of SoC components)
			self.sensors['SOC'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon0/curr3_input', 'r')
			# Computer Vision modules + Deep Learning Accelerators
			self.sensors['CV'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr1_input', 'r')
			# Memory
			self.sensors['VDDRQ'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr2_input', 'r')
			# Other components of the board (eMMC, video, audio, etc)
			self.sensors['SYS5V'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon1/curr3_input', 'r')
   
		elif self.device == 'orin2':
			# GPU
			self.sensors['GPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr1_input', 'r')
    		# CPU
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr2_input', 'r')
			self.sensors['CPU'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr2_input', 'r')
			# SoC - GPU - CPU (rest of SoC components)
			self.sensors['SOC'] = open('/sys/bus/i2c/drivers/ina3221/1-0040/hwmon/hwmon1/curr3_input', 'r')
			# Computer Vision modules + Deep Learning Accelerators
			self.sensors['CV'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon2/curr1_input', 'r')
            # Memory
			self.sensors['VDDRQ'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon2/curr2_input', 'r')
            # Other components of the board (eMMC, video, audio, etc)
			self.sensors['SYS5V'] = open('/sys/bus/i2c/drivers/ina3221/1-0041/hwmon/hwmon2/curr3_input', 'r')

		# Launch threads.
		self.measuring = False
		self.executing = True
		threading.Thread.__init__(self)

	def run(self):
		while self.executing:
			while self.measuring:
				t = time.time_ns()
				energy = int(self.sensors[self.mode].read().strip())
				self.total_energy = self.total_energy + (0.002 * energy)
				self.sensors[self.mode].seek(0)

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
