# -*- coding: utf-8 -*-
"""
Created on Tue Mar 19 10:40:05 2024

@author: Grisha Spektor
"""

import pyvisa as visa
import matplotlib.pyplot as plt
import struct
import math
import gc
import os

class SiglentScope:
    HORI_NUM = 10 #page 696 in the table corresponds to the grid variable (https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf)
    # This is the time base table in page 691 of (https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf)
    
    tdiv_enum = [200e-12, 500e-12, 1e-9,
                 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9,
                 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
                 1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
                 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

    def __init__(self, resource_string):
        self.resource_string = resource_string
        self._rm = visa.ResourceManager()
        self.scope = self._rm.open_resource(self.resource_string)
        self.scope.timeout = 2000
        self.scope.chunk_size = 10000000
        self.channel_data = {}  # Dictionary to store data for each channel
    
    def get_channel_data(self, channel):
            # Check if the channel data exists and return it
            if channel in self.channel_data:
                return self.channel_data[channel]
            else:
                raise ValueError(f"No data available for channel {channel}. Please ensure the channel number is correct and the data has been acquired.")

    def _parse_preamble(self, recv):
        # Parsing waveform preamble data according to: https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf
        WAVE_ARRAY_1 = recv[0x3c:0x3f + 1]
        wave_array_count = recv[0x74:0x77 + 1]
        first_point = recv[0x84:0x87 + 1]
        sp = recv[0x88:0x8b + 1]
        v_scale = recv[0x9c:0x9f + 1]
        v_offset = recv[0xa0:0xa3 + 1]
        interval = recv[0xb0:0xb3 + 1]
        code_per_div = recv[0xa4:0xa7 + 1]
        adc_bit = recv[0xac:0xad + 1]
        delay = recv[0xb4:0xbb + 1]
        tdiv = recv[0x144:0x145 + 1]
        probe = recv[0x148:0x14b + 1]
        
        data_bytes = struct.unpack('i', WAVE_ARRAY_1)[0]
        point_num = struct.unpack('i', wave_array_count)[0]
        fp = struct.unpack('i', first_point)[0]
        sp = struct.unpack('i', sp)[0]
        interval = struct.unpack('f', interval)[0]
        delay = struct.unpack('d', delay)[0]
        tdiv_index = struct.unpack('h', tdiv)[0]
        probe = struct.unpack('f', probe)[0]
        vdiv = struct.unpack('f', v_scale)[0] * probe
        offset = struct.unpack('f', v_offset)[0] * probe
        code = struct.unpack('f', code_per_div)[0]
        adc_bit = struct.unpack('h', adc_bit)[0]
        tdiv = SiglentScope.tdiv_enum[tdiv_index]
        
        return vdiv, offset, interval, delay, tdiv, code, adc_bit

    def _read_waveform_data(self, channel):
        # Logic to read the waveform data
        # Return the waveform data and time axis
        self.scope.write(f":WAV:SOUR C{channel}")
        self.scope.write(":WAV:PREamble?")
        recv_all = self.scope.read_raw()
        recv = recv_all[recv_all.find(b'#') + 11:]

        # Parse the waveform parameters
        vdiv, ofst, interval, trdl, tdiv, vcode_per, adc_bit = self._parse_preamble(recv)

        # Logic to read the waveform data
        points = float(self.scope.query(":ACQuire:POINts?").strip())
        one_piece_num = float(self.scope.query(":WAVeform:MAXPoint?").strip())
        read_times = math.ceil(points / one_piece_num)

        if points > one_piece_num:
            self.scope.write(":WAVeform:POINt {}".format(one_piece_num))

        self.scope.write(":WAVeform:WIDTh BYTE")
        
        if adc_bit > 8:
            self.scope.write(":WAVeform:WIDTh WORD")

        recv_byte = b''
        for i in range(read_times):
            start = i * one_piece_num
            self.scope.write(":WAVeform:STARt {}".format(start))
            self.scope.write("WAV:DATA?")
            recv_rtn = self.scope.read_raw()

            # Find the start of the data block after the header
            block_start = recv_rtn.find(b'#') + 2
            data_digit = int(chr(recv_rtn[block_start - 1]))
            data_start = block_start + data_digit
            data_end = data_start + int(recv_rtn[block_start:block_start + data_digit])
            recv_byte += recv_rtn[data_start:data_end]

        if adc_bit > 8:
            convert_data = struct.unpack(f">{int(len(recv_byte) / 2)}h", recv_byte)
        else:
            convert_data = struct.unpack(f"{len(recv_byte)}b", recv_byte)

        # Calculate the voltage value and time value
        volt_value = [(cv / vcode_per * vdiv) - ofst for cv in convert_data]
        time_value = [(-tdiv * SiglentScope.HORI_NUM / 2) + (i * interval) + trdl for i in range(len(convert_data))]
        
        # Save the data to the class
        self.channel_data[channel] = (time_value, volt_value)

        return time_value, volt_value
    
    def save_data(self, filename):
        # Save the waveform data
        base_filename, _ = os.path.splitext(filename)
        data_filename = f"{base_filename}.csv"
        with open(data_filename, 'w') as f:
            for channel, (time_values, volt_values) in self.channel_data.items():
                f.write(f'Channel {channel}\n')
                f.write('Time(s),Voltage(V)\n')
                for t, v in zip(time_values, volt_values):
                    f.write(f'{t},{v}\n')
                f.write('\n')

        # Save the plot
        plot_filename = f"{base_filename}.png"
        self.fig.savefig(plot_filename)
        
    @staticmethod
    def list_visa_addresses():
        rm = visa.ResourceManager()
        addresses = rm.list_resources()
        instruments = {}

        for address in addresses:
            try:
                instrument = rm.open_resource(address)
                idn = instrument.query('*IDN?')
                instruments[address] = idn.strip()
            except Exception as e:
                print(f"Error querying device at {address}: {e}")
                instruments[address] = "Could not query IDN"

        return instruments


    def plot_channels(self, channel_vec=[1, 2, 3, 4], labels=None, title=""):
        self.fig, self.ax = plt.subplots(figsize=(10, 6))

        if labels is None:
            labels = [f'Channel {ch}' for ch in channel_vec]

        for i, channel in enumerate(channel_vec):
            if channel in self.channel_data:
                time_value, volt_value = self.channel_data[channel]
            else:
                time_value, volt_value = self._read_waveform_data(channel)
            self.ax.plot(time_value, volt_value, label=labels[i])

        self.ax.set_title(title)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.legend(loc="upper right")
        self.ax.grid(True)
        plt.show()

if __name__ == '__main__':
    scope = SiglentScope("USB0::0xF4EC::0x1011::SDS2PEED6R3524::INSTR")
    scope.plot_channels([1,2],labels=['signal','output'],title = "Modulator 1")  # Example usage
    scope.save_data('channel_data.csv')
    
    visa_addresses = SiglentScope.list_visa_addresses()
    for address, idn in visa_addresses.items():
        print(f"{address}: {idn}")

