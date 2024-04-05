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

#<todo>
# make sequence reading capability with selected frames.
# can we get the state of the scope measurement? - seems that I can get it through manually saving a csv file with the options and then manually setting them.
# But I don't think I wanna do it...
# can we then set the state of the scope measurement?
class SiglentScope:
    """
    A class to interface with a Siglent oscilloscope and perform data acquisition and analysis.

    Attributes:
        HORI_NUM (int): Represents the horizontal number used in time base calculations.
        tdiv_enum (list): Time division settings for the oscilloscope.
        resource_string (str): VISA resource string to connect to the oscilloscope.
        channel_data (dict): Stores the waveform data for each channel.
    """
    HORI_NUM = 10 #page 696 in the table corresponds to the grid variable (https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf)
    
    # This is the time base table in page 691 of (https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf)
    tdiv_enum = [200e-12, 500e-12, 1e-9,
                 2e-9, 5e-9, 10e-9, 20e-9, 50e-9, 100e-9, 200e-9, 500e-9,
                 1e-6, 2e-6, 5e-6, 10e-6, 20e-6, 50e-6, 100e-6, 200e-6, 500e-6,
                 1e-3, 2e-3, 5e-3, 10e-3, 20e-3, 50e-3, 100e-3, 200e-3, 500e-3,
                 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]

    def __init__(self, resource_string):
        """
        Initializes the SiglentScope with the given VISA resource string.

        Args:
            resource_string (str): The VISA resource string for the oscilloscope.
            Can be obtained by running SiglentScope.list_visa_addresses()
        """
        self.resource_string = resource_string
        self._rm = visa.ResourceManager()
        self.scope = self._rm.open_resource(self.resource_string)
        print("connected to scope.")
        self.scope.timeout = 2000
        self.scope.chunk_size = 10000000
        self.channel_data = {}  # Dictionary to store data for each channel
    
    def get_channel_data(self, channel):
        """
        Retrieves the waveform data for a specified channel.

        Args:
            channel (int): The channel number to retrieve data for.

        Returns:
            tuple: A tuple containing time values and voltage values for the channel.

        Raises:
            ValueError: If data for the specified channel is not available.
        """
        # Check if the channel data exists and return it
        if channel in self.channel_data:
            return self.channel_data[channel]
        else:
            raise ValueError(f"No data available for channel {channel}. Please ensure the channel number is correct and the data has been acquired.")

    def _main_time_stamp_deal(self, time):
        """
        main_time_stamp_deal:Parsing timestamps from binary blocks
        https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf page 784


        Parameters
        ----------
        time : a binary block
            DESCRIPTION.

        Returns
        -------
        None.

        """
        seconds = time[0x00:0x08] # long double
        minutes = time[0x08:0x09] # char
        hours = time[0x09:0x0a] # char
        days = time[0x0a:0x0b] # char
        months = time[0x0b:0x0c] # char
        year = time[0x0c:0x0e] # short
        seconds = struct.unpack('d',seconds)[0]
        minutes = struct.unpack('c', minutes)[0]
        hours = struct.unpack('c', hours)[0]
        days = struct.unpack('c', days)[0]
        months = struct.unpack('c', months)[0]
        year = struct.unpack('h', year)[0]
        months = int.from_bytes(months, byteorder='big', signed=False)
        days = int.from_bytes(days, byteorder='big', signed=False)
        hours = int.from_bytes(hours, byteorder='big', signed=False)
        minutes = int.from_bytes(minutes, byteorder='big', signed=False)
        
        return "{}/{}/{},{}:{}:{}".format(year,months,days,hours,minutes,seconds)

    def _parse_preamble(self, recv, reading_frames=False):
        """
        Parses the waveform preamble data to extract essential parameters.
        Parsing waveform preamble data according to: https://www.siglenteu.com/wp-content/uploads/dlm_uploads/2024/03/ProgrammingGuide_EN11F.pdf

        Args:
            recv (bytes): The raw preamble data received from the oscilloscope.
            reading_frames: a backward-compatability flag to not disturb the reading procedure of the regular channel

        Returns:
            tuple: A tuple containing various oscilloscope parameters like vertical division, offset, etc.
        """
        
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
        
        # additional paramteres for the Sequence frame reading:
        if reading_frames:
            data_width = recv[0x20:0x21+1]#01-16bit,00-8bit
            data_order = recv[0x22:0x23+1]#01-MSB,00-LSB
            one_fram_pts = recv[0x74:0x77+1]#pts of single frame,maybe bigger than 12.5M
            read_frame = recv[0x90:0x93+1]#all sequence frames number return by this command
            sum_frame = recv[0x94:0x97+1]#all sequence frames number acquired
            sn = recv[0xae:0xaf+1]
            interval = recv[0xb0:0xb3+1]
            
            width = struct.unpack('h',data_width)[0]
            order = struct.unpack('h',data_order)[0]
            sn = struct.unpack('h',sn)[0]
            one_fram_pts = struct.unpack('i',one_fram_pts)[0]
            read_frame = struct.unpack('i',read_frame)[0]
            sum_frame = struct.unpack('i',sum_frame)[0]

        
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
        
        if reading_frames: # returns more arguments.
            return vdiv,offset,interval,delay,tdiv,code,adc_bit,one_fram_pts,read_frame,sum_frame
        else:
            return vdiv, offset, interval, delay, tdiv, code, adc_bit

    def read_sequence_frame(self, channel, frame_num=1):
        """
        Read data of single frame of a sequence.
        Assumes there is a sequence! no error checking.
        A bit duplicated with read_waveform_data

        Parameters
        ----------
        channel : int
            number of channel to read from.
        frame_num : int
            number of frame to load - no error checking!.

        Returns
        -------
        time and voltage traces .

        """
        print(f"Reading channel {channel}, frame {frame_num}..")
        self.scope.write(f":WAV:SOUR C{channel}")
        
               
        self.scope.write(":WAVeform:STARt 0")
        self.scope.write(":WAVeform:POINt 0")
        self.scope.write(":WAVeform:SEQUence {},{}".format(frame_num,0))
        
        self.scope.write(":WAV:PREamble?")
        recv_all = self.scope.read_raw()
        # print(len(recv_all)) # just the package length.
        recv = recv_all[recv_all.find(b'#')+11:]
        time_stamp = recv[346:]
        
                
        vdiv, ofst, interval, delay, tdiv, code,adc_bit,one_frame_pts, read_frame, sum_frame = self._parse_preamble(recv,reading_frames=True)
        
        one_piece_num = float(self.scope.query(":WAVeform:MAXPoint?").strip())
        
        if one_frame_pts > one_piece_num:
            self.scope.write(":WAVeform:POINt {}".format(one_piece_num))
        
        self.scope.write(":WAVeform:WIDTh BYTE")
        # if there is a 10 bit option set in the Acquisition setting
        if adc_bit > 8:
            self.scope.write(":WAVeform:WIDTh WORD")
        
        read_times = math.ceil(one_frame_pts / one_piece_num)
        data_recv = b''
        
        for i in range(0, read_times):
            start = i * one_piece_num
            self.scope.write(":WAVeform:STARt {}".format(start))
            self.scope.write("WAV:DATA?")
            recv_rtn = self.scope.read_raw().rstrip()
            
            block_start = recv_rtn.find(b'#')
            data_digit = int(recv_rtn[block_start + 1:block_start + 2])
            data_start = block_start + 2 + data_digit
            data_recv += recv_rtn[data_start:]
            
        # print("len(data_recv)=", len(data_recv))
        

        if adc_bit > 8:
            convert_data = struct.unpack("%dh" % one_frame_pts, data_recv)
        else:
            convert_data = struct.unpack("%db" % one_frame_pts, data_recv)
            
        volt_value = []
        time_value = []
        
        for idx in range(0, len(convert_data)):
            volt_value.append(convert_data[idx] / code * float(vdiv) - float(ofst))
            time_value.append(-(float(tdiv) * SiglentScope.HORI_NUM / 2) + idx * interval + delay)
               
        # Save the data to the class
        self.channel_data[channel] = (time_value, volt_value)
        self.sequence_frame_number = frame_num
        #parse and print the timestamp - perhaps remove?
        self.frame_timestamp = self._main_time_stamp_deal(time_stamp)

        return time_value, volt_value
        
        

    def read_waveform_data(self, channel):
        """
        Reads waveform data from the oscilloscope for the specified channel and stores it.

        Args:
            channel (int): The channel number to read data from.

        Returns:
            tuple: A tuple containing time values and voltage values for the waveform.
        """
        
        # Return the waveform data and time axis
        print('Reading Data..')
        self.scope.write(f":WAV:SOUR C{channel}")
        self.scope.write(":WAV:PREamble?")
        recv_all = self.scope.read_raw()
        print(f'Read channel {channel} data.')
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
        # if there is a 10 bit option set in the Acquisition setting
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
        """
        Saves the collected waveform data for all available channels into a CSV file,
        formatting the headers and data according to the specified layout.
    
        Args:
            filename (str): Base filename to save the data. The extension is added automatically.
        """
        base_filename, _ = os.path.splitext(filename)
        data_filename = f"{base_filename}.csv"
    
        # Ensure the directory exists
        os.makedirs(os.path.dirname(data_filename), exist_ok=True)
    
        with open(data_filename, 'w') as f:
            # Write channel headers
            for ch in self.channel_data.keys():
                f.write(f'Channel {ch},,')
            f.write('\n')
    
            # Write sub-headers for Time and Voltage
            for _ in self.channel_data.keys():
                f.write('Time (s),Voltage (V),')
            f.write('\n')
    
            # Find the longest set of data points among all channels
            max_length = max(len(data[1]) for data in self.channel_data.values())
    
            # Write data
            for i in range(max_length):
                for ch, (time_values, volt_values) in self.channel_data.items():
                    if i < len(time_values):
                        f.write(f"{time_values[i]},{volt_values[i]},")
                    else:
                        # Fill in empty data if this channel has fewer points
                        f.write(' , ,')
                f.write('\n')
    
        # Save the plot if it exists
        if hasattr(self, 'fig'):
            plot_filename = f"{base_filename}.png"
            self.fig.savefig(plot_filename)

    @staticmethod
    def list_visa_addresses():
        """
        Lists all VISA addresses and their corresponding device IDNs.

        Returns:
            dict: A dictionary with VISA addresses as keys and device IDNs as values.
        """
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

    @staticmethod
    def plot_external_channel_data(channel_data, channels_to_plot=None, channel_titles=None):
        """
        Plots the waveform data for specified channels with custom titles, using externally provided data.

        Args:
            channel_data (dict): A dictionary containing the waveform data for each channel,
                                 where each key is a channel number, and the value is a tuple of (time_values, volt_values).
            channels_to_plot (list, optional): A list of channels to plot. If None, plots all channels in the provided data.
            channel_titles (dict, optional): A dictionary mapping channels to custom titles.
        """
        if channels_to_plot is None:
            channels_to_plot = channel_data.keys()
        
        plt.figure(figsize=(10, 6))
        
        for channel in channels_to_plot:
            if channel in channel_data:
                time_values, volt_values = channel_data[channel]
                title = channel_titles.get(channel, f"Channel {channel}") if channel_titles else f"Channel {channel}"
                plt.plot(time_values, volt_values, label=title)
            else:
                print(f"Data for Channel {channel} is not available.")
        
        plt.title("External Scope Data")
        plt.xlabel("Time (s)")
        plt.ylabel("Voltage (V)")
        plt.legend()
        plt.grid(True)
        plt.show()

    def plot_channels(self, channel_vec=[1, 2, 3, 4], labels=None, title="", read_data = True, sequence_frame_number = None):
        """
        Plots the waveform data for the specified channels.

        Args:
            channel_vec (list of int): A list of channels to plot.
            labels (list of str, optional): A list of labels for the channels. Defaults to None.
            title (str, optional): The title of the plot. Defaults to an empty string.
            read_data (bool, optional): If True, read data from the scope before plotting. Defaults to True.
        """
        self.fig, self.ax = plt.subplots(figsize=(10, 6))

        if labels is None:
            labels = [f'Channel {ch}' for ch in channel_vec]
            
        if sequence_frame_number is None:    

            for i, channel in enumerate(channel_vec):
                if not read_data:
                    time_value, volt_value = self.channel_data[channel]
                else:
                    time_value, volt_value = self.read_waveform_data(channel)
                
                self.ax.plot(time_value, volt_value, label=labels[i])
        else:
            
            for i, channel in enumerate(channel_vec):
                if not read_data:
                    time_value, volt_value = self.channel_data[channel]
                else:
                    time_value, volt_value = self.read_sequence_frame(channel, frame_num=sequence_frame_number)#---(channel)
                
                self.ax.plot(time_value, volt_value, label=labels[i])
        
        if sequence_frame_number is None:
            self.ax.set_title(title)
        else:
            self.ax.set_title(title + " sequence frame: " + str(sequence_frame_number))
        
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.legend(loc="upper right")
        self.ax.grid(True)
        plt.show()

if __name__ == '__main__':
    # # Example plot and save the data
    scope = SiglentScope("USB0::0xF4EC::0x1011::SDS2PEED6R3524::INSTR")
    scope.plot_channels([1,2,3],labels=['signal','output','MZI'],title = "Modulator 1")  # Example usage
    # scope.save_data('channel_data.csv')
    
    # # Example of reading a frame and plotting it
    # import pickle
    # folder_name = r'some base folder name'
    
    # scope = SiglentScope("USB0::0xF4EC::0x1011::SDS2PEED6R3524::INSTR")
    # frame_start = 100
    # frame_stop = 167
    # for frame_number in range(frame_start,frame_stop+1,5):
    #     #show every fifth frame.
    #     scope.plot_channels([1,2,3,4],labels=['ramp','output','MZI',"Voltage"],sequence_frame_number=frame_number)  # Example usage
    #     base_filename = f"50Vpk2pk_frame_{frame_number}.pkl"
    #     pickle_filename = os.path.join(folder_name, f"{base_filename}.pkl")

    #     #do some processing
            
    #     # Combine the data and metadata into a single object
    #     complete_data = {
    #         'scope_channel_data': scope.channel_data,
    #         'scope_frame_number': scope.frame_timestamp,
    #         'sequence_frame_number':scope.sequence_frame_number,
    #         'description':"This is a 50 volt peak to peak scan of a ring resontor with 0 offset. at 0.5Hz. The start and end frames should have the extremum voltage data.",
    #         'channel_labels': ['ramp','output','MZI',"Voltage"],
    #         'central_wavelength_nm':1550.747,
    #         'MZI_Freq_MHz': 196,
                   
    #         }
    
    #     # Save the data to a pickle file
    #     with open(pickle_filename, 'wb') as f:
    #         pickle.dump(complete_data, f)
        
        
    # # Example read the data and then plot it
    # scope = SiglentScope("USB0::0xF4EC::0x1011::SDS2PEED6R3524::INSTR")
    # scope.read_waveform_data(channel=1)
    # scope.read_waveform_data(channel=2)
    # scope.read_waveform_data(channel=4)
    # scope.plot_channels([1,2],labels=['signal','output'],title = "Modulator 1", read_data=False)  # Example usage of plot without reading the data again.
    # scope.save_data('channel_data.csv')
    
    
    # # Example plot all the visa-readable devices
    # visa_addresses = SiglentScope.list_visa_addresses()
    # for address, idn in visa_addresses.items():
    #     print(f"{address}: {idn}")

