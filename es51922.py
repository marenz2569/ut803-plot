#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utility for parsing data from multimeters based on Cyrustek ES51922 chipset.

Written using as much information from the datasheet as possible
(some functionality is not documented).
The utility should output only sensible measurements and checks if
the data packet is valid (there is no check sum in the data packet).

Tested with UNI-T UT61E multimeter.
All the functionality of UNI-T UT61E seems to work fine.
Not tested: temperature and ADP modes.

Licenced LGPL2+
Copyright
  (C) 2013 Domas Jokubauskis (domas@jokubauskis.lt)
  (C) 2014 Philipp Klaus (philipp.l.klaus@web.de)

Some information was used from dmmut61e utility by Steffen Vogel
"""

from __future__ import print_function
import sys
from decimal import Decimal
import struct
import logging
import datetime

def test_bit(int_type, offset):
    """
    testBit() returns True if the bit at 'offset' is one.
    From http://wiki.python.org/moin/BitManipulation
    """
    mask = 1 << offset
    return bool(int_type & mask)

def get_bits(int_type, template):
    """
    Extracts 'named bits' from int_type.
    Naming the bits works by supplying a list of
    bit names (or fixed bits as 0/1) via template.
    """
    bits = {}
    for i in range(4):
        bit = test_bit(int_type, i)
        bit_name = template[3-i]
        #print(bit, bit_name, i)
        if bit_name in (0,1) and bit==bit_name:
            continue
        elif bit_name in (0,1):
            raise ValueError
        else:
           bits[bit_name] = bit
    return bits

"""
The entries in the following RANGE dictionaries have the following structure:

    (value_multiplier, dp_digit_position, display_unit)

value_multiplier:  Multiply the displayed value by this factor to get the value in base units.
dp_digit_position: The digit position of the decimal point in the displayed meter reading value.
display_unit:      The unit the displayed value is shown in.
"""
RANGE_DIODE = [
    (1e0, 3, "V"), #6.000V
]

RANGE_FREQUENCY = [
    (1e0, 0, "Hz"), #6000Hz
    (1e3, 2, "kHz"), #60.00kHz
    (1e3, 1, "kHz"), #600.0kHz
		(1e6, 3, "MHz"), #6.000MHz
		(1e6, 2, "MHz"), #60.00MHz
]

RANGE_RESISTANCE = [
    (1e0, 1, "Ω"), #600.0Ω
    (1e3, 3, "kΩ"), #6.000KΩ
    (1e3, 2, "kΩ"), #60.00KΩ
    (1e3, 1, "kΩ"), #600.0KΩ
    (1e6, 3, "MΩ"), #6.000MΩ
    (1e6, 2, "MΩ"), #60.00MΩ
]

RANGE_CONTINUITY = [
    (1e0, 1, "Ω"), #600.0Ω
]

RANGE_CAPACITANCE = [
    (1e-9, 3, "nF"), #6.000nF
    (1e-9, 2, "nF"), #60.00nF
    (1e-9, 1, "nF"), #600.0nF
    (1e-6, 3, "µF"), #6.000μF
    (1e-6, 2, "µF"), #60.00μF
    (1e-6, 1, "µF"), #600.0μF
    (1e-3, 3, "mF"), #6.000mF
]

RANGE_CURRENT_10A = [
    (1e0, 2, "A") #10.00A
]

RANGE_VOLTAGE = [
    (1e0, 3, "V"),  #6.000V
    (1e0, 2, "V"),  #60.00V
    (1e0, 1, "V"),  #600.0V
    (1e0, 0, "V"),  #1000V
    (1e-1, 1,"mV"), #600.0mV
]

RANGE_CURRENT_AUTO_UA = [
    (1e-6, 1, "µA"), #
    (1e-6, 0, "µA"), #2
]

RANGE_HFE =  [
    (1e0, 0, "hFe"),
]

RANGE_CURRENT_AUTO_MA = [
    (1e-3, 2, "mA"), #
    (1e-3, 1, "mA"), #2
]

FUNCTION = {
    # (function, subfunction, unit)
    0x01: ("diode", RANGE_DIODE, "V"),
    0x02: ("frequency", RANGE_FREQUENCY, "Hz"),
    0x03: ("resistance", RANGE_RESISTANCE, "Ω"),
    0x04: ("temperature", None, "deg"),
    0x05: ("continuity", RANGE_CONTINUITY, "Ω"),
    0x06: ("capacitance", RANGE_CAPACITANCE, "F"),
    0x09: ("current", RANGE_CURRENT_10A, "A"), #10 A current
    0x0b: ("voltage", RANGE_VOLTAGE, "V"),
    0x0d: ("current", RANGE_CURRENT_AUTO_UA, "A"),
    0x0e: ("current gain", RANGE_HFE, ""),
    0x0f: ("current", RANGE_CURRENT_AUTO_MA, "A"),
}

STATUS = [
    "JUDGE", # 1-°C, 0-°F.
    "SIGN", # 1-minus sign, 0-no sign
    "BATT", # 1-battery low
    "OL", # input overflow
]

OPTION1 = [
		"HOLD",
    "MAX", # maximum
    "MIN", # minimum
		0,
]

OPTION2 = [
		"DC",
		"AC",
		"AUTO",
    0,
]

def parse(packet):
    """
    The most important function of this module:
    Parses 9-byte-long packets from the UT803 DMM and returns
    a dictionary with all information extracted from the packet.
    """
    d_range, \
    d_digit0, d_digit1, d_digit2, d_digit3, \
    d_function, d_status, \
    d_option1, d_option2 = struct.unpack("B"*9, packet)
    
    options = {}
    d_options = (d_status, d_option1, d_option2)
    OPTIONS = (STATUS, OPTION1, OPTION2)
    for d_option, OPTION in zip(d_options, OPTIONS):
        bits = get_bits(d_option, OPTION)
        options.update(bits)
    
    function = FUNCTION[d_function & 0x0f]

    mode = function[0]
    m_range =  function[1][d_range & 0x0f]
    unit = function[2]
    if mode == "frequency" and options["JUDGE"]:
        mode = "duty_cycle"
        unit = "%"
        m_range = (1e0, 1, "%") #2200.0°C
    
    current = None
    if options["AC"] and options["DC"]:
        raise ValueError
    elif options["DC"]:
        current = "DC"
    elif options["AC"]:
        current = "AC"
    
    operation = "normal"
    if options["OL"]:
        operation = "overload"
    
    if options["AUTO"]:
        mrange = "auto"
    else:
        mrange = "manual"
    
    if options["BATT"]:
        battery_low = True
    else:
        battery_low = False
    
    # data hold mode, received value is actual!
    if options["HOLD"]:
        hold = True
    else:
        hold = False
    
    peak = None
    if options["MAX"]:
        peak = "max"
    elif options["MIN"]:
        peak = "min"
    
    digits = [d_digit0, d_digit1, d_digit2, d_digit3]
    digits = [digit & 0x0f for digit in digits]
    
    display_value = 0
    for i, digit in zip(range(4), digits):
        display_value += digit*(10**(3-i))
    if options["SIGN"]: display_value = -display_value
    display_value = Decimal(display_value) / 10**m_range[1]
    display_unit = m_range[2]
    value = float(display_value) * m_range[0]
    
    if operation != "normal":
        display_value = ""
        value = ""
    results = {
        'value'         : value,
        'unit'          : unit,
        'display_value' : display_value,
        'display_unit'  : display_unit,
        'mode'          : mode,
        'current'       : current,
        'peak'          : peak,
        'hold'          : hold,
        'range'         : mrange,
        'operation'     : operation,
        'battery_low'   : battery_low
    }
    
    return results

def output_readable(results):
    operation = results["operation"]
    battery_low = results["battery_low"]
    if operation == "normal":
        display_value = results["display_value"]
        display_unit = results["display_unit"]
        line = "{value} {unit}".format(value=display_value, unit=display_unit)
    else:
        line = "-, the measurement is {operation}ed!".format(operation=operation)
    if battery_low:
        line.append(" Battery low!")
    return line

def format_field(results, field_name):
    """
    Helper function for output formatting.
    """
    value = results[field_name]
    if field_name == "value":
        if results["operation"]=="normal":
            return str(value)
        else:
            return ""
    if value==None:
        return ""
    elif value==True:
        return "1"
    elif value==False:
        return "0"
    else:
        return str(value)

CSV_FIELDS = ["value", "unit", "mode", "current", "operation", "peak",
            "battery_low", "hold"]
def output_csv(results):
    """
    Helper function to write output lines to a CSV file.
    """
    field_data = [format_field(results, field_name) for field_name in CSV_FIELDS]
    line = ";".join(field_data)
    return line

def main():
    """
    Main function: Entry point if running this module from the command line.
    Reads lines from stdin and parses them as ES51922 messages.
    Prints to stdout and to a CSV file.
    """
    import argparse
    parser = argparse.ArgumentParser(description='Utility for parsing data from multimeters based on Cyrustek ES51922 chipset.')
    parser.add_argument('-m', '--mode', choices=['csv', 'plot', 'readable'],
                        default="csv",
                        help='output mode (default: csv)')
    parser.add_argument('-f', '--file',
                        help='output file')
    parser.add_argument('--verbose', action='store_true',
                        help='enable verbose output')
    args = parser.parse_args()
    
    if args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    logging.basicConfig(format='%(levelname)s:%(message)s', level=log_level)
    
    output_file = None
    if args.mode == 'csv':
        timestamp = datetime.datetime.now()
        date_format = "%Y-%m-%d_%H:%S"
        timestamp = timestamp.strftime(date_format)
        if args.file:
            file_name = args.file
        else:
            file_name = "measurement_{}.csv".format(timestamp)
        output_file = open(file_name, "w")
        logging.info('Writing to file "{}"'.format(file_name))
        header = "timestamp;{}\n".format(";".join(CSV_FIELDS))
        output_file.write(header)
    elif args.mode == 'chch':
        if args.file:
            file_name = args.file
        else:
            logging.error('No file name specified')
    while True:
        line = sys.stdin.readline()
        if not line: break
        line = line.strip()
        try:
            line = line.encode('ascii')
        except:
            logging.warning('Not an ASCII input line, ignoring: "{}"'.format(line))
            continue
        timestamp = datetime.datetime.now()
        timestamp = timestamp.isoformat(sep=' ')
        if len(line)==9:
            try:
                results = parse(line)
            except Exception as e:
                logging.warning('Error "{}" packet from multimeter: "{}"'.format(e, line))
            if args.mode == 'csv':
                line = output_csv(results)
                output_file.write("{};{}\n".format(timestamp, line))
            elif args.mode == 'readable':
                line = output_readable(results)
                print(timestamp.split(" ")[1], line)
            elif args.mode == 'plot':
                ost = results['mode'] + ': '
                if results['operation'] != 'normal':
                    ost += 'overload'
                else:
                    ost += str(results['value']) + results['unit']
                output_file = open(file_name, 'a')
                output_file.write(ost + '\n')
                output_file.close()
                print(ost)
            else:
                raise NotImplementedError
        elif line:
            logging.warning('Unknown packet from multimeter: "{}", length: {}'.format(line, len(line)))
        else:
            logging.warning('Not a response from the multimeter: ""'.format(line))

if __name__ == "__main__":
    main()
