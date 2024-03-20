# SiglentScope

A Python library to interface with Siglent oscilloscopes, enabling data acquisition.
Nothing fancy but will get you started.
Tested on SDS2204X Plus.

## Installation

To install the library, use the following command:

```bash
pip install git+https://github.com/grishaspektor/singletscope.git
```

## Usage
Initializing the Oscilloscope
To start, initialize the SiglentScope object with your oscilloscope's VISA resource string:

```python
from singletscope import SiglentScope

# Replace 'resource_string' with your actual VISA resource string
scope = SiglentScope("USB0::0xF4EC::0x1011::SDS2PEED6R3524::INSTR")
```

### Reading Waveform Data
To read waveform data from a specific channel:

```python

# Read waveform data from channel 1
time_values, voltage_values = scope.read_waveform_data(1)
```
### Plotting Channel Data
To plot the waveform data from specified channels:

```python

# Plot data for channels 1 and 2
scope.plot_channels([1, 2], labels=['Channel 1', 'Channel 2'], title="Waveform Data")
```
### Saving Data and Plots
To save the waveform data and plots:

```python

# Save waveform data and plot for the channels read
scope.save_data('output/channel_data')
```
Data and plots will be saved in the output directory, using the base filename provided (channel_data in this example).

### Listing VISA Addresses
To list all VISA addresses connected to your computer and their corresponding device IDs:

```python

# List all VISA addresses and their device IDNs
addresses = SiglentScope.list_visa_addresses()
for address, idn in addresses.items():
    print(f"{address}: {idn}")
```
## Documentation
For more detailed information, refer to the method documentation within the code.
