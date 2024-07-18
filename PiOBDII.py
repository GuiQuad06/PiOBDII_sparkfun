#!/usr/bin/python3

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#/***************************************************************************/
#/* Raspberry Pi ELM327 OBBII CAN BUS Diagnostic Software.                  */
#/*                                                                         */
#/* (C) Jason Birch 2018-04-27 V1.00                                        */
#/*                                                                         */
#/* Initial OBDII Python application to read trouble codes from the ECU and */
#/* display each trouble code along with it's human readable description.   */
#/*                                                                         */
#/* In this initial version, the user must update the constant at the top   */
#/* of the program code, SERIAL_PORT_NAME, with the serial port which is    */
#/* to be used. Future verstions of the code should have a graphical        */
#/* interface for configuration and provide more features than just reading */
#/* trouble codes.                                                          */
#/***************************************************************************/

import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError as e:
    print(e)
    msg = str(e).split()
    print("Please, run: pip install " + msg[-1].replace("'", ""))
    input("Press enter to quit. . . ")
    sys.exit()

# Set SERIAL_PORT_NAME to the serial port your ELM327 device is connected to. 
SERIAL_PORT_BAUD = 9600
SERIAL_PORT_TIME_OUT = 60

ELM_CONNECT_SETTLE_PERIOD = 5
ELM_CONNECT_TRY_COUNT = 5

#/*************************************************/
#/* This function can be used to auto detect the  */
#/* serial COM Port.                              */
#/* Only one match is allowed, else an Error is   */
#/* raised (ValueError).                          */
#/* Takes the search pattern as a parameter,      */
#/* for instance FTDI cables interfaces started   */
#/* with "USB Serial Port"                        */
#/* Returns the COM Port.                         */
#/* response.                                     */
#/*************************************************/
def serial_auto_detect(search_pattern="USB Serial Port"):
    # retrieve comport by description
    tmp_comport = list(serial.tools.list_ports.grep(f".*{search_pattern}.*"))

    if len(tmp_comport) == 0:
        raise ValueError(f"Unable to find comport with pattern '{search_pattern}'")

    if len(tmp_comport) > 1:
        tmp_name = "\t-> " + ",\n\t-> ".join([c.description for c in tmp_comport])
        raise ValueError(f"Several comports with pattern '{search_pattern}'\n{tmp_name}")

    else:
        comport = tmp_comport[0]
        print(f"[auto detect] Found {comport.description}")
        return comport


#/*************************************************/
#/* Talk to the ELM327 device over a serial port. */
#/* Send request data, and wait for the response. */
#/* The expected response ends with a prompt      */
#/* character '>', the ELM327 provides promting   */
#/* for more user requests.                       */
#/* Otherwise a timeout occurs waiting for a      */
#/* response.                                     */
#/*************************************************/
def GetResponse(SerialCon, Data):
	SerialCon.write(Data)
	Response = ""
	ReadChar = 1
	while ReadChar != b'>' and ReadChar != 0:
		ReadChar = SerialCon.read()
		if ReadChar != b'>':
			Response += str(ReadChar, 'utf-8')
	return Response.replace('\r', '\n').replace('\n\n', '\n')



#/*******************************************************/
#/* The OBDII protocol will sometimes prefix a response */
#/* with confirmation of the request sent or other      */
#/* unwanted bytes of data. Use this function to remove */
#/* unwanted bytes from the start of lines, and         */
#/* concatenate the remainder of the response into a    */
#/* single line of data, ready for processing.          */
#/*******************************************************/
def PruneData(Data, RemoveByteCount):
	Response = ""
	Lines = Data.split('\n')
	for Line in Lines:
		Response += Line[2 * RemoveByteCount:]
	return Response


#/*******************************************************/
#/* This is very particular case I got from get VIN     */
#/* It seems that the STN1110 chip is sending the data  */
#/* differently on my SparkFun OBDII UART board.        */
#/* I have to prune a different nb of byte depending on */
#/* the line number as the chip is sending line number !*/
#/* Only the VIN (0902) as this format of data.         */
#/*******************************************************/
def PruneDataVin(Data, RemoveByteCount):
	Response = ""
	for index, Line in enumerate(Data.split('\n')):
		# Second line "0:" + ACK shall be pruned" 
		if index == 1:
			Response += Line[2 * 4:]
		# Other lines only "i:" line number shall be pruned
		elif 2 <= index < 4:
			Response += Line[2:]
		# First & last line RemoveByteCount
		else:
			Response += Line[2 * RemoveByteCount:]
	return Response


#/**********************************************************/
#/* Convert pairs of data bytes into actual trouble codes, */
#/* translating the first digit as required, and ignoring  */
#/* zero value data.                                       */
#/**********************************************************/
def DataToTroubleCodes(Data):
	TroubleCodes = list()
	while len(Data) > 0:
		ThisCode = Data[:4]
		if int(ThisCode) != 0:
			TroubleCodes.append(TroubleCodePrefix[ThisCode[0]] + ThisCode[1:])
		Data = Data[4:]
	return TroubleCodes



#/*****************************************************/
#/* Get the trouble codes from the ECU and lookup the */
#/* trouble code descriptions. Return the data in a   */
#/* formatted string.                                 */
#/*****************************************************/
def GetTroubleCodeData(ELM327, OBDIImode):
	TroubleCodeData = ""
	Response = GetResponse(ELM327, OBDIImode + b'\r')
	Response = PruneData(Response, 1)
	TroubleCodes = DataToTroubleCodes(Response)
	for TroubleCode in TroubleCodes:
		TroubleCodeData += TroubleCode
		try:
			TroubleCodeData += " : " + TroubleCodeDescriptions[TroubleCode] + "\n"
		except:
			TroubleCodeData += " : [DESCRIPTION NOT FOUND]\n"
	return TroubleCodeData



#  /**********************************************/
# /* Read OBDII Trouble Code lookup table data. */
#/**********************************************/
TroubleCodePrefix = {}
with open("TroubleCodePrefix.txt", encoding='utf-8') as ThisFile:
	for ThisLine in ThisFile:
		Digit, Code = ThisLine.partition(" ")[::2]
		TroubleCodePrefix[Digit] = Code.strip()

#  /**********************************************************/
# /* Read OBDII Trouble Code Description lookup table data. */
#/**********************************************************/
TroubleCodeDescriptions = {}
# Load the ISO/SAE Trouble Code Descriptions.
with open("TroubleCodes-ISO-SAE.txt", encoding='utf-8') as ThisFile:
	for ThisLine in ThisFile:
		Code, Description = ThisLine.partition(" ")[::2]
		TroubleCodeDescriptions[Code] = Description.strip()
# Load the Vehicle/Manufacturer Trouble Code Descriptions.
with open("TroubleCodes-R53_Cooper_S.txt", encoding='utf-8') as ThisFile:
	for ThisLine in ThisFile:
		Code, Description = ThisLine.partition(" ")[::2]
		TroubleCodeDescriptions[Code] = Description.strip()

#  /****************************************************************/
# /* Open the required serial port which the ELM327 device is on. */
#/****************************************************************/
comport = serial_auto_detect()
ELM327 = serial.Serial(comport.device, SERIAL_PORT_BAUD)
ELM327.timeout = SERIAL_PORT_TIME_OUT
ELM327.write_timeout = SERIAL_PORT_TIME_OUT
print("Serial Port: " + ELM327.name)

# Initialize the ELM327 device.
Response = GetResponse(ELM327, b'AT Z\r')
print(Response)

# Echo Off, for faster communications.
Response = GetResponse(ELM327, b'AT E0\r')
if Response != 'AT E0\nOK\n':
	print("FAILED: AT E0 (Set Echo Off)")

# Don't print space characters, for faster communications.
Response = GetResponse(ELM327, b'AT S0\r')
if Response != 'OK\n':
	print("FAILED: AT S0 (Set Space Characters Off)")

# Set CAN communication protocol to ISO 9141-2 or auto detect on fail.
Response = GetResponse(ELM327, b'AT SP A3\r')
if Response != 'OK\n':
	print("FAILED: AT SP A3 (Set Protocol ISO 9141-2 / Auto)")

# Set CAN Baud to high speed.
Response = GetResponse(ELM327, b'AT IB 10\r')
if Response != 'OK\n':
	print("FAILED: AT IB 10 (Set High Speed CAN BUS)")

# Get the ELM device description.
Response = GetResponse(ELM327, b'AT @1\r')
print("ELM Device Description: " + Response)

# Get the ELM device user supplied description.
Response = GetResponse(ELM327, b'AT @2\r')
print("ELM Device User Description: " + Response)

# Get the Voltage measured at the OBDII connector.
Response = GetResponse(ELM327, b'AT RV\r')
print("Volt Reading At OBDII Connector: " + Response)

# Initial connect to OBDII CAN BUS with first request.
print("CONNECTING TO CAN BUS FOR OBDII COMMUNICATION...")
TryCount = 5
Response = "UNABLE TO CONNECT"
while Response.find("UNABLE TO CONNECT") != -1 and TryCount > 0:
	TryCount -= 1
	# Wait before tring to connect to ensure EML device is idle.
	Count = ELM_CONNECT_SETTLE_PERIOD
	while Count > 0:
		sys.stdout.write('\r' + str(Count))
		sys.stdout.flush()
		time.sleep(1)
		Count -= 1
	sys.stdout.write('\r \r')
	sys.stdout.flush()
	# Request Mode 1 PID 0 (Supported PIDs for Mode 1) to test connection.
	Response = GetResponse(ELM327, b'0100\r')
	if Response.find("UNABLE TO CONNECT") != -1:
		print("REATTEMPTING CONNECT... [" + str(TryCount) + "]")
if Response.find("UNABLE TO CONNECT") != -1:
	print("FAILED TO CONNECT TO CAN BUS")
	# Close serial port after use.
	ELM327.close()
	quit()

# Get the current OBDII data protocol after OBDII CAN BUS communication.
Response = GetResponse(ELM327, b'AT DP\r')
print("Using CAN BUS Protocol: " + Response)

# Get the current Vehicle VIN Number from the ECU.
Response = GetResponse(ELM327, b'0902\r')
Response = PruneDataVin(Response, 3)
Response = str(bytearray.fromhex(Response).replace(bytes([0x00]), b' '), 'UTF-8')
print("Vehicle VIN Number: " + str(Response) + "\n")

# Get the Stored Trouble Codes from the ECU.
Response = GetTroubleCodeData(ELM327, b'03')
print("Stored Trouble Codes:")
print(Response)

# Get the Pending Trouble Codes from the ECU.
Response = GetTroubleCodeData(ELM327, b'07')
print("Pending Trouble Codes:")
print(Response)

# Get the Permanent Trouble Codes from the ECU.
Response = GetTroubleCodeData(ELM327, b'0A')
print("Permanent Trouble Codes:")
print(Response)

# Erase all Pending/Stored Trouble Codes and Data from the ECU.
# Response = GetResponse(ELM327, b'04\r')

# Close serial port after use.
ELM327.close()

