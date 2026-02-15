#!/usr/bin/env python3
"""
Quick UART sniffer for debugging serial communication.
Listens to a serial port and prints everything received.
Useful for diagnosing what the FPGA is actually sending.
"""
import serial
import sys
import argparse
import time

def main():
    parser = argparse.ArgumentParser(description='UART sniffer - print all serial output')
    parser.add_argument('--port', required=True, help='Serial port (e.g., COM3 or /dev/ttyUSB1)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--timeout', type=float, default=1.0, help='Read timeout in seconds (default: 1.0)')
    parser.add_argument('--hex', action='store_true', help='Show hex values of received bytes')
    parser.add_argument('--send', help='Send this string on startup (e.g., "s" to trigger FPGA)')
    args = parser.parse_args()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=args.timeout)
        print(f"Connected to {args.port} at {args.baud} baud")
        print(f"Timeout: {args.timeout}s")
        print("Press Ctrl+C to exit\n")
        print("-" * 60)
    except Exception as e:
        print(f"Error opening {args.port}: {e}")
        sys.exit(1)

    # Send initial command if specified
    if args.send:
        print(f"Sending: {repr(args.send)}")
        ser.write(args.send.encode('utf-8'))
        print("-" * 60)

    try:
        line_count = 0
        while True:
            line = ser.readline()
            if line:
                line_count += 1
                decoded = line.decode('utf-8', errors='replace').rstrip('\r\n')
                
                if args.hex:
                    hex_str = ' '.join(f'{b:02X}' for b in line)
                    print(f"[{line_count:04d}] {decoded}")
                    print(f"       HEX: {hex_str}")
                else:
                    print(f"[{line_count:04d}] {decoded}")
            else:
                # Timeout - check for individual bytes
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    decoded = data.decode('utf-8', errors='replace')
                    print(f"[PARTIAL] {repr(decoded)}")
                else:
                    # True timeout - print a dot to show we're alive
                    print(".", end='', flush=True)
                    time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\n\nReceived {line_count} lines. Exiting.")
        ser.close()

if __name__ == "__main__":
    main()
