#!/usr/bin/env python3
"""
UART Diagnostic Tool for FPGA Communication Debugging

This script helps diagnose UART communication issues by:
- Testing different serial port configurations
- Capturing and displaying raw UART traffic
- Checking if firmware is running
- Verifying baud rate settings

Usage:
    python uart_diagnose.py --port COM3
    python uart_diagnose.py --port COM3 --baud 9600 --send s
"""
import serial
import serial.tools.list_ports
import time
import sys
import argparse


def bytes_to_hex(data):
    """Convert bytes to hex string"""
    return ' '.join(f'{b:02X}' for b in data)


def bytes_to_ascii(data):
    """Convert bytes to ASCII, replacing non-printable with dots"""
    return ''.join(chr(b) if 32 <= b < 127 else '.' for b in data)


def list_ports():
    """List all available serial ports"""
    ports = serial.tools.list_ports.comports()
    if not ports:
        print("No serial ports found!")
        return
    
    print("\n=== Available Serial Ports ===")
    for i, port in enumerate(ports, 1):
        print(f"{i}. {port.device}")
        print(f"   Description: {port.description}")
        print(f"   Hardware ID: {port.hwid}")
        print()


def test_connection(port, baud, timeout=5.0, send_char=None):
    """Test UART connection and capture output"""
    print(f"\n=== Testing {port} at {baud} baud ===")
    print(f"Timeout: {timeout}s")
    print(f"Format: 8N1 (8 data bits, No parity, 1 stop bit)")
    print(f"Flow control: None")
    print()
    
    try:
        # Open serial port with explicit settings
        ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=8,
            parity='N',
            stopbits=1,
            timeout=0.5,  # Short timeout for responsive reading
            xonxoff=False,
            rtscts=False,
            dsrdtr=False
        )
    except Exception as e:
        print(f"❌ Error opening port: {e}")
        print("\nPossible causes:")
        print("  - Port is in use by another program (close PuTTY, Vivado, etc.)")
        print("  - Insufficient permissions (try running as Administrator)")
        print("  - Port does not exist (check Device Manager)")
        return False
    
    print("✓ Port opened successfully")
    print()
    
    # Flush any existing data
    ser.reset_input_buffer()
    
    # If send character specified, send it first
    if send_char:
        print(f"--- Sending: '{send_char}' (0x{ord(send_char):02X}) ---\n")
        ser.write(send_char.encode('ascii'))
        time.sleep(0.1)  # Brief delay after sending
    
    # Capture data for specified timeout
    print(f"--- Capturing for {timeout}s ---")
    print("Press Ctrl+C to stop early\n")
    
    all_data = bytearray()
    lines_received = []
    start_time = time.time()
    line_number = 1
    
    try:
        while (time.time() - start_time) < timeout:
            # Read a line (or timeout)
            line_bytes = ser.readline()
            
            if line_bytes:
                all_data.extend(line_bytes)
                
                # Try to decode as text
                try:
                    line_text = line_bytes.decode('utf-8', errors='replace').strip()
                    if line_text:
                        print(f"[{line_number:04d}] {line_text}")
                        lines_received.append(line_text)
                        line_number += 1
                except:
                    # Show as hex if not valid UTF-8
                    hex_str = bytes_to_hex(line_bytes)
                    print(f"[{line_number:04d}] [HEX] {hex_str}")
                    lines_received.append(f"[HEX] {hex_str}")
                    line_number += 1
    
    except KeyboardInterrupt:
        print("\n\n--- Stopped by user ---\n")
    
    ser.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    print(f"Lines received: {len(lines_received)}")
    print(f"Total bytes:    {len(all_data)}")
    
    if len(all_data) == 0:
        print("\n⚠ NO DATA RECEIVED")
        print("\nPossible causes:")
        print("  1. FPGA firmware not running")
        print("     → Check if FPGA is programmed with correct bitstream")
        print("     → Try pressing PROG button to reset FPGA")
        print("  2. Wrong baud rate")
        print("     → Try different rates: 9600, 57600, 115200")
        print("  3. Wrong COM port")
        print("     → Use --list to see all available ports")
        print("  4. FPGA in bootloader mode")
        print("     → Need to upload firmware first")
    
    elif len(lines_received) > 0:
        print("\n✓ COMMUNICATION OK")
        print("\nFirst few lines:")
        for i, line in enumerate(lines_received[:5], 1):
            print(f"  {i}. {line}")
        
        # Check for expected firmware messages
        boot_found = any('MODE:' in line or 'BASELINE' in line for line in lines_received)
        ready_found = any('Ready' in line for line in lines_received)
        done_found = any('Done' in line for line in lines_received)
        
        print("\nFirmware detection:")
        print(f"  Boot banner:  {'✓' if boot_found else '✗'}")
        print(f"  'Ready' msg:  {'✓' if ready_found else '✗'}")
        print(f"  'Done' msg:   {'✓' if done_found else '✗'}")
        
        if boot_found and ready_found:
            print("\n✅ Firmware appears to be running correctly!")
            if send_char and not done_found:
                print(f"   However, 'Done' not seen after sending '{send_char}'")
                print("   → Algorithm may have crashed or taken too long")
        elif ready_found:
            print("\n⚠ 'Ready' seen but no boot banner - firmware may be mid-execution")
        else:
            print("\n⚠ Expected firmware messages not found")
            print("   → May be wrong firmware or bootloader output")
    
    else:
        print("\n⚠ Received bytes but no valid lines")
        print("\nLast 50 bytes (HEX):")
        print(bytes_to_hex(all_data[-50:]))
        print("\nLast 50 bytes (ASCII):")
        print(bytes_to_ascii(all_data[-50:]))
        print("\nPossible causes:")
        print("  - Wrong baud rate (data is garbled)")
        print("  - Wrong serial format (try 7E1 instead of 8N1)")
    
    print("=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description='UART diagnostic tool for FPGA communication debugging',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all serial ports
  %(prog)s --list
  
  # Test COM3 at 115200 baud
  %(prog)s --port COM3
  
  # Test and send 's' to trigger baseline
  %(prog)s --port COM3 --send s
  
  # Try different baud rate
  %(prog)s --port COM3 --baud 9600
        """
    )
    
    parser.add_argument('--list', action='store_true', help='List all available serial ports')
    parser.add_argument('--port', help='Serial port to test (e.g., COM3, /dev/ttyUSB1)')
    parser.add_argument('--baud', type=int, default=115200, help='Baud rate (default: 115200)')
    parser.add_argument('--timeout', type=float, default=5.0, help='Capture timeout in seconds (default: 5)')
    parser.add_argument('--send', help='Character to send after opening port (e.g., "s")')
    parser.add_argument('--try_all_bauds', action='store_true', help='Try multiple common baud rates')
    
    args = parser.parse_args()
    
    if args.list:
        list_ports()
        return
    
    if not args.port:
        print("Error: --port required (or use --list to see available ports)")
        print("\nUsage: uart_diagnose.py --port COM3")
        sys.exit(1)
    
    if args.try_all_bauds:
        common_bauds = [9600, 19200, 38400, 57600, 115200]
        print(f"\n{'='*60}")
        print(f"Testing multiple baud rates on {args.port}")
        print(f"{'='*60}\n")
        
        for baud in common_bauds:
            test_connection(args.port, baud, timeout=2.0, send_char=args.send)
            time.sleep(0.5)
    else:
        test_connection(args.port, args.baud, timeout=args.timeout, send_char=args.send)


if __name__ == "__main__":
    main()
